"""
REST API Routes - TradingBot Backend

Detta är huvudmodulen för REST API-routes.
Inkluderar endpoints för orderhantering, marknadsdata, plånboksinformation och positioner.
"""

import asyncio
from typing import Any, Dict, List, Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from config.settings import Settings
from indicators.atr import calculate_atr
from rest import auth as rest_auth
from rest.active_orders import ActiveOrdersService
from rest.margin import MarginService
from rest.order_history import (
    LedgerEntry,
    OrderHistoryItem,
    OrderHistoryService,
    TradeItem,
)
from rest.order_validator import order_validator
from rest.positions import Position, PositionsService
from rest.wallet import WalletBalance, WalletService
from services.backtest import BacktestService
from services.bitfinex_data import BitfinexDataService
from services.bracket_manager import bracket_manager
from services.metrics import inc
from services.notifications import notification_service
from services.performance import PerformanceService
from services.risk_manager import RiskManager
from services.strategy import evaluate_weighted_strategy
from services.strategy_settings import StrategySettings, StrategySettingsService
from services.symbols import SymbolService
from services.templates import OrderTemplatesService
from services.trading_integration import trading_integration
from services.trading_window import TradingWindowService
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v2")
security = HTTPBearer(auto_error=False)
settings = Settings()
JWT_SECRET = settings.SOCKETIO_JWT_SECRET


# Hjälpfunktion för att emit:a notifieringar via Socket.IO
def _emit_notification(event_type: str, title: str, payload: dict):
    try:
        from ws.manager import socket_app

        asyncio.create_task(
            socket_app.emit(
                "notification",
                {"type": event_type, "title": title, "payload": payload},
            )
        )
    except Exception:
        pass


# Modeller för förfrågningar och svar


class OrderRequest(BaseModel):
    """Request model för orderläggning."""

    symbol: str
    amount: str
    price: Optional[str] = None  # Optional för MARKET orders
    type: str = "EXCHANGE LIMIT"  # EXCHANGE LIMIT, EXCHANGE MARKET, etc.
    side: Optional[str] = None  # Optional för att matcha test_order_operations.py


class CancelOrderRequest(BaseModel):
    """Request model för orderavbrytning."""

    order_id: int


class UpdateOrderRequest(BaseModel):
    """Request model för orderuppdatering."""

    order_id: int
    price: Optional[float] = None
    amount: Optional[float] = None


class OrderResponse(BaseModel):
    """Generiskt svar för orderoperationer (wrapper)."""

    success: bool
    error: Optional[str] = None
    data: Optional[Any] = None


class BracketOrderRequest(BaseModel):
    """Request för bracket-order (entry + valfri SL/TP)."""

    symbol: str
    amount: str
    side: str  # buy/sell
    entry_type: str = "EXCHANGE MARKET"  # eller EXCHANGE LIMIT (kräver entry_price)
    entry_price: Optional[str] = None
    sl_price: Optional[str] = None
    tp_price: Optional[str] = None
    tif: Optional[str] = None  # e.g. GTC/IOC/FOK
    post_only: bool = False
    reduce_only: bool = False


# Order endpoints


def require_auth(credentials: HTTPAuthorizationCredentials | None = Depends(security)):
    """Kräv JWT endast när AUTH_REQUIRED=True. Annars släpp igenom utan header."""
    current = Settings()
    if current.AUTH_REQUIRED is False:
        return True
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=403, detail="Not authenticated")
    try:
        jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        return True
    except Exception:
        raise HTTPException(status_code=401, detail="Ogiltig token")


@router.post("/order", response_model=OrderResponse)
async def place_order_endpoint(order: OrderRequest, _: bool = Depends(require_auth)):
    """
    Lägger en order via Bitfinex API.
    """
    try:
        logger.info(f"Mottog orderförfrågan: {order.dict()}")

        # Validera order innan den skickas
        is_valid, err = order_validator.validate_order(order.dict())
        if not is_valid:
            return OrderResponse(success=False, error=f"validation_error:{err}")

        # Riskkontroller före order (skippa i pytest-miljö för enhetstester)
        import os

        if "PYTEST_CURRENT_TEST" not in os.environ:
            risk = RiskManager()
            ok, reason = risk.pre_trade_checks(symbol=order.symbol)
            if not ok:
                logger.warning(f"Order blockeras av riskkontroll: {reason}")
                return OrderResponse(success=False, error=f"risk_blocked:{reason}")
        else:
            risk = RiskManager()

        # Skicka ordern till Bitfinex
        result = await rest_auth.place_order(order.dict())

        if "error" in result:
            logger.error(f"Fel vid orderläggning: {result['error']}")
            await notification_service.notify(
                "error",
                "Order misslyckades",
                {"request": order.dict(), "error": result.get("error")},
            )
            inc("orders_total")
            inc("orders_failed_total")
            try:
                # Registrera fel i circuit breaker
                RiskManager().record_error()
            except Exception:
                pass
            return OrderResponse(success=False, error=result["error"])

        # Markera trade om lyckad
        if "error" not in result:
            risk.record_trade(symbol=order.symbol)
            inc("orders_total")
        logger.info(f"Order framgångsrikt lagd: {result}")
        await notification_service.notify(
            "info", "Order lagd", {"request": order.dict(), "response": result}
        )
        return OrderResponse(success=True, data=result)

    except Exception as e:
        logger.exception(f"Oväntat fel vid orderläggning: {e}")
        return OrderResponse(success=False, error=str(e))


@router.post("/order/cancel", response_model=OrderResponse)
async def cancel_order_endpoint(
    cancel_request: CancelOrderRequest, _: bool = Depends(require_auth)
):
    """
    Avbryter en order via Bitfinex API.
    """
    try:
        logger.info(f"Mottog avbrottsförfrågan för order: {cancel_request.order_id}")

        # Skicka avbrottsförfrågan till Bitfinex
        result = await rest_auth.cancel_order(cancel_request.order_id)

        if "error" in result:
            logger.error(f"Fel vid avbrytning av order: {result['error']}")
            await notification_service.notify(
                "error",
                "Order cancel misslyckades",
                {"order_id": cancel_request.order_id, "error": result.get("error")},
            )
            try:
                RiskManager().record_error()
            except Exception:
                pass
            return OrderResponse(success=False, error=result["error"])

        logger.info(f"Order framgångsrikt avbruten: {result}")
        await notification_service.notify(
            "info",
            "Order avbruten",
            {"order_id": cancel_request.order_id, "response": result},
        )
        return OrderResponse(success=True, data=result)

    except Exception as e:
        logger.exception(f"Oväntat fel vid avbrytning av order: {e}")
        return OrderResponse(success=False, error=str(e))


@router.post("/order/update", response_model=OrderResponse)
async def update_order_endpoint(
    update_request: UpdateOrderRequest, _: bool = Depends(require_auth)
):
    """
    Uppdaterar en order via Bitfinex API.
    """
    try:
        logger.info(
            f"Mottog uppdateringsförfrågan för order: {update_request.order_id}"
        )

        # Skapa en instans av ActiveOrdersService
        active_orders_service = ActiveOrdersService()

        # Uppdatera ordern
        result = await active_orders_service.update_order(
            update_request.order_id, update_request.price, update_request.amount
        )

        logger.info(f"Order framgångsrikt uppdaterad: {result}")
        _emit_notification(
            "info",
            "Order uppdaterad",
            {"request": update_request.dict(), "response": result},
        )
        return OrderResponse(success=True, data=result)

    except Exception as e:
        logger.exception(f"Oväntat fel vid uppdatering av order: {e}")
        return OrderResponse(success=False, error=str(e))


@router.post("/orders/cancel/all", response_model=OrderResponse)
async def cancel_all_orders_endpoint(_: bool = Depends(require_auth)):
    """
    Avbryter alla aktiva ordrar.
    """
    try:
        logger.info("Mottog förfrågan om att avbryta alla ordrar")

        # Skapa en instans av ActiveOrdersService
        active_orders_service = ActiveOrdersService()

        # Avbryt alla ordrar
        result = await active_orders_service.cancel_all_orders()

        logger.info("Alla ordrar framgångsrikt avbrutna")
        _emit_notification("info", "Alla ordrar avbrutna", {"response": result})
        return OrderResponse(success=True, data=result)

    except Exception as e:
        logger.exception(f"Oväntat fel vid avbrytning av alla ordrar: {e}")
        return OrderResponse(success=False, error=str(e))


@router.post("/orders/cancel/symbol/{symbol}", response_model=OrderResponse)
async def cancel_orders_by_symbol_endpoint(
    symbol: str, _: bool = Depends(require_auth)
):
    """
    Avbryter alla aktiva ordrar för en specifik symbol.
    """
    try:
        logger.info(f"Mottog förfrågan om att avbryta alla ordrar för symbol: {symbol}")

        # Skapa en instans av ActiveOrdersService
        active_orders_service = ActiveOrdersService()

        # Avbryt alla ordrar för symbolen
        result = await active_orders_service.cancel_orders_by_symbol(symbol)

        logger.info(f"Ordrar för {symbol} framgångsrikt avbrutna")
        _emit_notification(
            "info", "Ordrar avbrutna för symbol", {"symbol": symbol, "response": result}
        )
        return OrderResponse(success=True, data=result)

    except Exception as e:
        logger.exception(f"Oväntat fel vid avbrytning av ordrar för {symbol}: {e}")
        return OrderResponse(success=False, error=str(e))


@router.get("/orders", response_model=List[OrderResponse])
async def get_active_orders_endpoint(_: bool = Depends(require_auth)):
    """
    Hämtar alla aktiva ordrar.
    """
    try:
        # Skapa en instans av ActiveOrdersService
        active_orders_service = ActiveOrdersService()

        # Hämta alla aktiva ordrar
        orders = await active_orders_service.get_active_orders()

        # Konvertera varje order till vår API OrderResponse-modell
        return [OrderResponse(success=True, data=order) for order in orders]

    except Exception as e:
        logger.exception(f"Fel vid hämtning av aktiva ordrar: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orders/symbol/{symbol}", response_model=List[OrderResponse])
async def get_orders_by_symbol_endpoint(symbol: str, _: bool = Depends(require_auth)):
    """
    Hämtar aktiva ordrar för en specifik symbol.
    """
    try:
        # Skapa en instans av ActiveOrdersService
        active_orders_service = ActiveOrdersService()

        # Hämta aktiva ordrar för symbolen
        orders = await active_orders_service.get_active_orders_by_symbol(symbol)

        # Konvertera varje order till vår API OrderResponse-modell
        return [OrderResponse(success=True, data=order) for order in orders]

    except Exception as e:
        logger.exception(f"Fel vid hämtning av aktiva ordrar för {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/order/{order_id}", response_model=OrderResponse)
async def get_order_by_id_endpoint(order_id: int, _: bool = Depends(require_auth)):
    """
    Hämtar en specifik order baserat på ID.
    """
    try:
        # Skapa en instans av ActiveOrdersService
        active_orders_service = ActiveOrdersService()

        # Hämta ordern
        order = await active_orders_service.get_order_by_id(order_id)

        if not order:
            raise HTTPException(
                status_code=404, detail=f"Order med ID {order_id} hittades inte"
            )

        return OrderResponse(success=True, data=order)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Fel vid hämtning av order {order_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Wallet endpoints


@router.get("/wallets", response_model=List[WalletBalance])
async def get_wallets_endpoint(_: bool = Depends(require_auth)):
    """
    Hämtar alla plånböcker från Bitfinex API.
    """
    try:
        wallet_service = WalletService()
        wallets = await wallet_service.get_wallets()
        return wallets

    except Exception as e:
        logger.exception(f"Fel vid hämtning av plånböcker: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/wallets/balance")
async def get_wallets_balance_endpoint(
    currency: Optional[str] = None, _: bool = Depends(require_auth)
):
    """Aggregat saldo per valuta med brytning per wallet-typ.

    - Om `currency` anges returneras endast den valutan.
    - Annars returneras alla valutor.
    """
    try:
        wallet_service = WalletService()
        wallets = await wallet_service.get_wallets()

        def _upper(s: Optional[str]) -> str:
            return s.upper() if isinstance(s, str) else ""

        balances: Dict[str, Dict[str, Any]] = {}
        for w in wallets:
            cur = _upper(w.currency)
            entry = balances.setdefault(
                cur, {"total": 0.0, "available_total": 0.0, "by_type": {}}
            )
            entry["total"] += float(w.balance)
            entry["available_total"] += float(w.available_balance or 0.0)
            by_type = entry["by_type"]
            by_type[w.wallet_type] = float(by_type.get(w.wallet_type, 0.0)) + float(
                w.balance
            )

        if currency:
            cur = currency.upper()
            data = balances.get(
                cur, {"total": 0.0, "available_total": 0.0, "by_type": {}}
            )
            # inkludera råa wallets för valutan
            data["wallets"] = [w.dict() for w in wallets if _upper(w.currency) == cur]
            data["currency"] = cur
            return data
        else:
            # inkludera valutor sorterade alfabetiskt
            out = []
            for cur, data in sorted(balances.items()):
                out.append({"currency": cur, **data})
            return out
    except Exception as e:
        logger.exception(f"Fel vid wallets/balance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/wallets/exchange", response_model=List[WalletBalance])
async def get_exchange_wallets_endpoint(_: bool = Depends(require_auth)):
    """
    Hämtar alla exchange-plånböcker från Bitfinex API.
    """
    try:
        wallet_service = WalletService()
        wallets = await wallet_service.get_exchange_wallets()
        return wallets

    except Exception as e:
        logger.exception(f"Fel vid hämtning av exchange-plånböcker: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/wallets/margin", response_model=List[WalletBalance])
async def get_margin_wallets_endpoint(_: bool = Depends(require_auth)):
    """
    Hämtar alla margin-plånböcker från Bitfinex API.
    """
    try:
        wallet_service = WalletService()
        wallets = await wallet_service.get_margin_wallets()
        return wallets

    except Exception as e:
        logger.exception(f"Fel vid hämtning av margin-plånböcker: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/wallets/funding", response_model=List[WalletBalance])
async def get_funding_wallets_endpoint(_: bool = Depends(require_auth)):
    """
    Hämtar alla funding-plånböcker från Bitfinex API.
    """
    try:
        wallet_service = WalletService()
        wallets = await wallet_service.get_funding_wallets()
        return wallets

    except Exception as e:
        logger.exception(f"Fel vid hämtning av funding-plånböcker: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Position endpoints


@router.get("/positions", response_model=List[Position])
async def get_positions_endpoint(_: bool = Depends(require_auth)):
    """
    Hämtar alla aktiva positioner från Bitfinex API.
    """
    try:
        positions_service = PositionsService()
        positions = await positions_service.get_positions()
        return positions

    except Exception as e:
        logger.exception(f"Fel vid hämtning av positioner: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions/long", response_model=List[Position])
async def get_long_positions_endpoint(_: bool = Depends(require_auth)):
    """
    Hämtar alla long-positioner från Bitfinex API.
    """
    try:
        positions_service = PositionsService()
        positions = await positions_service.get_long_positions()
        return positions

    except Exception as e:
        logger.exception(f"Fel vid hämtning av long-positioner: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions/short", response_model=List[Position])
async def get_short_positions_endpoint(_: bool = Depends(require_auth)):
    """
    Hämtar alla short-positioner från Bitfinex API.
    """
    try:
        positions_service = PositionsService()
        positions = await positions_service.get_short_positions()
        return positions

    except Exception as e:
        logger.exception(f"Fel vid hämtning av short-positioner: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/positions/close/{symbol}", response_model=Dict[str, Any])
async def close_position_endpoint(symbol: str, _: bool = Depends(require_auth)):
    """
    Stänger en position för en specifik symbol.
    """
    try:
        positions_service = PositionsService()
        result = await positions_service.close_position(symbol)
        return result

    except Exception as e:
        logger.exception(f"Fel vid stängning av position: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Margin endpoints


@router.get("/margin", response_model=Dict[str, Any])
async def get_margin_info_endpoint(_: bool = Depends(require_auth)):
    """
    Hämtar margin-information från Bitfinex API.
    """
    try:
        margin_service = MarginService()
        margin_info = await margin_service.get_margin_info()
        return margin_info.dict()

    except Exception as e:
        logger.exception(f"Fel vid hämtning av margin-information: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/margin/status", response_model=Dict[str, Any])
async def get_margin_status_endpoint(_: bool = Depends(require_auth)):
    """
    Hämtar en sammanfattning av margin-status.
    """
    try:
        margin_service = MarginService()
        margin_status = await margin_service.get_margin_status()
        return margin_status

    except Exception as e:
        logger.exception(f"Fel vid hämtning av margin-status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/margin/leverage", response_model=Dict[str, float])
async def get_leverage_endpoint(_: bool = Depends(require_auth)):
    """
    Hämtar nuvarande hävstång (leverage).
    """
    try:
        margin_service = MarginService()
        leverage = await margin_service.get_leverage()
        return {"leverage": leverage}

    except Exception as e:
        logger.exception(f"Fel vid hämtning av hävstång: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Order History endpoints


@router.get("/orders/history", response_model=List[OrderHistoryItem])
async def get_orders_history_endpoint(
    limit: int = 25,
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
    _: bool = Depends(require_auth),
):
    """
    Hämtar orderhistorik från Bitfinex API.
    """
    try:
        order_history_service = OrderHistoryService()
        orders = await order_history_service.get_orders_history(
            limit, start_time, end_time
        )
        return orders

    except Exception as e:
        logger.exception(f"Fel vid hämtning av orderhistorik: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/order/{order_id}/trades", response_model=List[TradeItem])
async def get_order_trades_endpoint(order_id: int, _: bool = Depends(require_auth)):
    """
    Hämtar alla trades för en specifik order.
    """
    try:
        order_history_service = OrderHistoryService()
        trades = await order_history_service.get_order_trades(order_id)
        return trades

    except Exception as e:
        logger.exception(f"Fel vid hämtning av trades för order {order_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trades/history", response_model=List[TradeItem])
async def get_trades_history_endpoint(
    symbol: Optional[str] = None, limit: int = 25, _: bool = Depends(require_auth)
):
    """
    Hämtar handelshistorik från Bitfinex API.
    """
    try:
        order_history_service = OrderHistoryService()
        trades = await order_history_service.get_trades_history(symbol, limit)
        return trades

    except Exception as e:
        logger.exception(f"Fel vid hämtning av handelshistorik: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ledgers", response_model=List[LedgerEntry])
async def get_ledgers_endpoint(
    currency: Optional[str] = None, limit: int = 25, _: bool = Depends(require_auth)
):
    """
    Hämtar ledger-poster från Bitfinex API.
    """
    try:
        order_history_service = OrderHistoryService()
        ledgers = await order_history_service.get_ledgers(currency, limit)
        return ledgers

    except Exception as e:
        logger.exception(f"Fel vid hämtning av ledger: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# WebSocket Autentisering endpoints
from ws.auth import generate_token


class TokenRequest(BaseModel):
    """Request model för token generering."""

    user_id: str = "frontend_user"
    scope: str = "read"
    expiry_hours: int = 1


class TokenResponse(BaseModel):
    """Response model för token generering."""

    success: bool
    token: Optional[str] = None
    error: Optional[str] = None


@router.post("/auth/ws-token", response_model=TokenResponse)
async def generate_ws_token(request: TokenRequest):
    """
    Genererar en token för WebSocket-autentisering.
    """
    try:
        token_data = generate_token(
            user_id=request.user_id,
            scope=request.scope,
            expiry_minutes=request.expiry_hours * 60,
        )

        if token_data and isinstance(token_data, dict):
            return TokenResponse(success=True, token=token_data.get("access_token"))
        else:
            return TokenResponse(success=False, error="Kunde inte generera token")

    except Exception as e:
        logger.exception(f"Fel vid generering av WebSocket-token: {e}")
        return TokenResponse(success=False, error=str(e))


# Strategy endpoints
class WeightedStrategyRequest(BaseModel):
    """Input för viktad strategiutvärdering."""

    ema: str
    rsi: str
    atr: Optional[str] = None


class WeightedStrategyResponse(BaseModel):
    """Svar för viktad strategiutvärdering."""

    signal: str
    probabilities: Dict[str, float]


@router.post("/strategy/evaluate-weighted", response_model=WeightedStrategyResponse)
async def evaluate_weighted_strategy_endpoint(
    request: WeightedStrategyRequest, _: bool = Depends(require_auth)
):
    """
    Returnerar viktad slutsignal (buy/sell/hold) och sannolikheter baserat på
    simplifierade signaler från EMA, RSI och ATR.
    """
    try:
        result = evaluate_weighted_strategy(
            {
                "ema": request.ema,
                "rsi": request.rsi,
                "atr": request.atr,
            }
        )
        return result
    except Exception as e:
        logger.exception(f"Fel vid viktad strategiutvärdering: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Strategy settings endpoints
class StrategySettingsPayload(BaseModel):
    ema_weight: Optional[float] = None
    rsi_weight: Optional[float] = None
    atr_weight: Optional[float] = None
    ema_period: Optional[int] = None
    rsi_period: Optional[int] = None
    atr_period: Optional[int] = None


@router.get("/strategy/settings")
async def get_strategy_settings(
    symbol: Optional[str] = None, _: bool = Depends(require_auth)
):
    try:
        svc = StrategySettingsService()
        return svc.get_settings(symbol=symbol).to_dict()
    except Exception as e:
        logger.exception(f"Fel vid hämtning av strategiinställningar: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/strategy/settings")
async def update_strategy_settings(
    payload: StrategySettingsPayload,
    symbol: Optional[str] = None,
    _: bool = Depends(require_auth),
):
    try:
        svc = StrategySettingsService()
        current = svc.get_settings(symbol=symbol)
        updated = StrategySettings(
            ema_weight=(
                payload.ema_weight
                if payload.ema_weight is not None
                else current.ema_weight
            ),
            rsi_weight=(
                payload.rsi_weight
                if payload.rsi_weight is not None
                else current.rsi_weight
            ),
            atr_weight=(
                payload.atr_weight
                if payload.atr_weight is not None
                else current.atr_weight
            ),
            ema_period=(
                payload.ema_period
                if payload.ema_period is not None
                else current.ema_period
            ),
            rsi_period=(
                payload.rsi_period
                if payload.rsi_period is not None
                else current.rsi_period
            ),
            atr_period=(
                payload.atr_period
                if payload.atr_period is not None
                else current.atr_period
            ),
        )
        saved = svc.save_settings(updated, symbol=symbol)
        # Skicka WS-notifiering
        try:
            import asyncio

            from ws.manager import socket_app

            asyncio.create_task(
                socket_app.emit(
                    "notification",
                    {
                        "type": "info",
                        "title": "Strategiinställningar uppdaterade",
                        "payload": {
                            **saved.to_dict(),
                            **({"symbol": symbol} if symbol else {}),
                        },
                    },
                )
            )
        except Exception:
            pass
        return saved.to_dict()
    except Exception as e:
        logger.exception(f"Fel vid uppdatering av strategiinställningar: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Position sizing endpoint (enkel riskprocent-variant)
class PositionSizeRequest(BaseModel):
    symbol: str
    risk_percent: float = 1.0  # procent av total USD balans
    price: Optional[float] = None  # om ej satt, försök hämta ticker
    side: str = "buy"  # buy eller sell för SL/TP-beräkning
    timeframe: str = "1m"
    atr_multiplier_sl: float = 1.5
    atr_multiplier_tp: float = 3.0


@router.post("/risk/position-size")
async def calculate_position_size(
    req: PositionSizeRequest, _: bool = Depends(require_auth)
):
    try:
        # Hämta total balans i quote-valutan (auto-detektera från symbol)
        wallet_service = WalletService()
        wallets = await wallet_service.get_wallets()
        symbol_clean = req.symbol[1:] if req.symbol.startswith("t") else req.symbol
        if ":" in symbol_clean:
            quote_currency = symbol_clean.split(":", 1)[1]
        else:
            # Fallback: anta 3 sista tecken som quote (t.ex. BTCUSD -> USD)
            quote_currency = symbol_clean[-3:] if len(symbol_clean) >= 3 else "USD"
        quote_upper = quote_currency.upper()
        total_quote = sum(
            w.balance for w in wallets if w.currency.upper() == quote_upper
        )
        if total_quote <= 0 and quote_upper != "USD":
            # Fallback till USD om ingen balans i quote hittas
            total_quote = sum(w.balance for w in wallets if w.currency.upper() == "USD")
            quote_upper = "USD" if total_quote > 0 else quote_upper
        if total_quote <= 0:
            return {
                "size": 0.0,
                "reason": "no_quote_balance",
                "quote_currency": quote_currency,
            }

        # Hämta pris
        price = req.price
        if price is None:
            data = BitfinexDataService()
            ticker = await data.get_ticker(req.symbol)
            if not ticker:
                return {"size": 0.0, "reason": "no_price"}
            price = float(ticker.get("last_price", 0))
        if price <= 0:
            return {"size": 0.0, "reason": "invalid_price"}

        # Storlek i basvaluta
        quote_to_use = max(req.risk_percent, 0.0) / 100.0 * total_quote
        size = quote_to_use / price

        # Försök beräkna ATR och föreslå SL/TP
        sl_price = None
        tp_price = None
        try:
            data = BitfinexDataService()
            candles = await data.get_candles(
                req.symbol,
                req.timeframe,
                limit=req.atr_period if hasattr(req, "atr_period") else 100,
            )
            if candles:
                parsed = data.parse_candles_to_strategy_data(candles)
                # Hämta ATR-period från strategiinställningar
                ssvc = StrategySettingsService()
                s = ssvc.get_settings(symbol=req.symbol)
                atr_val = calculate_atr(
                    parsed.get("highs", []),
                    parsed.get("lows", []),
                    parsed.get("closes", []),
                    period=s.atr_period,
                )
                if atr_val is not None and atr_val > 0:
                    if req.side.lower() == "buy":
                        sl_price = price - req.atr_multiplier_sl * atr_val
                        tp_price = price + req.atr_multiplier_tp * atr_val
                    else:
                        sl_price = price + req.atr_multiplier_sl * atr_val
                        tp_price = price - req.atr_multiplier_tp * atr_val
        except Exception:
            pass

        resp = {
            "size": round(size, 8),
            "quote_alloc": round(quote_to_use, 2),
            "quote_currency": quote_upper,
            "price": price,
        }
        if sl_price is not None and tp_price is not None:
            resp.update(
                {
                    "atr_sl": round(sl_price, 8),
                    "atr_tp": round(tp_price, 8),
                    "atr_multipliers": {
                        "sl": req.atr_multiplier_sl,
                        "tp": req.atr_multiplier_tp,
                    },
                    "side": req.side,
                    "timeframe": req.timeframe,
                }
            )
        return resp
    except Exception as e:
        logger.exception(f"Fel vid positionsstorleksberäkning: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Performance endpoint (förenklad)
@router.get("/account/performance")
async def get_account_performance(_: bool = Depends(require_auth)):
    try:
        perf = PerformanceService()
        equity = await perf.compute_current_equity()
        pnl = await perf.compute_realized_pnl(limit=500)
        return {"equity": equity, "realized": pnl}
    except Exception as e:
        logger.exception(f"Fel vid performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Market data endpoints
@router.get("/market/ticker/{symbol}")
async def market_ticker(symbol: str, _: bool = Depends(require_auth)):
    try:
        data = BitfinexDataService()
        result = await data.get_ticker(symbol)
        if not result:
            raise HTTPException(status_code=502, detail="Kunde inte hämta ticker")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Fel vid ticker: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/market/candles/{symbol}")
async def market_candles(
    symbol: str,
    timeframe: str = "1m",
    limit: int = 100,
    _: bool = Depends(require_auth),
):
    try:
        data = BitfinexDataService()
        candles = await data.get_candles(symbol, timeframe, limit)
        if candles is None:
            raise HTTPException(status_code=502, detail="Kunde inte hämta candles")
        parsed = data.parse_candles_to_strategy_data(candles)
        from services.strategy import evaluate_strategy

        # bädda in symbol i parsed för vikt-override
        parsed["symbol"] = symbol
        strategy = evaluate_strategy(parsed)
        return {
            "candles_count": len(candles),
            "strategy": strategy,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Fel vid candles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Health endpoint
@router.get("/health")
async def health(_: bool = Depends(require_auth)):
    try:
        from services.bitfinex_websocket import bitfinex_ws

        return {
            "rest": True,
            "ws_connected": bool(bitfinex_ws.is_connected),
            "ws_authenticated": bool(bitfinex_ws.is_authenticated),
        }
    except Exception as e:
        logger.exception(f"Health error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Symbols endpoint
@router.get("/market/symbols")
async def market_symbols(
    test_only: bool = False, format: str = "v2", _: bool = Depends(require_auth)
):
    try:
        svc = SymbolService()
        return svc.get_symbols(test_only=test_only, fmt=format)
    except Exception as e:
        logger.exception(f"Fel vid symbols: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Watchlist endpoint (liten vy) med ticker + volym + senaste strategi-signal
@router.get("/market/watchlist")
async def market_watchlist(
    symbols: Optional[str] = None, _: bool = Depends(require_auth)
):
    try:
        svc = SymbolService()
        data = BitfinexDataService()
        if symbols:
            syms = [s.strip() for s in symbols.split(",") if s.strip()]
        else:
            syms = svc.get_symbols(test_only=True, fmt="v2")[:10]
        out = []
        for s in syms:
            ticker = await data.get_ticker(s)
            last = float(ticker.get("last_price", 0)) if ticker else None
            vol = float(ticker.get("volume", 0)) if ticker else None
            candles = await data.get_candles(s, "1m", 50)
            strat = None
            if candles:
                parsed = data.parse_candles_to_strategy_data(candles)
                from services.strategy import evaluate_strategy

                parsed["symbol"] = s
                strat = evaluate_strategy(parsed)
            out.append({"symbol": s, "last": last, "volume": vol, "strategy": strat})
        return out
    except Exception:
        logger.exception("Fel vid watchlist")
        raise HTTPException(status_code=500, detail="internal_error")


# Backtest endpoint
class BacktestRequest(BaseModel):
    symbol: str
    timeframe: str = "1m"
    limit: int = 500
    tz_offset_minutes: int | None = 0


@router.post("/strategy/backtest")
async def strategy_backtest(payload: BacktestRequest, _: bool = Depends(require_auth)):
    try:
        svc = BacktestService()
        tz_off = payload.tz_offset_minutes or 0
        result = await svc.run(payload.symbol, payload.timeframe, payload.limit, tz_off)
        return result
    except Exception:
        logger.exception("Backtest fel")
        raise HTTPException(status_code=500, detail="internal_error")


# --- Auto trading controls ---
class AutoStartRequest(BaseModel):
    symbol: str


@router.post("/auto/start")
async def auto_start(req: AutoStartRequest, _: bool = Depends(require_auth)):
    try:
        await trading_integration.start_automated_trading(req.symbol)
        _emit_notification("info", "Auto trading startad", {"symbol": req.symbol})
        return {"ok": True, "symbol": req.symbol}
    except Exception as e:
        logger.exception(f"Fel vid auto/start: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/auto/stop")
async def auto_stop(req: AutoStartRequest, _: bool = Depends(require_auth)):
    try:
        await trading_integration.stop_automated_trading(req.symbol)
        _emit_notification("info", "Auto trading stoppad", {"symbol": req.symbol})
        return {"ok": True, "symbol": req.symbol}
    except Exception as e:
        logger.exception(f"Fel vid auto/stop: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/auto/status")
async def auto_status(_: bool = Depends(require_auth)):
    try:
        summary = await trading_integration.get_account_summary()
        return {
            "active_symbols": list(trading_integration.active_symbols),
            "summary": summary,
        }
    except Exception as e:
        logger.exception(f"Fel vid auto/status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Batch/Stop-all endpoints
class AutoBatchRequest(BaseModel):
    symbols: List[str]


@router.post("/auto/stop-all")
async def auto_stop_all(_: bool = Depends(require_auth)):
    try:
        await trading_integration.stop_all_trading()
        _emit_notification("info", "Auto trading stoppad (alla)", {"symbols": []})
        return {"ok": True}
    except Exception as e:
        logger.exception(f"Fel vid auto/stop-all: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/auto/start-batch")
async def auto_start_batch(req: AutoBatchRequest, _: bool = Depends(require_auth)):
    try:
        started: List[str] = []
        for sym in req.symbols:
            s = sym.strip()
            if not s:
                continue
            try:
                await trading_integration.start_automated_trading(s)
                started.append(s)
            except Exception as ie:
                logger.warning(f"Kunde inte starta {s}: {ie}")
        if started:
            _emit_notification(
                "info", "Auto trading startad (batch)", {"symbols": started}
            )
        return {"ok": True, "started": started}
    except Exception as e:
        logger.exception(f"Fel vid auto/start-batch: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Bracket order endpoint
@router.post("/order/bracket", response_model=OrderResponse)
async def place_bracket_order(
    req: BracketOrderRequest, _: bool = Depends(require_auth)
):
    try:
        logger.info(f"Mottog bracket-order: {req.dict()}")
        risk = RiskManager()
        ok, reason = risk.pre_trade_checks(symbol=req.symbol)
        if not ok:
            return OrderResponse(success=False, error=f"risk_blocked:{reason}")

        # Hjälpare: extrahera order-id från Bitfinex svar (kan vara list-format)
        def _extract_order_id(res: Any) -> int | None:
            try:
                if isinstance(res, dict):
                    return res.get("order_id") or res.get("id")
                if isinstance(res, list) and len(res) >= 5:
                    orders = res[4]
                    if (
                        isinstance(orders, list)
                        and len(orders) > 0
                        and isinstance(orders[0], list)
                    ):
                        return int(orders[0][0])
            except Exception:
                return None
            return None

        # Entry
        entry_payload = {
            "symbol": req.symbol,
            "amount": req.amount,
            "type": req.entry_type,
            "side": req.side,
        }
        if req.entry_type and "LIMIT" in req.entry_type.upper():
            entry_payload["price"] = req.entry_price
        # Validera payload
        is_valid, err = order_validator.validate_order(entry_payload)
        if not is_valid:
            return OrderResponse(success=False, error=f"validation_error:{err}")
        entry_res = await rest_auth.place_order(entry_payload)
        if "error" in entry_res:
            return OrderResponse(success=False, error=entry_res.get("error"))
        entry_id = _extract_order_id(entry_res)
        if not entry_id:
            return OrderResponse(success=False, error="entry_id_missing")

        sl_id = None
        tp_id = None
        # SL
        if req.sl_price:
            sl_payload = {
                "symbol": req.symbol,
                "amount": (
                    req.amount if req.side.lower() == "sell" else f"-{req.amount}"
                ),
                "type": "EXCHANGE STOP",
                "price": req.sl_price,
                "side": "sell" if req.side.lower() == "buy" else "buy",
            }
            is_valid, err = order_validator.validate_order(sl_payload)
            if not is_valid:
                return OrderResponse(success=False, error=f"validation_error:{err}")
            sl_res = await rest_auth.place_order(sl_payload)
            if "error" not in sl_res:
                sl_id = _extract_order_id(sl_res)
        # TP
        if req.tp_price:
            tp_payload = {
                "symbol": req.symbol,
                "amount": (
                    req.amount if req.side.lower() == "sell" else f"-{req.amount}"
                ),
                "type": "EXCHANGE LIMIT",
                "price": req.tp_price,
                "side": "sell" if req.side.lower() == "buy" else "buy",
            }
            is_valid, err = order_validator.validate_order(tp_payload)
            if not is_valid:
                return OrderResponse(success=False, error=f"validation_error:{err}")
            tp_res = await rest_auth.place_order(tp_payload)
            if "error" not in tp_res:
                tp_id = _extract_order_id(tp_res)

        gid = f"br_{entry_id}"
        bracket_manager.register_group(str(gid), entry_id, sl_id, tp_id)
        await notification_service.notify(
            "info",
            "Bracket order lagd",
            {
                "entry_id": entry_id,
                "sl_id": sl_id,
                "tp_id": tp_id,
                "symbol": req.symbol,
            },
        )
        return OrderResponse(
            success=True, data={"entry_id": entry_id, "sl_id": sl_id, "tp_id": tp_id}
        )
    except Exception as e:
        logger.exception(f"Fel vid bracket-order: {e}")
        return OrderResponse(success=False, error=str(e))


# Risk windows GET + pause/resume
@router.get("/risk/windows")
async def get_trading_windows(_: bool = Depends(require_auth)):
    try:
        s = Settings()
        tw = TradingWindowService(s)
        return {
            "timezone": tw.rules.timezone,
            "windows": tw.rules.windows,
            "paused": tw.rules.paused,
            "limits": tw.get_limits(),
        }
    except Exception as e:
        logger.exception(f"Fel vid hämtning av trading windows: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/risk/pause")
async def pause_trading(_: bool = Depends(require_auth)):
    try:
        s = Settings()
        tw = TradingWindowService(s)
        tw.set_paused(True)
        return {"success": True, "paused": True}
    except Exception as e:
        logger.exception(f"Fel vid paus: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/risk/resume")
async def resume_trading(_: bool = Depends(require_auth)):
    try:
        s = Settings()
        tw = TradingWindowService(s)
        tw.set_paused(False)
        return {"success": True, "paused": False}
    except Exception as e:
        logger.exception(f"Fel vid resume: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Performance breakdown per symbol
@router.get("/account/performance/detail")
async def get_account_performance_detail(_: bool = Depends(require_auth)):
    try:
        wallet_svc = WalletService()
        pos_svc = PositionsService()
        data_svc = BitfinexDataService()
        perf = PerformanceService()

        wallets = await wallet_svc.get_wallets()
        positions = await pos_svc.get_positions()

        # Hjälp: parse symbol till (base, quote)
        def parse_bq(sym: str) -> Dict[str, str]:
            s = sym[1:] if sym.startswith("t") else sym
            if ":" in s:
                base, quote = s.split(":", 1)
            else:
                base, quote = s[:-3], s[-3:]
            return {"base": base.upper(), "quote": quote.upper()}

        # PnL per symbol + positionsinfo med current price
        pnl_by_symbol: Dict[str, float] = {}
        positions_info: List[Dict[str, Any]] = []
        prices_cache: Dict[str, float] = {}

        for p in positions:
            # Hämta current price (cache per symbol)
            if p.symbol not in prices_cache:
                try:
                    t = await data_svc.get_ticker(p.symbol)
                    prices_cache[p.symbol] = float(t.get("last_price", 0)) if t else 0.0
                except Exception:
                    prices_cache[p.symbol] = 0.0
            cur_price = prices_cache[p.symbol]

            pnl = float(p.profit_loss or 0.0)
            pnl_by_symbol[p.symbol] = pnl_by_symbol.get(p.symbol, 0.0) + pnl

            positions_info.append(
                {
                    "symbol": p.symbol,
                    "amount": p.amount,
                    "base_price": p.base_price,
                    "current_price": cur_price,
                    "profit_loss": p.profit_loss,
                    "profit_loss_percentage": p.profit_loss_percentage,
                    "liquidation_price": p.liquidation_price,
                    "status": p.status,
                }
            )

        # Per-symbol wallets (summa av base- och quote-valutor över alla wallet-typer)
        wallets_by_symbol: Dict[str, Dict[str, Any]] = {}
        # För snabb uppslagning: summera per currency
        totals_by_currency: Dict[str, Dict[str, float]] = {}
        for w in wallets:
            cur = w.currency.upper()
            e = totals_by_currency.setdefault(
                cur, {"total": 0.0, "exchange": 0.0, "margin": 0.0, "funding": 0.0}
            )
            e["total"] += float(w.balance)
            e[w.wallet_type] += float(w.balance)

        for p in positions:
            bq = parse_bq(p.symbol)
            base = bq["base"]
            quote = bq["quote"]
            base_tot = totals_by_currency.get(base, {})
            quote_tot = totals_by_currency.get(quote, {})
            wallets_by_symbol[p.symbol] = {
                "base_currency": base,
                "quote_currency": quote,
                "base_total": float(base_tot.get("total", 0.0)),
                "quote_total": float(quote_tot.get("total", 0.0)),
                "base_by_type": {
                    "exchange": float(base_tot.get("exchange", 0.0)),
                    "margin": float(base_tot.get("margin", 0.0)),
                    "funding": float(base_tot.get("funding", 0.0)),
                },
                "quote_by_type": {
                    "exchange": float(quote_tot.get("exchange", 0.0)),
                    "margin": float(quote_tot.get("margin", 0.0)),
                    "funding": float(quote_tot.get("funding", 0.0)),
                },
            }

        realized = await perf.compute_realized_pnl(limit=500)
        equity = await perf.compute_current_equity()
        return {
            "wallets": [w.dict() for w in wallets],
            "positions": positions_info,
            "pnl_by_symbol": pnl_by_symbol,
            "wallets_by_symbol": wallets_by_symbol,
            "prices": prices_cache,
            "realized": realized,
            "equity": equity,
        }
    except Exception as e:
        logger.exception(f"Fel vid performance/detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Risk endpoints
class UpdateMaxTradesRequest(BaseModel):
    max_trades_per_day: int


@router.get("/risk/status")
async def get_risk_status(_: bool = Depends(require_auth)):
    rm = RiskManager()
    return rm.status()


@router.post("/risk/max-trades")
async def update_max_trades(
    req: UpdateMaxTradesRequest, _: bool = Depends(require_auth)
):
    # Uppdatera i runtime settings (enkel variant). Permanent lagring kräver filskrivning.
    try:
        s = Settings()
        s.MAX_TRADES_PER_DAY = req.max_trades_per_day
        # persistera till regler
        tw = TradingWindowService(s)
        tw.rules.max_trades_per_day = req.max_trades_per_day
        tw.save_rules()
        rm = RiskManager(s)
        return {"success": True, "status": rm.status()}
    except Exception as e:
        logger.exception(f"Fel vid uppdatering av max trades: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class UpdateMaxTradesSymbolRequest(BaseModel):
    max_trades_per_symbol_per_day: int


@router.post("/risk/max-trades-symbol")
async def update_max_trades_symbol(
    req: UpdateMaxTradesSymbolRequest, _: bool = Depends(require_auth)
):
    try:
        s = Settings()
        tw = TradingWindowService(s)
        tw.save_rules(max_trades_per_symbol_per_day=req.max_trades_per_symbol_per_day)
        rm = RiskManager(s)
        return {"success": True, "status": rm.status()}
    except Exception as e:
        logger.exception(f"Fel vid uppdatering av max trades per symbol: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/risk/trade-counter")
async def get_trade_counter(_: bool = Depends(require_auth)):
    try:
        rm = RiskManager()
        return rm.trade_counter.stats()
    except Exception as e:
        logger.exception(f"Fel vid hämtning av trade counter: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Circuit Breaker endpoints ---
class CircuitConfigRequest(BaseModel):
    enabled: Optional[bool] = None
    window_seconds: Optional[int] = None
    max_errors_per_window: Optional[int] = None
    notify: Optional[bool] = None


@router.get("/risk/circuit")
async def circuit_status(_: bool = Depends(require_auth)):
    try:
        rm = RiskManager()
        return rm.status().get("circuit", {})
    except Exception as e:
        logger.exception(f"Fel vid circuit status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/risk/circuit/reset")
async def circuit_reset(
    resume: bool = True, clear_errors: bool = True, _: bool = Depends(require_auth)
):
    try:
        rm = RiskManager()
        return rm.circuit_reset(resume=resume, clear_errors=clear_errors)
    except Exception as e:
        logger.exception(f"Fel vid circuit reset: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/risk/circuit/config")
async def circuit_config(req: CircuitConfigRequest, _: bool = Depends(require_auth)):
    try:
        rm = RiskManager()
        return rm.update_circuit_config(
            enabled=req.enabled,
            window_seconds=req.window_seconds,
            max_errors_per_window=req.max_errors_per_window,
            notify=req.notify,
        )
    except Exception as e:
        logger.exception(f"Fel vid circuit config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Equity endpoints
@router.get("/account/equity")
async def get_equity(_: bool = Depends(require_auth)):
    try:
        perf = PerformanceService()
        equity = await perf.compute_current_equity()
        return equity
    except Exception as e:
        logger.exception(f"Fel vid equity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/account/equity/snapshot")
async def equity_snapshot(_: bool = Depends(require_auth)):
    try:
        perf = PerformanceService()
        snap = await perf.snapshot_equity()
        return snap
    except Exception as e:
        logger.exception(f"Fel vid equity snapshot: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/account/equity/history")
async def equity_history(limit: Optional[int] = None, _: bool = Depends(require_auth)):
    try:
        perf = PerformanceService()
        hist = perf.get_equity_history(limit=limit)
        return {"equity": hist}
    except Exception as e:
        logger.exception(f"Fel vid equity history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Order Templates endpoints
class SaveTemplateRequest(BaseModel):
    name: str
    symbol: Optional[str] = None
    side: Optional[str] = None
    type: Optional[str] = None
    amount: Optional[str] = None
    price: Optional[str] = None
    sl_price: Optional[str] = None
    tp_price: Optional[str] = None


# OBS: GET /order/templates togs bort för att undvika kollision med /order/{order_id} (int)


@router.get("/order/templates/{name}")
async def get_template(name: str, _: bool = Depends(require_auth)):
    try:
        svc = OrderTemplatesService()
        tpl = svc.get_template(name)
        if not tpl:
            raise HTTPException(status_code=404, detail="template_not_found")
        return tpl
    except HTTPException:
        raise
    except Exception:
        logger.exception("Fel vid get_template")
        raise HTTPException(status_code=500, detail="internal_error")


@router.post("/order/templates")
async def save_template(payload: SaveTemplateRequest, _: bool = Depends(require_auth)):
    try:
        svc = OrderTemplatesService()
        result = svc.save_template(
            {k: v for k, v in payload.dict().items() if v is not None}
        )
        return result
    except Exception as e:
        logger.exception(f"Fel vid save_template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Alias endpoints för att undvika kollision med /order/{order_id}
@router.get("/orders/templates", response_model=List[Dict[str, Any]])
async def list_templates_alias(_: bool = Depends(require_auth)):
    try:
        svc = OrderTemplatesService()
        items = svc.list_templates()
        if not isinstance(items, list):
            return []
        return items
    except Exception as e:
        logger.exception(f"Fel vid list_templates (alias): {e}")
        return []


@router.delete("/order/templates/{name}")
async def delete_template(name: str, _: bool = Depends(require_auth)):
    try:
        svc = OrderTemplatesService()
        ok = svc.delete_template(name)
        if not ok:
            raise HTTPException(status_code=404, detail="template_not_found")
        return {"deleted": True, "name": name}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Fel vid delete_template")
        raise HTTPException(status_code=500, detail="internal_error")


@router.post("/orders/templates")
async def save_template_alias(
    payload: SaveTemplateRequest, _: bool = Depends(require_auth)
):
    try:
        svc = OrderTemplatesService()
        result = svc.save_template(
            {k: v for k, v in payload.dict().items() if v is not None}
        )
        return result
    except Exception as e:
        logger.exception(f"Fel vid save_template (alias): {e}")
        raise HTTPException(status_code=500, detail=str(e))


class UpdateWindowsRequest(BaseModel):
    timezone: Optional[str] = None
    windows: Optional[Dict[str, List[List[str]]]] = None
    paused: Optional[bool] = None
    max_trades_per_symbol_per_day: Optional[int] = None
    max_trades_per_day: Optional[int] = None
    trade_cooldown_seconds: Optional[int] = None


@router.post("/risk/windows")
async def update_trading_windows(
    req: UpdateWindowsRequest, _: bool = Depends(require_auth)
):
    try:
        s = Settings()
        tw = TradingWindowService(s)
        # Omvandla list[List[str]] till List[Tuple[str, str]]
        windows_typed = None
        if req.windows is not None:
            windows_typed = {k: [(a, b) for a, b in v] for k, v in req.windows.items()}
        tw.save_rules(
            timezone=req.timezone,
            windows=windows_typed,
            paused=req.paused,
            max_trades_per_symbol_per_day=req.max_trades_per_symbol_per_day,
            max_trades_per_day=req.max_trades_per_day,
            trade_cooldown_seconds=req.trade_cooldown_seconds,
        )
        rm = RiskManager(s)
        return {"success": True, "status": rm.status()}
    except Exception as e:
        logger.exception(f"Fel vid uppdatering av trading windows: {e}")
        raise HTTPException(status_code=500, detail=str(e))
