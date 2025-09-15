"""
Wallet Service - TradingBot Backend

Denna modul hanterar plånboksinformation från Bitfinex API.
Inkluderar funktioner för att hämta plånbokssaldon och hantera plånbokstransaktioner.
"""

import asyncio
import time

import httpx
from services.exchange_client import get_exchange_client
from pydantic import BaseModel

from config.settings import Settings
from rest.auth import build_auth_headers
from services.metrics import record_http_result
from utils.advanced_rate_limiter import get_advanced_rate_limiter
from utils.logger import get_logger
from utils.private_concurrency import get_private_rest_semaphore

logger = get_logger(__name__)


class WalletBalance(BaseModel):
    """Modell för plånbokssaldo."""

    wallet_type: str  # "exchange", "margin", "funding"
    currency: str
    balance: float
    unsettled_interest: float = 0.0
    available_balance: float | None = None

    @classmethod
    def from_bitfinex_data(cls, data: list) -> "WalletBalance":
        """Skapar en WalletBalance från Bitfinex API-data."""
        if len(data) < 4:
            raise ValueError(f"Ogiltig plånboksdata: {data}")

        return cls(
            wallet_type=data[0],
            currency=data[1],
            balance=float(data[2]),
            unsettled_interest=float(data[3]) if len(data) > 3 else 0.0,
            available_balance=float(data[4]) if len(data) > 4 else None,
        )


class WalletService:
    """Service för att hämta och hantera plånboksinformation från Bitfinex."""

    def __init__(self):
        self.settings = Settings()
        self.base_url = getattr(self.settings, "BITFINEX_AUTH_API_URL", None) or self.settings.BITFINEX_API_URL
        self.rate_limiter = get_advanced_rate_limiter()
        # Concurrency cap för privata REST
        # Global semafor för alla privata REST-klasser
        self._sem = get_private_rest_semaphore()

    async def get_wallets(self) -> list[WalletBalance]:
        """
        Hämtar alla plånböcker från Bitfinex.

        Returns:
            Lista med WalletBalance-objekt
        """
        try:
            # Safeguard: saknade nycklar → tom lista istället för 500
            if not (self.settings.BITFINEX_API_KEY and self.settings.BITFINEX_API_SECRET):
                logger.info("BITFINEX_API_KEY/SECRET saknas – returnerar tom wallet-lista")
                return []
            endpoint = "auth/r/wallets"

            # Circuit breaker: respektera ev. cooldown + rate limiter
            try:
                if hasattr(self.rate_limiter, "can_request") and not self.rate_limiter.can_request(endpoint):
                    wait = float(self.rate_limiter.time_until_open(endpoint))
                    logger.warning(f"CB: {endpoint} stängd i {wait:.1f}s")
                    await asyncio.sleep(max(0.0, wait))
            except Exception:
                pass
            try:
                await self.rate_limiter.wait_if_needed(endpoint)
            except Exception:
                pass

            logger.info(f"🌐 REST API: Hämtar plånböcker från {self.base_url}/{endpoint}")
            _t0 = time.perf_counter()
            async with self._sem:
                try:
                    ec = get_exchange_client()
                    response = await ec.signed_request(method="post", endpoint=endpoint, body=None, timeout=15.0)
                except Exception:
                    async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
                        headers = build_auth_headers(endpoint)
                        response = await client.post(f"{self.base_url}/{endpoint}", headers=headers)
                _t1 = time.perf_counter()
                try:
                    record_http_result(
                        path=f"/{endpoint}",
                        method="POST",
                        status_code=int(response.status_code),
                        duration_ms=int((_t1 - _t0) * 1000),
                        _retry_after=response.headers.get("Retry-After"),
                    )
                    if response.status_code in (429, 500, 502, 503, 504):
                        ra = response.headers.get("Retry-After")
                        logger.warning(
                            "HTTP %s %s Retry-After=%s",
                            response.status_code,
                            endpoint,
                            ra if ra is not None else "-",
                        )
                except Exception:
                    pass

                # Kontrollera nonce-fel specifikt (10114: "nonce: small") och bumpa + engångs‑retry
                if response.status_code == 500:
                    try:
                        error_data = response.json()
                        if (
                            isinstance(error_data, list)
                            and len(error_data) >= 3
                            and "nonce" in str(error_data[2]).lower()
                        ):
                            logger.error(f"🚨 Nonce-fel i wallets: {error_data}")
                            try:
                                # Nonce bump hanteras centralt i ExchangeClient.signed_request
                                # Returnera svar för vidare hantering
                                return []
                            except Exception:
                                pass
                    except Exception:
                        pass

                # Hantera server busy
                if response.status_code in (429, 500, 502, 503, 504):
                    try:
                        if (
                            "server busy" in (response.text or "").lower() or response.status_code in (429, 503)
                        ) and hasattr(self.rate_limiter, "note_failure"):
                            cooldown = self.rate_limiter.note_failure(
                                endpoint,
                                int(response.status_code),
                                response.headers.get("Retry-After"),
                            )
                            logger.warning(f"CB öppnad för {endpoint} i {cooldown:.1f}s")
                            # Transport‑CB hanteras av AdvancedRateLimiter
                        await self.rate_limiter.handle_server_busy(endpoint)
                    except Exception:
                        pass
                    logger.warning(f"Bitfinex server busy för wallets (status {response.status_code})")
                    return []

                try:
                    response.raise_for_status()
                    # Återställ räknare och CB vid framgång
                    try:
                        self.rate_limiter.reset_server_busy_count()
                    except Exception:
                        pass
                    try:
                        if hasattr(self.rate_limiter, "note_success"):
                            self.rate_limiter.note_success(endpoint)
                    except Exception:
                        pass
                    # Transport‑CB hanteras av AdvancedRateLimiter
                except httpx.HTTPStatusError as he:
                    status = he.response.status_code if he.response is not None else "?"
                    logger.warning(f"Bitfinex svarade {status} vid hämtning av wallets – returnerar tom lista")
                    return []

                wallets_data = response.json()
                logger.info(f"✅ REST API: Hämtade {len(wallets_data)} plånböcker")

                wallets = [WalletBalance.from_bitfinex_data(wallet) for wallet in wallets_data]
                return wallets

        except Exception as e:
            logger.error(f"Fel vid hämtning av plånböcker: {e}")
            return []

    async def get_wallet_by_type_and_currency(self, wallet_type: str, currency: str) -> WalletBalance | None:
        """
        Hämtar en specifik plånbok baserat på typ och valuta.

        Args:
            wallet_type: Plånbokstyp ("exchange", "margin", "funding")
            currency: Valutakod (t.ex. "BTC", "USD")

        Returns:
            WalletBalance-objekt eller None om plånboken inte hittas
        """
        wallets = await self.get_wallets()

        for wallet in wallets:
            if wallet.wallet_type.lower() == wallet_type.lower() and wallet.currency.lower() == currency.lower():
                return wallet

        return None

    async def get_exchange_wallets(self) -> list[WalletBalance]:
        """
        Hämtar alla exchange-plånböcker.

        Returns:
            Lista med WalletBalance-objekt för exchange-plånböcker
        """
        wallets = await self.get_wallets()
        return [wallet for wallet in wallets if wallet.wallet_type.lower() == "exchange"]

    async def get_margin_wallets(self) -> list[WalletBalance]:
        """
        Hämtar alla margin-plånböcker.

        Returns:
            Lista med WalletBalance-objekt för margin-plånböcker
        """
        wallets = await self.get_wallets()
        return [wallet for wallet in wallets if wallet.wallet_type.lower() == "margin"]

    async def get_funding_wallets(self) -> list[WalletBalance]:
        """
        Hämtar alla funding-plånböcker.

        Returns:
            Lista med WalletBalance-objekt för funding-plånböcker
        """
        wallets = await self.get_wallets()
        return [wallet for wallet in wallets if wallet.wallet_type.lower() == "funding"]

    async def get_total_balance_usd(self) -> float:
        """
        Beräknar det totala saldot i USD över alla plånböcker.
        Detta är en förenklad implementation som antar att USD-plånböcker har direkt USD-värde
        och att andra valutor skulle behöva konverteras (inte implementerat här).

        Returns:
            Totalt saldo i USD
        """
        wallets = await self.get_wallets()
        usd_wallets = [wallet for wallet in wallets if wallet.currency.upper() == "USD"]

        total_usd = sum(wallet.balance for wallet in usd_wallets)
        return total_usd


# Skapa en global instans av WalletService
wallet_service = WalletService()


# Exportera funktioner för enkel användning
async def get_wallets() -> list[WalletBalance]:
    return await wallet_service.get_wallets()


async def get_wallet_by_type_and_currency(wallet_type: str, currency: str) -> WalletBalance | None:
    return await wallet_service.get_wallet_by_type_and_currency(wallet_type, currency)


async def get_exchange_wallets() -> list[WalletBalance]:
    return await wallet_service.get_exchange_wallets()


async def get_margin_wallets() -> list[WalletBalance]:
    return await wallet_service.get_margin_wallets()


async def get_funding_wallets() -> list[WalletBalance]:
    return await wallet_service.get_funding_wallets()


async def get_total_balance_usd() -> float:
    return await wallet_service.get_total_balance_usd()
