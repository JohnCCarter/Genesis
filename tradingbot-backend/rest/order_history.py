"""
Order History Service - TradingBot Backend

Denna modul hanterar historiska orderdata från Bitfinex API.
Inkluderar funktioner för att hämta orderhistorik, trades och ledger.
"""

import asyncio
import json
import random
import time
from datetime import datetime
from typing import Any

import httpx
from services.exchange_client import get_exchange_client
from pydantic import BaseModel

from config.settings import settings
from services.metrics import record_http_result, metrics_store
from utils.advanced_rate_limiter import get_advanced_rate_limiter
from utils.logger import get_logger
from utils.private_concurrency import get_private_rest_semaphore

logger = get_logger(__name__)


class OrderHistoryItem(BaseModel):
    """Modell för en historisk order."""

    id: int
    symbol: str
    status: str  # "EXECUTED", "CANCELED", etc.
    type: str
    amount: float
    original_amount: float
    price: float
    avg_execution_price: float | None = None
    created_at: datetime
    updated_at: datetime | None = None
    is_cancelled: bool = False
    is_hidden: bool = False

    @classmethod
    def from_bitfinex_data(cls, data: list) -> "OrderHistoryItem":
        """Skapar en OrderHistoryItem från Bitfinex API-data."""
        if len(data) < 12:
            raise ValueError(f"Ogiltig orderhistorikdata: {data}")

        return cls(
            id=int(data[0]),
            symbol=data[1],
            status=data[2],
            type=data[3],
            amount=float(data[4]),
            original_amount=float(data[5]),
            price=float(data[6]),
            avg_execution_price=float(data[7]) if data[7] is not None else None,
            created_at=(
                datetime.fromtimestamp(float(data[8]) / 1000.0)
                if (len(data) > 8 and data[8] is not None and str(data[8]).strip() != "")
                else datetime.now()
            ),
            updated_at=(
                datetime.fromtimestamp(float(data[9]) / 1000.0)
                if (len(data) > 9 and data[9] is not None and str(data[9]).strip() != "")
                else None
            ),
            is_cancelled=bool(data[10]),
            is_hidden=bool(data[11]),
        )


class TradeItem(BaseModel):
    """Modell för en trade."""

    id: int
    symbol: str
    order_id: int
    execution_id: str | int | float | None = None
    amount: float
    price: float
    fee: float
    fee_currency: str
    executed_at: datetime

    @classmethod
    def from_bitfinex_data(cls, data: list) -> "TradeItem":
        """Skapar en TradeItem från Bitfinex API-data.

        Bitfinex kan returnera olika former för trades:
        - Klassisk (utan order_type): [ID, PAIR, ORDER_ID, EXECUTION_ID, AMOUNT, PRICE, FEE, FEE_CURRENCY, MTS_CREATE]
        - Variant med tidsstämpel i index 2: [ID, PAIR, MTS_CREATE, ORDER_ID, EXECUTION_ID, AMOUNT, PRICE, FEE, FEE_CURRENCY]
        - Variant med order_type (t.ex. 'EXCHANGE MARKET') i index 5:
          [ID, PAIR, MTS_CREATE, ORDER_ID, EXECUTION_ID, ORDER_TYPE, AMOUNT, PRICE, FEE, FEE_CURRENCY]
        """
        if not data or len(data) < 8:
            raise ValueError(f"Ogiltig tradedata: {data}")

        def try_float(x):
            try:
                return float(x)
            except Exception:
                return 0.0

        trade_id = int(data[0])
        symbol = data[1]

        mts_create: int | None = None
        order_id: int = 0
        execution_id: str | None = None
        amount: float = 0.0
        price: float = 0.0
        fee: float = 0.0
        fee_currency: str = ""

        try:
            # Fall 1: ORDER_TYPE som str på index 5
            if len(data) >= 10 and isinstance(data[5], str):
                # [id, sym, mts, orderId, execId, type, amount, price, fee, feeCur]
                mts_create = int(data[2]) if data[2] is not None else None
                order_id = int(data[3]) if data[3] is not None else 0
                execution_id = data[4] if data[4] else None
                amount = try_float(data[6])
                price = try_float(data[7])
                fee = try_float(data[8])
                fee_currency = str(data[9]) if len(data) > 9 else ""
            # Fall 2: tidsstämpel på index 2 (ms)
            elif len(data) >= 9 and isinstance(data[2], (int, float)) and float(data[2]) > 10_000_000_000:
                # [id, sym, mts, orderId, execId, amount, price, fee, feeCur]
                mts_create = int(data[2])
                order_id = int(data[3]) if len(data) > 3 and data[3] is not None else 0
                execution_id = data[4] if len(data) > 4 else None
                amount = try_float(data[5]) if len(data) > 5 else 0.0
                price = try_float(data[6]) if len(data) > 6 else 0.0
                fee = try_float(data[7]) if len(data) > 7 else 0.0
                fee_currency = str(data[8]) if len(data) > 8 else ""
            else:
                # Fallback: klassisk mappning utan mts i index 2
                # [id, sym, orderId, execId, amount, price, fee, feeCur, mts]
                order_id = int(data[2]) if len(data) > 2 and data[2] is not None else 0
                execution_id = data[3] if len(data) > 3 else None
                amount = try_float(data[4]) if len(data) > 4 else 0.0
                price = try_float(data[5]) if len(data) > 5 else 0.0
                fee = try_float(data[6]) if len(data) > 6 else 0.0
                fee_currency = str(data[7]) if len(data) > 7 else ""
                if len(data) > 8 and isinstance(data[8], (int, float)):
                    mts_create = int(data[8])
        except Exception as e:
            raise ValueError(f"Kunde inte tolka tradedata: {data} ({e})") from e

        executed_at = datetime.fromtimestamp(mts_create / 1000) if mts_create else datetime.now()

        return cls(
            id=trade_id,
            symbol=symbol,
            order_id=order_id,
            execution_id=execution_id,
            amount=amount,
            price=price,
            fee=fee,
            fee_currency=fee_currency,
            executed_at=executed_at,
        )


class LedgerEntry(BaseModel):
    """Modell för en ledger-post."""

    id: int
    currency: str
    amount: float
    balance: float
    description: str
    created_at: datetime
    wallet_type: str

    @classmethod
    def from_bitfinex_data(cls, data: list) -> "LedgerEntry":
        """Skapar en LedgerEntry från Bitfinex API-data.

        Bitfinex kan returnera olika ordningar. Robust parsing:
        Förväntade fält: id (int), currency (str), mts (ms), amount (float), balance (float), description (str), wallet (str)
        """
        if not isinstance(data, (list, tuple)) or len(data) < 5:
            raise ValueError(f"Ogiltig ledgerdata: {data}")

        try:
            _id = int(data[0])
        except Exception:
            _id = 0
        _currency = str(data[1]) if len(data) > 1 else ""

        # Hitta timestamp (ms)
        _mts_ms = None
        for item in data:
            if isinstance(item, (int, float)) and float(item) > 10_000_000_000:
                _mts_ms = int(item)
                break
        created = datetime.fromtimestamp(_mts_ms / 1000) if _mts_ms else datetime.now()

        # Kandidater för numeriska amount/balance är de första två float-konverterbara
        numeric_vals: list[float] = []
        for item in data:
            if isinstance(item, (int, float)):
                # uteslut id och mts
                if int(item) == _id:
                    continue
                if _mts_ms and int(item) == _mts_ms:
                    continue
                numeric_vals.append(float(item))
            else:
                # Försök tolka str som float
                try:
                    val = float(item)
                    numeric_vals.append(val)
                except Exception:
                    pass
        amount = numeric_vals[0] if len(numeric_vals) >= 1 else 0.0
        balance = numeric_vals[1] if len(numeric_vals) >= 2 else 0.0

        # Beskrivning = första sträng som inte är currency och inte wallet-type token
        desc = ""
        wallet = ""
        for item in data:
            if isinstance(item, str):
                low = item.strip().lower()
                if low in ("exchange", "margin", "funding"):
                    if not wallet:
                        wallet = item
                    continue
                if item != _currency and not desc:
                    desc = item
        return cls(
            id=_id,
            currency=_currency,
            amount=float(amount),
            balance=float(balance),
            description=desc,
            created_at=created,
            wallet_type=wallet or "",
        )


class OrderHistoryService:
    """Service för att hämta och hantera orderhistorik från Bitfinex."""

    def __init__(self):
        self.settings = settings
        self.base_url = getattr(self.settings, "BITFINEX_AUTH_API_URL", None) or self.settings.BITFINEX_API_URL
        self.rate_limiter = get_advanced_rate_limiter()
        # Global semafor för alla privata REST-klasser
        self._sem = get_private_rest_semaphore()

    async def _signed_post_with_retry(self, endpoint: str, body: dict[str, Any] | None = None) -> httpx.Response:
        """
        Skicka ett signerat POST-anrop med timeout och retry/backoff.

        Återanvänder DATA_* inställningar för timeout/retries.
        Signerar på exakt samma JSON-sträng som skickas.
        """
        # Anropet hanteras nu helt av ExchangeClient, som har sin egen nonce/retry-logik.
        # Denna metod behålls för att hantera applikationsspecifik backoff/retry.
        
        # Bygg deterministisk JSON och signera den exakta strängen
        body = body or {}
        
        timeout = getattr(self.settings, "DATA_HTTP_TIMEOUT", 15.0)
        retries = max(int(getattr(self.settings, "DATA_MAX_RETRIES", 2) or 0), 0)
        backoff_base = max(int(getattr(self.settings, "DATA_BACKOFF_BASE_MS", 250) or 0), 0) / 1000.0
        backoff_max = max(int(getattr(self.settings, "DATA_BACKOFF_MAX_MS", 2000) or 0), 0) / 1000.0

        last_exc: Exception | None = None
        response: httpx.Response | None = None
        for attempt in range(retries + 1):
            try:
                # Circuit breaker: respektera cooldown
                if hasattr(self.rate_limiter, "can_request") and not self.rate_limiter.can_request(endpoint):
                    wait = self.rate_limiter.time_until_open(endpoint)
                    logger.warning(f"CB: {endpoint} stängd i {wait:.1f}s")
                    await asyncio.sleep(wait)
                # Använd rate limiter före varje request
                await self.rate_limiter.wait_if_needed(endpoint)

                _t0 = time.perf_counter()
                async with self._sem:
                    # Använd centraliserad ExchangeClient för signering/nonce-hantering
                    ec = get_exchange_client()
                    response = await ec.signed_request(method="post", endpoint=endpoint, body=body, timeout=timeout)
                _t1 = time.perf_counter()
                try:
                    record_http_result(
                        path=f"/{endpoint}",
                        method="POST",
                        status_code=int(response.status_code),
                        duration_ms=int((_t1 - _t0) * 1000),
                        _retry_after=response.headers.get("Retry-After"),
                    )
                except Exception:
                    pass

                    # Kontrollera om det är nonce-fel - bumpa och gör en engångs‑retry
                    if response.status_code == 500:
                        try:
                            error_data = response.json()
                            if (
                                isinstance(error_data, list)
                                and len(error_data) >= 3
                                and "nonce" in str(error_data[2]).lower()
                            ):
                                logger.error(f"🚨 Nonce-fel detekterat: {error_data}")
                                # Nonce bump hanteras redan i ExchangeClient.signed_request
                                # Returnera originalsvaret utan lokal bump
                                return response
                        except (json.JSONDecodeError, ValueError):
                            pass  # Inte JSON eller felformat, fortsätt med vanlig hantering

                    # Retrybara statuskoder (ej nonce-fel)
                    if response.status_code in (429, 500, 502, 503, 504):
                        # Hantera server busy med intelligenta backoffs
                        if "server busy" in (response.text or "").lower() or response.status_code in (429, 503):
                            # Circuit breaker + Retry-After
                            retry_after = response.headers.get("Retry-After")
                            if hasattr(self.rate_limiter, "note_failure"):
                                cooldown = self.rate_limiter.note_failure(endpoint, response.status_code, retry_after)
                                logger.warning(f"CB öppnad för {endpoint} i {cooldown:.1f}s")
                                try:
                                    # Toggle transport CB metric on failure
                                    metrics_store["transport_circuit_breaker_active"] = 1
                                except Exception:
                                    pass
                            # Ny: namngiven TransportCircuitBreaker wrapper (parallell markering)
                            # Transport‑CB hanteras av AdvancedRateLimiter
                            await self.rate_limiter.handle_server_busy(endpoint)
                        raise httpx.HTTPError("server busy")

                    response.raise_for_status()
                    # Återställ räknare och CB vid framgång
                    try:
                        self.rate_limiter.reset_server_busy_count()
                        try:
                            metrics_store["transport_circuit_breaker_active"] = 0
                        except Exception:
                            pass
                    except Exception:
                        pass
                    try:
                        if hasattr(self.rate_limiter, "note_success"):
                            self.rate_limiter.note_success(endpoint)
                    except Exception:
                        pass
                    # Ny: parallell success till TransportCircuitBreaker
                    # Transport‑CB hanteras av AdvancedRateLimiter
                    return response

            except Exception as e:
                last_exc = e
                if attempt < retries:
                    delay = min(backoff_max, backoff_base * (2**attempt)) + random.uniform(0, 0.1)
                    await asyncio.sleep(delay)
                    continue
                break

        # Om vi hamnar här, kasta sista undantaget om svar finns
        if response is not None:
            try:
                # Trunkera text för att undvika stora loggar
                text = response.text or ""
                if len(text) > 300:
                    text = text[:300] + "... [truncated]"
                logger.error(
                    "Bitfinex API fel %s på %s: %s",
                    response.status_code,
                    endpoint,
                    text,
                )
            except Exception:
                pass
        if last_exc:
            raise last_exc
        raise RuntimeError("unknown_http_error")

    async def get_orders_history(
        self,
        limit: int = 25,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> list[OrderHistoryItem]:
        """
        Hämtar orderhistorik från Bitfinex.

        Args:
            limit: Maximalt antal ordrar att hämta
            start_time: Starttid i millisekunder sedan epoch
            end_time: Sluttid i millisekunder sedan epoch

        Returns:
            Lista med OrderHistoryItem-objekt
        """
        try:
            endpoint = "auth/r/orders/hist"

            # Skapa payload med filter
            payload = {}
            if limit:
                payload["limit"] = limit
            if start_time:
                payload["start"] = start_time
            if end_time:
                payload["end"] = end_time

            logger.info(f"🌐 REST API: Hämtar orderhistorik från {self.base_url}/{endpoint}")
            response = await self._signed_post_with_retry(endpoint, payload)
            orders_data = response.json()
            logger.info(f"✅ REST API: Hämtade {len(orders_data)} historiska ordrar")

            orders = [OrderHistoryItem.from_bitfinex_data(order) for order in orders_data]
            return orders

        except Exception as e:
            logger.error(f"Fel vid hämtning av orderhistorik: {e}")
            raise

    async def get_order_trades(self, order_id: int) -> list[TradeItem]:
        """
        Hämtar alla trades för en specifik order.

        Args:
            order_id: ID för ordern

        Returns:
            Lista med TradeItem-objekt
        """
        try:
            endpoint = f"auth/r/order/{order_id}/trades"
            logger.info(f"🌐 REST API: Hämtar trades för order {order_id}")
            response = await self._signed_post_with_retry(endpoint, {})
            trades_data = response.json()
            logger.info(f"✅ REST API: Hämtade {len(trades_data)} trades för order {order_id}")

            trades = [TradeItem.from_bitfinex_data(trade) for trade in trades_data]
            return trades

        except Exception as e:
            logger.error(f"Fel vid hämtning av trades för order {order_id}: {e}")
            raise

    async def get_trades_history(self, symbol: str | None = None, limit: int = 25) -> list[TradeItem]:
        """
        Hämtar handelshistorik från Bitfinex.

        Args:
            symbol: Handelssymbol (t.ex. "tBTCUSD") eller None för alla symboler
            limit: Maximalt antal trades att hämta

        Returns:
            Lista med TradeItem-objekt
        """
        try:
            endpoint = "auth/r/trades/hist"
            if symbol:
                endpoint = f"auth/r/trades/{symbol}/hist"

            payload = {"limit": limit} if limit else {}
            logger.info(f"🌐 REST API: Hämtar handelshistorik från {self.base_url}/{endpoint}")
            response = await self._signed_post_with_retry(endpoint, payload)
            trades_data = response.json()
            logger.info(f"✅ REST API: Hämtade {len(trades_data)} historiska trades")

            trades = [TradeItem.from_bitfinex_data(trade) for trade in trades_data]
            return trades

        except Exception as e:
            logger.error(f"Fel vid hämtning av handelshistorik: {e}")
            raise

    async def get_ledgers(self, currency: str | None = None, limit: int = 25) -> list[LedgerEntry]:
        """
        Hämtar ledger-poster från Bitfinex.

        Args:
            currency: Valutakod (t.ex. "BTC", "USD") eller None för alla valutor
            limit: Maximalt antal poster att hämta

        Returns:
            Lista med LedgerEntry-objekt
        """
        try:
            endpoint = "auth/r/ledgers/hist"
            if currency:
                endpoint = f"auth/r/ledgers/{currency}/hist"

            payload = {"limit": limit} if limit else {}
            logger.info(f"🌐 REST API: Hämtar ledger från {self.base_url}/{endpoint}")
            response = await self._signed_post_with_retry(endpoint, payload)
            ledgers_data = response.json()
            logger.info(f"✅ REST API: Hämtade {len(ledgers_data)} ledger-poster")

            ledgers = [LedgerEntry.from_bitfinex_data(ledger) for ledger in ledgers_data]
            return ledgers

        except Exception as e:
            logger.error(f"Fel vid hämtning av ledger: {e}")
            raise


# Skapa en global instans av OrderHistoryService
order_history_service = OrderHistoryService()


# Exportera funktioner för enkel användning
async def get_orders_history(
    limit: int = 25, start_time: int | None = None, end_time: int | None = None
) -> list[OrderHistoryItem]:
    return await order_history_service.get_orders_history(limit, start_time, end_time)


async def get_order_trades(order_id: int) -> list[TradeItem]:
    return await order_history_service.get_order_trades(order_id)


async def get_trades_history(symbol: str | None = None, limit: int = 25) -> list[TradeItem]:
    return await order_history_service.get_trades_history(symbol, limit)


async def get_ledgers(currency: str | None = None, limit: int = 25) -> list[LedgerEntry]:
    return await order_history_service.get_ledgers(currency, limit)


# Exempel på användning
if __name__ == "__main__":

    async def main():
        try:
            # Hämta senaste 10 ordrar
            orders = await get_orders_history(10)
            print(f"Senaste {len(orders)} ordrar:")
            for order in orders:
                print(f"  {order.id}: {order.symbol} {order.type} {order.amount} @ {order.price} ({order.status})")

            # Om det finns ordrar, hämta trades för den första
            if orders:
                trades = await get_order_trades(orders[0].id)
                print(f"\nTrades för order {orders[0].id}:")
                for trade in trades:
                    print(f"  {trade.id}: {trade.amount} @ {trade.price} (Fee: {trade.fee} {trade.fee_currency})")

            # Hämta senaste 5 ledger-poster för USD
            ledgers = await get_ledgers("USD", 5)
            print(f"\nSenaste {len(ledgers)} ledger-poster för USD:")
            for ledger in ledgers:
                print(f"  {ledger.id}: {ledger.amount} {ledger.currency} - {ledger.description}")

        except Exception as e:
            print(f"Fel: {e}")

    asyncio.run(main())
