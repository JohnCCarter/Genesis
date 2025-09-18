"""
Margin Service - TradingBot Backend

Denna modul hanterar margin-information från Bitfinex API.
Inkluderar funktioner för att hämta margin-status och marginhandelsinformation.
"""

from typing import Any

import httpx
from pydantic import BaseModel

from config.settings import settings
from services.exchange_client import get_exchange_client
from services.symbols import SymbolService
from services.bitfinex_websocket import bitfinex_ws
from utils.bitfinex_rate_limiter import get_bitfinex_rate_limiter
from utils.logger import get_logger

logger = get_logger(__name__)


class MarginInfo(BaseModel):
    """Modell för margin-information."""

    margin_balance: float
    unrealized_pl: float
    unrealized_swap: float
    net_value: float
    required_margin: float
    leverage: float | None = None
    margin_limits: list[dict[str, Any]] = []

    @classmethod
    def from_bitfinex_data(cls, data: list) -> "MarginInfo":
        """Skapar ett MarginInfo-objekt från Bitfinex API-data."""
        if len(data) < 5:
            raise ValueError(f"Ogiltig margin-data: {data}")

        # Beräkna leverage från margin_balance och net_value om det finns
        leverage = None
        if data[0] > 0 and data[3] > 0:
            leverage = data[3] / data[0]

        return cls(
            margin_balance=float(data[0]),
            unrealized_pl=float(data[1]),
            unrealized_swap=float(data[2]),
            net_value=float(data[3]),
            required_margin=float(data[4]),
            leverage=leverage,
            margin_limits=(data[5] if len(data) > 5 and isinstance(data[5], list) else []),
        )


class MarginLimitInfo(BaseModel):
    """Modell för margin-begränsningar för ett handelssymbol."""

    on_pair: str
    initial_margin: float
    tradable_balance: float
    margin_requirements: float

    @classmethod
    def from_bitfinex_data(cls, data: dict[str, Any]) -> "MarginLimitInfo":
        """Skapar ett MarginLimitInfo-objekt från Bitfinex API-data."""
        return cls(
            on_pair=data.get("on_pair", ""),
            initial_margin=float(data.get("initial_margin", 0)),
            tradable_balance=float(data.get("tradable_balance", 0)),
            margin_requirements=float(data.get("margin_requirements", 0)),
        )


class MarginService:
    """Service för att hämta och hantera margin-information från Bitfinex."""

    def __init__(self):
        self.settings = settings
        self.base_url = getattr(self.settings, "BITFINEX_AUTH_API_URL", None) or self.settings.BITFINEX_API_URL
        self.rate_limiter = get_bitfinex_rate_limiter()
        # OPTIMERING: In-memory cache för margin-status per symbol
        self._margin_status_cache = {}
        self._margin_status_cache_ttl = 60  # 1 minut TTL

    def _convert_v1_to_v2_format(self, v1_data: dict[str, Any]) -> list[Any]:
        """
        Konverterar margin info från v1 API format till v2 API format.

        Args:
            v1_data: Data från v1 API

        Returns:
            List med margin info i v2 API format
        """
        # v1 API returnerar ett objekt med margin_balance, unrealized_pl, etc.
        # v2 API förväntas returnera en lista med värden
        try:
            # Extrahera de viktigaste värdena från v1 svaret
            margin_balance = v1_data.get("margin_balance", 0)
            unrealized_pl = v1_data.get("unrealized_pl", 0)
            unrealized_swap = v1_data.get("unrealized_swap", 0)
            net_value = v1_data.get("net_value", 0)
            required_margin = v1_data.get("required_margin", 0)

            # Skapa v2 API format (lista med värden)
            v2_format = [
                margin_balance,
                unrealized_pl,
                unrealized_swap,
                net_value,
                required_margin,
            ]

            # Lägg till margin_limits om det finns
            if "margin_limits" in v1_data and isinstance(v1_data["margin_limits"], list):
                v2_format.append(v1_data["margin_limits"])

            return v2_format
        except Exception as e:
            logger.error(f"Fel vid konvertering av v1 margin data: {e}")
            # Returnera en grundläggande struktur om konverteringen misslyckas
            return [0, 0, 0, 0, 0]

    async def get_margin_info(self) -> MarginInfo:
        """
        Hämtar margin-information från Bitfinex.

        Returns:
            MarginInfo-objekt
        """
        try:
            # Försök först med v2 API endpoint (base)
            endpoint = "auth/r/info/margin/base"
            ec = get_exchange_client()
            response = await ec.signed_request(method="post", endpoint=endpoint, body={}, timeout=None)
            response.raise_for_status()
            # v2 base svar: [ 'base', [USER_PL, USER_SWAPS, MARGIN_BALANCE, MARGIN_NET, MARGIN_MIN] ]
            raw = response.json()
            if isinstance(raw, list) and len(raw) >= 2 and isinstance(raw[1], list):
                data = raw[1]
            else:
                data = [0, 0, 0, 0, 0]
            margin_data = [data[2], data[0], data[1], data[3], data[4]]
            logger.info("✅ REST API: Hämtade margin-information (base) från v2 API")
            # Transport‑CB hanteras av AdvancedRateLimiter; explicit success-märkning borttagen
        except httpx.HTTPStatusError as e:
            # Om v2 API misslyckas, försök med v1 API endpoint
            if e.response.status_code in (404, 400, 500):
                logger.warning(
                    "⚠️ v2 API misslyckades (%s), försöker med v1 API",
                    e.response.status_code,
                )
                try:
                    v1_endpoint = "margin_infos"
                    ec = get_exchange_client()
                    v1_response = await ec.signed_request(method="post", endpoint=v1_endpoint, body={}, v1=True)
                    v1_response.raise_for_status()
                    v1_data = v1_response.json()
                    margin_data = self._convert_v1_to_v2_format(v1_data)
                    logger.info("✅ REST API: Hämtade margin-information från v1 API")
                    # Transport‑CB hanteras av AdvancedRateLimiter
                except Exception as e1:
                    logger.error(f"❌ v1 margin API misslyckades: {e1}")
                    # Fallback – returnera neutral struktur så flödet inte kraschar
            else:
                # Okänt fel – fallback med neutral struktur
                logger.error(f"❌ v2 margin API fel: {e}")
                margin_data = [0, 0, 0, 0, 0]
                # Transport‑CB hanteras av AdvancedRateLimiter

        margin_info = MarginInfo.from_bitfinex_data(margin_data)
        return margin_info

    async def get_margin_limits(self) -> list[MarginLimitInfo]:
        """
        Hämtar margin-begränsningar för alla handelssymboler.

        Returns:
            Lista med MarginLimitInfo-objekt
        """
        try:
            margin_info = await self.get_margin_info()

            margin_limits = []
            for limit_data in margin_info.margin_limits:
                if isinstance(limit_data, dict):
                    margin_limits.append(MarginLimitInfo.from_bitfinex_data(limit_data))

            return margin_limits

        except Exception as e:
            logger.error(f"Fel vid hämtning av margin-begränsningar: {e}")
            raise

    async def get_margin_limit_by_pair(self, pair: str) -> MarginLimitInfo | None:
        """
        Hämtar margin-begränsningar för ett specifikt handelssymbol.

        Args:
            pair: Handelssymbol (t.ex. "tBTCUSD")

        Returns:
            MarginLimitInfo-objekt eller None om symbolen inte hittas
        """
        # 1) Försök via redan hämtade limits från base (om de finns)
        try:
            margin_limits = await self.get_margin_limits()
            for limit in margin_limits:
                if limit.on_pair.lower() == pair.lower():
                    return limit
        except Exception:
            pass

        # 2) Direkt v2‑endpoint för symbol: auth/r/info/margin/sym:tPAIR
        try:
            eff = pair
            if not eff.startswith("t"):
                eff = f"t{eff}"
            key = f"sym:{eff}"
            endpoint = f"auth/r/info/margin/{key}"
            ec = get_exchange_client()
            resp = await ec.signed_request(method="post", endpoint=endpoint, body={})
            resp.raise_for_status()
            raw = resp.json()
            # Förväntat format: [ 'sym', 'tPAIR', [TRADABLE, GROSS, BUY, SELL, ...] ]
            if isinstance(raw, list) and len(raw) >= 3 and str(raw[0]).lower() == "sym" and isinstance(raw[2], list):
                arr = raw[2]
                tradable = float(arr[0]) if len(arr) > 0 and arr[0] is not None else 0.0
                # initial_margin/margin_requirements okända här; sätt 0 som placeholder
                return MarginLimitInfo(
                    on_pair=eff,
                    initial_margin=0.0,
                    tradable_balance=tradable,
                    margin_requirements=0.0,
                )
        except Exception as e:
            logger.debug("Margin sym v2 misslyckades: %s", e)

        return None

    async def get_leverage(self) -> float:
        """
        Hämtar nuvarande hävstång (leverage).

        Returns:
            Hävstångsvärde (1.0 betyder ingen hävstång)
        """
        margin_info = await self.get_margin_info()

        if margin_info.leverage is not None:
            return margin_info.leverage

        # Fallback-beräkning om leverage inte finns i API-svaret
        if margin_info.margin_balance > 0 and margin_info.net_value > 0:
            return margin_info.net_value / margin_info.margin_balance

        return 1.0  # Standardvärde om vi inte kan beräkna

    async def get_margin_status(self) -> dict[str, Any]:
        """
        Hämtar en sammanfattning av margin-status.

        Returns:
            Dict med margin-statusvärden och indikatorer
        """
        margin_info = await self.get_margin_info()

        # Beräkna margin-användning i procent
        margin_usage = 0.0
        if margin_info.required_margin > 0 and margin_info.net_value > 0:
            margin_usage = (margin_info.required_margin / margin_info.net_value) * 100

        # Beräkna margin-nivå (hur många gånger required_margin täcks av net_value)
        margin_level = 0.0
        if margin_info.required_margin > 0:
            margin_level = margin_info.net_value / margin_info.required_margin

        return {
            "margin_balance": margin_info.margin_balance,
            "net_value": margin_info.net_value,
            "unrealized_pl": margin_info.unrealized_pl,
            "required_margin": margin_info.required_margin,
            "margin_usage_percent": margin_usage,
            "margin_level": margin_level,
            "leverage": await self.get_leverage(),
            "status": ("healthy" if margin_level >= 2.0 else "warning" if margin_level >= 1.5 else "danger"),
        }

    async def get_symbol_margin_status(self, symbol: str) -> dict[str, Any]:
        """
        Per‑symbol marginstatus. WS (miu:sym) i första hand, REST margin_limits som fallback.
        Returnerar nycklar: { source, tradable, buy, sell } (buy/sell endast om WS finns).
        """
        try:
            # Normalisera/resolve symbol
            eff = symbol
            try:
                svc = SymbolService()
                await svc.refresh()
                eff = svc.resolve(symbol)
            except Exception:
                pass

            # WS‑först: läs miu:sym arr om tillgängligt
            try:
                arr = (bitfinex_ws.margin_sym or {}).get(eff)
                if isinstance(arr, list) and arr:
                    # Försök tolka fält: [tradable, gross, buy, sell, ...]
                    tradable = float(arr[0]) if len(arr) >= 1 and arr[0] is not None else None
                    buy = float(arr[2]) if len(arr) >= 3 and arr[2] is not None else None
                    sell = float(arr[3]) if len(arr) >= 4 and arr[3] is not None else None
                    return {
                        "symbol": eff,
                        "source": "ws",
                        "tradable": tradable,
                        "buy": buy,
                        "sell": sell,
                    }
            except Exception:
                pass

            # REST fallback: margin_limits
            try:
                limit = await self.get_margin_limit_by_pair(eff)
                if limit:
                    return {
                        "symbol": eff,
                        "source": "rest",
                        "tradable": float(limit.tradable_balance),
                        "buy": None,
                        "sell": None,
                    }
            except Exception:
                pass

            # Sist: tom struktur
            return {
                "symbol": eff,
                "source": "none",
                "tradable": None,
                "buy": None,
                "sell": None,
            }
        except Exception as e:
            logger.error(f"Fel vid symbol margin status: {e}")
            return {"symbol": symbol, "source": "error"}

    async def get_symbol_margin_status_batch(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        """
        OPTIMERAD: Batch-hämtning av margin-status för flera symboler.
        Minskar API-anrop genom att hämta all data på en gång.

        Args:
            symbols: Lista med symboler att hämta margin-status för

        Returns:
            Dict med symbol -> margin-status mapping
        """
        try:
            import time

            now = time.time()
            results = {}

            # 1. Kontrollera cache först
            symbols_to_fetch = []
            for symbol in symbols:
                eff = symbol
                try:
                    from services.symbols import SymbolService

                    svc = SymbolService()
                    await svc.refresh()
                    eff = svc.resolve(symbol)
                except Exception:
                    pass

                cache_key = f"margin_status_{eff}"
                cached = self._margin_status_cache.get(cache_key)
                if cached and (now - cached["timestamp"]) < self._margin_status_cache_ttl:
                    logger.debug(f"📋 Använder cached margin-status för {eff}")
                    results[symbol] = cached["data"]
                else:
                    symbols_to_fetch.append((symbol, eff))

            if not symbols_to_fetch:
                return results

            # 2. Batch-hämta från WebSocket först
            ws_results = {}
            try:
                from services.bitfinex_websocket import bitfinex_ws

                for symbol, eff in symbols_to_fetch:
                    arr = (bitfinex_ws.margin_sym or {}).get(eff)
                    if isinstance(arr, list) and arr:
                        # Försök tolka fält: [tradable, gross, buy, sell, ...]
                        tradable = float(arr[0]) if len(arr) >= 1 and arr[0] is not None else None
                        buy = float(arr[2]) if len(arr) >= 3 and arr[2] is not None else None
                        sell = float(arr[3]) if len(arr) >= 4 and arr[3] is not None else None

                        result = {
                            "symbol": eff,
                            "source": "ws",
                            "tradable": tradable,
                            "buy": buy,
                            "sell": sell,
                        }
                        ws_results[symbol] = result

                        # Spara i cache
                        cache_key = f"margin_status_{eff}"
                        self._margin_status_cache[cache_key] = {
                            "timestamp": now,
                            "data": result,
                        }
            except Exception as e:
                logger.warning(f"⚠️ WS batch margin-status misslyckades: {e}")

            # 3. REST fallback för symboler som inte fick WS-data
            rest_symbols = [(s, eff) for s, eff in symbols_to_fetch if s not in ws_results]
            if rest_symbols:
                logger.info(f"🔄 Batch-hämtar margin-status för {len(rest_symbols)} symboler via REST")

                # Batch-hämta margin limits
                try:
                    margin_limits = await self.get_margin_limits()
                    limits_by_pair = {limit.on_pair.lower(): limit for limit in margin_limits}

                    for symbol, eff in rest_symbols:
                        limit = limits_by_pair.get(eff.lower())
                        if limit:
                            result = {
                                "symbol": eff,
                                "source": "rest",
                                "tradable": float(limit.tradable_balance),
                                "buy": None,
                                "sell": None,
                            }
                        else:
                            result = {
                                "symbol": eff,
                                "source": "none",
                                "tradable": None,
                                "buy": None,
                                "sell": None,
                            }

                        results[symbol] = result

                        # Spara i cache
                        cache_key = f"margin_status_{eff}"
                        self._margin_status_cache[cache_key] = {
                            "timestamp": now,
                            "data": result,
                        }

                except Exception as e:
                    logger.warning(f"⚠️ REST batch margin-status misslyckades: {e}")
                    # Fallback till individuella anrop
                    for symbol, eff in rest_symbols:
                        try:
                            result = await self.get_symbol_margin_status(symbol)
                            results[symbol] = result
                        except Exception:
                            results[symbol] = {
                                "symbol": eff,
                                "source": "error",
                                "tradable": None,
                                "buy": None,
                                "sell": None,
                            }

            # Lägg till WS-resultat
            results.update(ws_results)

            logger.info(f"✅ Batch margin-status klar: {len(results)}/{len(symbols)} symboler")
            return results

        except Exception as e:
            logger.error(f"❌ Batch margin-status fel: {e}")
            # Fallback till individuella anrop
            results = {}
            for symbol in symbols:
                try:
                    result = await self.get_symbol_margin_status(symbol)
                    results[symbol] = result
                except Exception:
                    results[symbol] = {
                        "symbol": symbol,
                        "source": "error",
                        "tradable": None,
                        "buy": None,
                        "sell": None,
                    }
            return results


# Skapa en global instans av MarginService
margin_service = MarginService()


# Exportera funktioner för enkel användning
async def get_margin_info() -> MarginInfo:
    return await margin_service.get_margin_info()


async def get_margin_limits() -> list[MarginLimitInfo]:
    return await margin_service.get_margin_limits()


async def get_margin_limit_by_pair(pair: str) -> MarginLimitInfo | None:
    return await margin_service.get_margin_limit_by_pair(pair)


async def get_leverage() -> float:
    return await margin_service.get_leverage()


async def get_margin_status() -> dict[str, Any]:
    return await margin_service.get_margin_status()
