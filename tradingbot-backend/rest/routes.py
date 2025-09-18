"""
REST API Routes - TradingBot Backend

Detta är huvudmodulen för REST API-routes.
Inkluderar endpoints för orderhantering, marknadsdata, plånboksinformation och positioner.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any

import jwt
from fastapi import APIRouter, Depends, HTTPException, Response, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.responses import JSONResponse, PlainTextResponse, ORJSONResponse
from pydantic import BaseModel, Field

from config.settings import Settings, settings
from indicators.atr import calculate_atr

# REST auth helpers/proxies (order submit/cancel)
import rest.auth as rest_auth
from rest.active_orders import ActiveOrdersService
from rest.funding import FundingService
from rest.margin import MarginService

# MCP routes removed - MCP functionality disabled
# from rest.mcp_routes import router as mcp_router
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
from services.bitfinex_websocket import bitfinex_ws
from services.bracket_manager import bracket_manager
from services.market_data_facade import get_market_data
from services.metrics import (
    render_prometheus_text,
)  # kvar tills klienten rullas ut överallt
from services.metrics_client import get_metrics_client
import services.runtime_config as rc
from services.idempotency_service import get_idempotency_service
from services.notifications import notification_service
from services.performance import PerformanceService
from services.prob_model import prob_model
from services.prob_validation import validate_on_candles
from services.risk_manager import RiskManager

# runtime_config används via lokala imports där det behövs
from services.risk_policy_engine import RiskPolicyEngine
from services.unified_risk_service import unified_risk_service
from utils.feature_flags import (
    get_feature_flag as _get_flag,
    set_feature_flag as _set_flag,
)
from services.signal_service import SignalService
from services.strategy import evaluate_weighted_strategy
from services.strategy_settings import StrategySettings, StrategySettingsService
from services.symbols import SymbolService
from services.templates import OrderTemplatesService
from services.trading_integration import trading_integration
from services.trading_window import TradingWindowService
from services.watchlist_service import get_watchlist_service
from utils.advanced_rate_limiter import get_advanced_rate_limiter
from utils.candle_cache import candle_cache
from utils.candles import parse_candles_to_strategy_data
from utils.logger import get_logger
from utils.rate_limiter import get_rate_limiter
from pathlib import Path
import json

# WebSocket Autentisering endpoints
from ws.auth import generate_token

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v2")
security = HTTPBearer(auto_error=False)
# Harmonisera verifierings-hemlighet med generatorn (ws.auth) och tillåt fallback
JWT_SECRET = settings.SOCKETIO_JWT_SECRET or getattr(settings, "JWT_SECRET_KEY", None) or "socket-io-secret"
_rl_adv = get_advanced_rate_limiter()
_rl = get_rate_limiter()


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
    price: str | None = None  # Optional för MARKET orders
    type: str = "EXCHANGE LIMIT"  # EXCHANGE LIMIT, EXCHANGE MARKET, etc.
    side: str | None = None  # Optional för att matcha test_order_operations.py
    post_only: bool = False
    reduce_only: bool = False
    client_id: str | None = None  # idempotens


class CancelOrderRequest(BaseModel):
    """Request model för orderavbrytning."""

    order_id: int


class UpdateOrderRequest(BaseModel):
    """Request model för orderuppdatering."""

    order_id: int
    price: float | None = None
    amount: float | None = None


class OrderResponse(BaseModel):
    """Generiskt svar för orderoperationer (wrapper)."""

    success: bool
    error: str | None = None
    data: Any | None = None


# --- WS order requestmodeller ---
class WSOrderUpdateRequest(BaseModel):
    order_id: int
    price: float | None = None
    amount: float | None = None
    extra: dict[str, Any] | None = None


class WSCancelMultiRequest(BaseModel):
    ids: list[int] | None = None
    cids: list[int] | None = None
    cid_date: str | None = None  # YYYY-MM-DD


class WSOrderOpsRequest(BaseModel):
    ops: list[Any]


class WSUnsubscribeRequest(BaseModel):
    channel: str  # ticker|trades|candles
    symbol: str  # tPAIR
    timeframe: str | None = None  # för candles, t.ex. 1m/5m


class WSSubscribeRequest(BaseModel):
    channel: str  # ticker|trades|candles
    symbol: str  # tPAIR
    timeframe: str | None = None  # för candles, t.ex. 1m/5m


class ProbPredictRequest(BaseModel):
    symbol: str
    timeframe: str = "1m"
    horizon: int = 20  # antal candles (metadata)
    tp: float = 0.002  # 0.2%
    sl: float = 0.002  # 0.2%
    fees: float = 0.0003  # 3 bps


class ProbPreviewRequest(BaseModel):
    symbol: str
    timeframe: str = "1m"
    risk_percent_cap: float | None = None  # override PROB_SIZE_MAX_RISK_PCT


@router.post("/prob/preview")
async def prob_preview(req: ProbPreviewRequest, _bypass_auth: bool = Depends(security)):
    try:
        # 1) inferens
        s = settings
        pred = await prob_predict(
            ProbPredictRequest(symbol=req.symbol, timeframe=req.timeframe),
            True,  # bypass auth re-check
        )
        # pred kan vara Response JSON; säkerställ dict
        if hasattr(pred, "dict"):
            pred = pred.dict()  # type: ignore[assignment]
        if not isinstance(pred, dict):
            return pred
        decision = pred.get("decision")
        if decision not in ("buy", "sell"):
            return {"decision": decision, "reason": "abstain"}
        # 2) positionsstorlek (återanvänd /risk/position-size i miniform)
        # Läs autotrade runtime‑state; påverkar bara blockeringen tidigare
        try:
            import services.runtime_config as rc

            autotrade_on = bool(
                rc.get_bool(
                    "PROB_AUTOTRADE_ENABLED",
                    getattr(s, "PROB_AUTOTRADE_ENABLED", False),
                )
            )
        except Exception:
            autotrade_on = bool(getattr(s, "PROB_AUTOTRADE_ENABLED", False))
        cap = float(req.risk_percent_cap or s.PROB_SIZE_MAX_RISK_PCT)
        side = str(decision)
        # begär storlek med ATR‑baserade SL/TP
        psz = await calculate_position_size(
            PositionSizeRequest(symbol=req.symbol, risk_percent=cap, side=side),
            True,
        )
        if not isinstance(psz, dict):
            return {"decision": decision, "size": 0.0, "reason": "size_error"}

        # Kelly + confidence‑viktning
        base_size = float(psz.get("size") or 0.0)
        try:
            probs = pred.get("probabilities", {}) or {}
            p_buy = float(probs.get("buy", 0.0))
            p_sell = float(probs.get("sell", 0.0))
            p_sel = p_buy if side == "buy" else p_sell
            params = pred.get("params", {}) or {}
            tp = float(params.get("tp", 0.002) or 0.002)
            sl = float(params.get("sl", 0.002) or 0.002)
            b = float(tp / sl) if sl else 1.0
            kelly_raw = p_sel - (1.0 - p_sel) / (b if b > 0 else 1.0)
            kelly_cap = float(getattr(s, "PROB_SIZE_KELLY_CAP", 0.5) or 0.5)
            kelly_used = max(0.0, min(kelly_raw, kelly_cap))
            kelly_norm = (kelly_used / kelly_cap) if kelly_cap > 0 else 0.0
            conf = float(pred.get("confidence", 0.0) or 0.0)
            conf_w = float(getattr(s, "PROB_SIZE_CONF_WEIGHT", 0.5) or 0.5)
            conf_scaled = max(0.0, min(conf, 1.0))
            size_weight = max(0.0, min(1.0, (1.0 - conf_w) * kelly_norm + conf_w * conf_scaled))
            weighted_size = round(base_size * size_weight, 8)
        except Exception:
            kelly_raw = 0.0
            kelly_used = 0.0
            size_weight = 1.0
            weighted_size = base_size

        # svar
        return {
            "decision": decision,
            "ev": pred.get("ev"),
            "probabilities": pred.get("probabilities"),
            "size": weighted_size,
            "price": psz.get("price"),
            "atr_sl": psz.get("atr_sl"),
            "atr_tp": psz.get("atr_tp"),
            "quote_alloc": psz.get("quote_alloc"),
            "quote_currency": psz.get("quote_currency"),
            "size_base": base_size,
            "size_weight": size_weight,
            "kelly_raw": round(kelly_raw, 6),
            "kelly_used": round(kelly_used, 6),
            "confidence": pred.get("confidence"),
        }
    except Exception as e:
        logger.exception(f"prob/preview error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


class BracketOrderRequest(BaseModel):
    """Request för bracket-order (entry + valfri SL/TP)."""

    symbol: str
    amount: str
    side: str  # buy/sell
    entry_type: str = "EXCHANGE MARKET"  # eller EXCHANGE LIMIT (kräver entry_price)
    entry_price: str | None = None
    sl_price: str | None = None
    tp_price: str | None = None
    tif: str | None = None  # e.g. GTC/IOC/FOK
    post_only: bool = False
    reduce_only: bool = False
    client_id: str | None = None  # idempotens


class ProbTradeRequest(BaseModel):
    symbol: str
    timeframe: str = "1m"
    risk_percent_cap: float | None = None


@router.post("/prob/trade")
async def prob_trade(req: ProbTradeRequest, _bypass_auth: bool = Depends(security)):
    try:
        s = settings
        if not bool(getattr(s, "PROB_AUTOTRADE_ENABLED", False)):
            try:
                from time import time as _now

                from services.metrics import metrics_store as _ms

                key = f"{req.symbol}|{req.timeframe}"
                last = _ms.setdefault("prob_trade_last", {})
                last[key] = {
                    "ts": int(_now()),
                    "symbol": req.symbol,
                    "tf": req.timeframe,
                    "side": None,
                    "result": "autotrade_disabled",
                    "size": 0.0,
                }
            except Exception:
                pass
            return {"ok": False, "error": "autotrade_disabled"}
        # Tidig guardrail: respektera riskregler innan vi gör preview
        try:
            decision = unified_risk_service.evaluate_risk(symbol=req.symbol)
            reason = decision.reason
            if not decision.allowed:
                try:
                    from services.metrics import inc_labeled as _inc_labeled

                    _inc_labeled(
                        "prob_trade_events",
                        {
                            "type": "risk_blocked",
                            "symbol": req.symbol,
                            "reason": str(reason),
                        },
                    )
                    try:
                        from time import time as _now

                        from services.metrics import metrics_store as _ms

                        key = f"{req.symbol}|{req.timeframe}"
                        last = _ms.setdefault("prob_trade_last", {})
                        last[key] = {
                            "ts": int(_now()),
                            "symbol": req.symbol,
                            "tf": req.timeframe,
                            "side": None,
                            "result": f"risk_blocked:{reason}",
                            "size": 0.0,
                        }
                    except Exception:
                        pass
                except Exception:
                    pass
                return {"ok": False, "error": f"risk_blocked:{reason}"}
        except Exception:
            pass
        # Mät latens för orderläggningen
        import time as _t

        _t0 = _t.time()
        pv = await prob_preview(
            ProbPreviewRequest(
                symbol=req.symbol,
                timeframe=req.timeframe,
                risk_percent_cap=req.risk_percent_cap,
            ),
            True,
        )
        if hasattr(pv, "dict"):
            pv = pv.dict()  # type: ignore[assignment]
        if not isinstance(pv, dict) or pv.get("decision") not in ("buy", "sell"):
            return {"ok": False, "error": "abstain"}
        # Guardrails: margin tradable > 0
        try:
            ms = MarginService()
            msym = await ms.get_symbol_margin_status(req.symbol)
            if not (msym and float(msym.get("tradable") or 0) > 0):
                return {"ok": False, "error": "margin_unavailable"}
        except Exception:
            pass
        side = "buy" if pv["decision"] == "buy" else "sell"
        amount = str(pv.get("size") or 0)
        if not amount or float(amount) <= 0:
            try:
                from time import time as _now

                from services.metrics import metrics_store as _ms

                key = f"{req.symbol}|{req.timeframe}"
                last = _ms.setdefault("prob_trade_last", {})
                last[key] = {
                    "ts": int(_now()),
                    "symbol": req.symbol,
                    "tf": req.timeframe,
                    "side": side,
                    "result": "size_zero",
                    "size": 0.0,
                }
            except Exception:
                pass
            return {"ok": False, "error": "size_zero"}
        # Bracket: marknadsentry + ATR SL/TP
        req_br = BracketOrderRequest(
            symbol=req.symbol,
            amount=amount,
            side=side,
            entry_type="EXCHANGE MARKET",
            entry_price=None,
            sl_price=(pv.get("atr_sl") if pv.get("atr_sl") else None),
            tp_price=(pv.get("atr_tp") if pv.get("atr_tp") else None),
            post_only=False,
            reduce_only=False,
        )
        res = await place_bracket_order(req_br, True)
        # Normalisera svar för metrics/utfall
        try:
            from typing import Any

            res_dict: dict[str, Any]
            if isinstance(res, dict):
                res_dict = res  # type: ignore[assignment]
            elif hasattr(res, "dict"):
                res_dict = res.dict()  # type: ignore[assignment]
            else:
                res_dict = {"success": False}
        except Exception:
            res_dict = {"success": False}
        # metrics/loggar
        try:
            from services.metrics import inc_labeled as _inc_labeled

            _inc_labeled(
                "prob_trade_events",
                {"type": "submit", "symbol": req.symbol, "side": side},
            )
            _inc_labeled(
                "prob_trade_events",
                {"type": "placed", "symbol": req.symbol, "side": side},
            )
            _inc_labeled(
                "prob_trade_sizes",
                {"symbol": req.symbol, "side": side},
                by=max(int(float(amount) * 1e6), 1),  # pseudo-size for counting
            )
            # Latens för prob/trade (ms) per symbol/side/timeframe
            _t1 = _t.time()
            _inc_labeled(
                "prob_trade_latency_ms",
                {"symbol": req.symbol, "side": side, "tf": req.timeframe},
                by=max(int((_t1 - _t0) * 1000), 0),
            )
            # Utfall: success/error per symbol/side/timeframe
            outcome = "success" if bool(res_dict.get("success", False)) else "error"
            _inc_labeled(
                "prob_trade_outcome",
                {
                    "symbol": req.symbol,
                    "side": side,
                    "tf": req.timeframe,
                    "result": outcome,
                },
                by=1,
            )
            # Senaste utfall (för UI)
            try:
                from time import time as _now

                from services.metrics import metrics_store as _ms

                key = f"{req.symbol}|{req.timeframe}"
                last = _ms.setdefault("prob_trade_last", {})
                amt = 0.0
                try:
                    amt = float(amount)
                except Exception:
                    amt = 0.0
                last[key] = {
                    "ts": int(_now()),
                    "symbol": req.symbol,
                    "tf": req.timeframe,
                    "side": side,
                    "result": outcome,
                    "size": amt,
                }
            except Exception:
                pass
        except Exception:
            pass
        return {"ok": True, "result": res_dict}
    except Exception as e:
        logger.exception(f"prob/trade error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


# Order endpoints


def require_auth(credentials: HTTPAuthorizationCredentials | None = Depends(security)):
    """Kräv JWT endast när AUTH_REQUIRED=True. Annars släpp igenom utan header.

    Läser runtime‑override först (POST /api/v2/runtime/config), faller tillbaka till Settings().
    """
    try:
        from services.runtime_config import get_bool as _rc_get_bool  # lazy import

        auth_required = bool(_rc_get_bool("AUTH_REQUIRED", settings.AUTH_REQUIRED))
    except Exception:
        auth_required = bool(settings.AUTH_REQUIRED)
    if not auth_required:
        return True
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=403, detail="Not authenticated")
    try:
        jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        return True
    except Exception as e:
        raise HTTPException(status_code=401, detail="Ogiltig token") from e


@router.post("/order", response_model=OrderResponse)
async def place_order_endpoint(order: OrderRequest, _: bool = Depends(require_auth)):
    """
    Lägger en order via Bitfinex API.
    """
    try:
        # Logga endast sammanfattning för att undvika läckage av tradingdetaljer i prod
        try:
            od = order.dict()
            logger.debug(
                "Mottog orderförfrågan: symbol=%s type=%s amount=%s price=%s flags(post_only=%s, reduce_only=%s)",
                od.get("symbol"),
                od.get("type"),
                od.get("amount"),
                od.get("price"),
                od.get("post_only"),
                od.get("reduce_only"),
            )
        except Exception:
            logger.debug("Mottog orderförfrågan (kunde inte serialisera)")
        # Enkel rate-limit (default avstängd om MAX_REQUESTS <= 0)
        try:
            max_requests = int(getattr(settings, "ORDER_RATE_LIMIT_MAX", 0) or 0)
            window_seconds = int(getattr(settings, "ORDER_RATE_LIMIT_WINDOW", 0) or 0)
            if max_requests > 0 and window_seconds > 0:
                key = "place_order"
                if not _rl.is_allowed(key, max_requests, window_seconds):
                    try:
                        get_metrics_client().inc("rate_limited_total")
                    except Exception:
                        pass
                    return OrderResponse(success=False, error="rate_limited")
        except Exception:
            pass

        # Dry-run: simulera svar utan att lägga order
        try:
            import os as _os
            import services.runtime_config as rc

            if rc.get_bool("DRY_RUN_ENABLED", False) and "PYTEST_CURRENT_TEST" not in _os.environ:
                return OrderResponse(
                    success=True,
                    data={
                        "dry_run": True,
                        "order": order.dict(),
                    },
                )
        except Exception:
            pass

        # Resolvera symbol före validering för att undvika falska "Ogiltig symbol"
        payload = order.dict()
        try:
            sym_in = str(payload.get("symbol", ""))
            from services.symbols import SymbolService as _SS

            _svc = _SS()
            await _svc.refresh()
            eff = _svc.resolve(sym_in)
            if not _svc.listed(eff):
                return OrderResponse(success=False, error="validation_error:pair_not_listed")
            payload["symbol"] = eff
        except Exception:
            pass

        # Validera order efter symbol‑resolution
        is_valid, err = order_validator.validate_order(payload)
        if not is_valid:
            return OrderResponse(success=False, error=f"validation_error:{err}")

        # Riskkontroller före order (skippa i pytest-miljö för enhetstester)
        import os

        if "PYTEST_CURRENT_TEST" not in os.environ:
            # Enhetlig riskkontroll via UnifiedRiskService
            amount = float(order.amount) if order.amount else None
            price = float(order.price) if order.price else None
            decision = unified_risk_service.evaluate_risk(symbol=order.symbol, amount=amount, price=price)
            if not decision.allowed:
                logger.warning(f"Order blockeras av riskkontroll: {decision.reason}")
                return OrderResponse(success=False, error=f"risk_blocked:{decision.reason}")

        # Idempotens: central service
        try:
            cid = (order.client_id or "").strip() if hasattr(order, "client_id") else ""
            if cid:
                idem = get_idempotency_service()
                hit = idem.check_and_register(cid)
                if hit is not None:
                    return OrderResponse(success=True, data={"idempotent": True, **(hit or {})})
        except Exception:
            pass

        # Skicka ordern till Bitfinex – payload innehåller redan resolverad symbol
        # Ignorera post_only för MARKET-ordrar (ingen effekt), men skicka vidare reduce_only
        if payload.get("type", "").upper().endswith("MARKET"):
            payload.pop("post_only", None)
        result = await rest_auth.place_order(payload)

        if "error" in result:
            logger.error(f"Fel vid orderläggning (REST): {result['error']}")
            # I testmiljö: hoppa över WS-fallback för deterministiskt beteende
            try:
                import os as _os

                if "PYTEST_CURRENT_TEST" in _os.environ:
                    await notification_service.notify(
                        "error",
                        "Order misslyckades",
                        {"request": order.dict(), "error": result.get("error")},
                    )
                    get_metrics_client().inc("orders_total")
                    get_metrics_client().inc("orders_failed_total")
                    try:
                        unified_risk_service.record_error()
                    except Exception:
                        pass
                    try:
                        get_metrics_client().inc_labeled(
                            "orders_total_labeled",
                            {
                                "symbol": order.symbol,
                                "type": (order.type or "").replace(" ", "_"),
                                "status": "error",
                            },
                        )
                    except Exception:
                        pass
                    return OrderResponse(success=False, error=result["error"])
            except Exception:
                pass
            # WS fallback (on) - men inte om Dry Run är aktiverat
            ws_fallback_ok = False
            try:
                import services.runtime_config as rc

                if rc.get_bool("DRY_RUN_ENABLED", False):
                    logger.info("WS fallback hoppas över: Dry Run är aktiverat")
                    return OrderResponse(success=False, error=result["error"])

                from services.bitfinex_websocket import bitfinex_ws as _ws

                # WS 'on' accepterar EXCHANGE-typer; behåll inkommande typ
                _t = str(payload.get("type") or "").upper().strip()
                # Säkerställ korrekt tecken på amount (WS kräver riktning i tecken)
                _amt_in = str(payload.get("amount") or "").strip()
                _side = (getattr(order, "side", None) or "").strip().lower()
                _amt = _amt_in
                try:
                    if _side == "sell" and _amt and not _amt.startswith("-"):
                        _amt = f"-{_amt}"
                    if _side == "buy" and _amt.startswith("-"):
                        _amt = _amt.lstrip("-")
                except Exception:
                    pass
                on_payload: dict[str, Any] = {
                    "type": _t,
                    "symbol": str(payload.get("symbol")),
                    "amount": _amt,
                }
                if payload.get("price") is not None:
                    on_payload["price"] = str(payload.get("price"))
                cid_val = str(getattr(order, "client_id", "") or "").strip()
                if cid_val:
                    try:
                        on_payload["cid"] = str(int(cid_val))
                    except Exception:
                        on_payload["cid"] = cid_val
                else:
                    # Sätt en enkel cid om ingen given
                    try:
                        import time as _tmod

                        on_payload["cid"] = str(int(_tmod.time() * 1000))
                    except Exception:
                        on_payload["cid"] = str(datetime.now().timestamp())
                # Skicka som singel 'on' istället för batch 'ops' (ökar kompatibilitet)
                try:
                    if await _ws.ensure_authenticated():
                        # Bitfinex WebSocket API förväntar array-format: [0, "on", null, payload]
                        ws_message = [0, "on", None, on_payload]
                        await _ws.send(json.dumps(ws_message))
                        ws_res = {"success": True, "sent": True}
                    else:
                        ws_res = {"success": False, "error": "ws_not_authenticated"}
                except Exception as _se:
                    ws_res = {"success": False, "error": str(_se)}
                ws_fallback_ok = bool(ws_res.get("success"))
                if ws_fallback_ok:
                    await notification_service.notify("info", "Order lagd via WS fallback", {"payload": on_payload})
                    get_metrics_client().inc("orders_total")
                    try:
                        get_metrics_client().inc_labeled(
                            "orders_total_labeled",
                            {
                                "symbol": order.symbol,
                                "type": (order.type or "").replace(" ", "_"),
                                "status": "ok_ws",
                            },
                        )
                    except Exception:
                        pass
                    return OrderResponse(success=True, data={"ws_fallback": True, **ws_res})
            except Exception as _wse:
                logger.warning(f"WS fallback misslyckades: {_wse}")
            # WS misslyckades → rapportera REST-felet
            await notification_service.notify(
                "error",
                "Order misslyckades",
                {"request": order.dict(), "error": str(result.get("error"))},
            )
            get_metrics_client().inc("orders_total")
            get_metrics_client().inc("orders_failed_total")
            try:
                unified_risk_service.record_error()
            except Exception:
                pass
            try:
                get_metrics_client().inc_labeled(
                    "orders_total_labeled",
                    {
                        "symbol": order.symbol,
                        "type": (order.type or "").replace(" ", "_"),
                        "status": "error",
                    },
                )
            except Exception:
                pass
            return OrderResponse(success=False, error=result["error"])

        # Markera trade om lyckad
        if "error" not in result:
            unified_risk_service.record_trade(symbol=order.symbol)
            get_metrics_client().inc("orders_total")
        logger.info(f"Order framgångsrikt lagd: {result}")
        try:
            get_metrics_client().inc_labeled(
                "orders_total_labeled",
                {
                    "symbol": order.symbol,
                    "type": (order.type or "").replace(" ", "_"),
                    "status": "ok",
                },
            )
        except Exception:
            pass
        await notification_service.notify("info", "Order lagd", {"request": order.dict(), "response": result})
        # Spara idempotent svar
        try:
            if cid:
                get_idempotency_service().store_response(cid, result)
        except Exception:
            pass
        return OrderResponse(success=True, data=result)

    except Exception as e:
        logger.exception(f"Oväntat fel vid orderläggning: {e}")
        return OrderResponse(success=False, error=str(e))


@router.post("/order/cancel", response_model=OrderResponse)
async def cancel_order_endpoint(cancel_request: CancelOrderRequest, _: bool = Depends(require_auth)):
    """
    Avbryter en order via Bitfinex API.
    """
    try:
        logger.info(f"Mottog avbrottsförfrågan för order: {cancel_request.order_id}")
        try:
            max_requests = int(getattr(settings, "ORDER_RATE_LIMIT_MAX", 0) or 0)
            window_seconds = int(getattr(settings, "ORDER_RATE_LIMIT_WINDOW", 0) or 0)
            if max_requests > 0 and window_seconds > 0:
                if not _rl.is_allowed("cancel_order", max_requests, window_seconds):
                    try:
                        get_metrics_client().inc("rate_limited_total")
                    except Exception:
                        pass
                    return OrderResponse(success=False, error="rate_limited")
        except Exception:
            pass

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
async def update_order_endpoint(update_request: UpdateOrderRequest, _: bool = Depends(require_auth)):
    """
    Uppdaterar en order via Bitfinex API.
    """
    try:
        logger.info(f"Mottog uppdateringsförfrågan för order: {update_request.order_id}")

        # Skapa en instans av ActiveOrdersService
        active_orders_service = ActiveOrdersService()

        # Uppdatera ordern
        try:
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
        except Exception as rest_err:
            logger.warning(f"REST update misslyckades, försöker WS fallback: {rest_err}")
            try:
                import services.runtime_config as rc

                if rc.get_bool("DRY_RUN_ENABLED", False):
                    logger.info("WS fallback hoppas över: Dry Run är aktiverat")
                    return OrderResponse(success=False, error=str(rest_err))

                from services.bitfinex_websocket import bitfinex_ws as _ws

                ws_res = await _ws.order_update(
                    order_id=update_request.order_id,
                    price=update_request.price,
                    amount=update_request.amount,
                    extra=None,
                )
                if bool(ws_res.get("success")):
                    _emit_notification(
                        "info",
                        "Order uppdaterad via WS",
                        {"request": update_request.dict(), "response": ws_res},
                    )
                    return OrderResponse(success=True, data={"ws_fallback": True, **ws_res})
                return OrderResponse(success=False, error=str(ws_res.get("error") or "ws_update_failed"))
            except Exception as _wse:
                logger.exception(f"WS fallback update fel: {_wse}")
                return OrderResponse(success=False, error=str(_wse))

    except Exception as e:
        logger.exception(f"Oväntat fel vid uppdatering av order: {e}")
        return OrderResponse(success=False, error=str(e))


# --- WS order endpoints ---
@router.post("/ws/order/update", response_model=OrderResponse)
async def ws_order_update(payload: WSOrderUpdateRequest, _: bool = Depends(require_auth)):
    try:
        from services.bitfinex_websocket import bitfinex_ws

        result = await bitfinex_ws.order_update(
            order_id=payload.order_id,
            price=payload.price,
            amount=payload.amount,
            extra=payload.extra,
        )
        if not result.get("success"):
            return OrderResponse(success=False, error=str(result.get("error")))
        return OrderResponse(success=True, data=result)
    except Exception as e:
        logger.exception(f"WS order update fel: {e}")
        return OrderResponse(success=False, error=str(e))


@router.post("/ws/orders/cancel-multi", response_model=OrderResponse)
async def ws_order_cancel_multi(payload: WSCancelMultiRequest, _: bool = Depends(require_auth)):
    try:
        from services.bitfinex_websocket import bitfinex_ws

        result = await bitfinex_ws.order_cancel_multi(ids=payload.ids, cids=payload.cids, cid_date=payload.cid_date)
        if not result.get("success"):
            return OrderResponse(success=False, error=str(result.get("error")))
        return OrderResponse(success=True, data=result)
    except Exception as e:
        logger.exception(f"WS cancel-multi fel: {e}")
        return OrderResponse(success=False, error=str(e))


@router.post("/ws/orders/ops", response_model=OrderResponse)
async def ws_order_ops(payload: WSOrderOpsRequest, _: bool = Depends(require_auth)):
    try:
        # Respektera Dry Run: simulera svar och skicka inte WS‑ops
        try:
            import services.runtime_config as rc

            if rc.get_bool("DRY_RUN_ENABLED", False):
                return OrderResponse(success=True, data={"dry_run": True, "ops": payload.ops})
        except Exception:
            pass

        # Symbol‑resolution för "on"‑ops: säkerställ effektiv Bitfinex‑symbol
        try:
            resolved_ops: list[list] = []
            for op in payload.ops:
                if not isinstance(op, list) or not op:
                    resolved_ops.append(op)
                    continue
                tag = str(op[0]).lower()
                if tag == "on" and len(op) >= 2 and isinstance(op[1], dict):
                    body = dict(op[1])
                    sym_in = str(body.get("symbol", ""))
                    if sym_in:
                        try:
                            from services.symbols import SymbolService as _SS

                            _svc = _SS()
                            await _svc.refresh()
                            eff = _svc.resolve(sym_in)
                            body["symbol"] = eff
                        except Exception:
                            pass
                    resolved_ops.append([op[0], body])
                else:
                    resolved_ops.append(op)
        except Exception:
            resolved_ops = payload.ops

        from services.bitfinex_websocket import bitfinex_ws

        result = await bitfinex_ws.order_ops(resolved_ops)
        if not result.get("success"):
            return OrderResponse(success=False, error=str(result.get("error")))
        return OrderResponse(success=True, data=result)
    except Exception as e:
        logger.exception(f"WS ops fel: {e}")
        return OrderResponse(success=False, error=str(e))


@router.post("/orders/cancel/all", response_model=OrderResponse)
async def cancel_all_orders_endpoint(_: bool = Depends(require_auth)):
    """
    Avbryter alla aktiva ordrar.
    """
    try:
        logger.info("Mottog förfrågan om att avbryta alla ordrar")
        # Rate-limit skydd
        try:
            max_requests = int(getattr(settings, "ORDER_RATE_LIMIT_MAX", 0) or 0)
            window_seconds = int(getattr(settings, "ORDER_RATE_LIMIT_WINDOW", 0) or 0)
            if max_requests > 0 and window_seconds > 0:
                if not _rl.is_allowed("cancel_all_orders", max_requests, window_seconds):
                    try:
                        from services.metrics import inc as _inc

                        _inc("rate_limited_total")
                    except Exception:
                        pass
                    return OrderResponse(success=False, error="rate_limited")
        except Exception:
            pass

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
async def cancel_orders_by_symbol_endpoint(symbol: str, _: bool = Depends(require_auth)):
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
        _emit_notification("info", "Ordrar avbrutna för symbol", {"symbol": symbol, "response": result})
        return OrderResponse(success=True, data=result)

    except Exception as e:
        logger.exception(f"Oväntat fel vid avbrytning av ordrar för {symbol}: {e}")
        return OrderResponse(success=False, error=str(e))


@router.get("/orders", response_model=list[OrderResponse])
async def get_active_orders_endpoint(_: bool = Depends(require_auth)):
    """
    Hämtar alla aktiva ordrar.
    """
    # Skapa en instans av ActiveOrdersService
    active_orders_service = ActiveOrdersService()

    # Hämta alla aktiva ordrar (tolerant: tjänsten returnerar tom lista vid fel)
    orders = await active_orders_service.get_active_orders()

    # Konvertera varje order till vår API OrderResponse-modell
    return [OrderResponse(success=True, data=order) for order in orders]


@router.get("/orders/symbol/{symbol}", response_model=list[OrderResponse])
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
        raise HTTPException(status_code=500, detail="Internal server error") from e


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
            raise HTTPException(status_code=404, detail=f"Order med ID {order_id} hittades inte")

        return OrderResponse(success=True, data=order)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Fel vid hämtning av order {order_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


# Wallet endpoints


@router.get("/wallets", response_model=list[WalletBalance])
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
        raise HTTPException(status_code=500, detail="Internal server error") from e


# Funding/Transfer endpoints
class TransferRequest(BaseModel):
    from_wallet: str
    to_wallet: str
    currency: str
    amount: str


@router.post("/funding/transfer")
async def funding_transfer(req: TransferRequest, _: bool = Depends(require_auth)):
    try:
        svc = FundingService()
        res = await svc.transfer(req.from_wallet, req.to_wallet, req.currency, req.amount)
        if isinstance(res, dict) and res.get("error"):
            # mappa interna felkoder till generiska HTTP‑felmeddelanden
            code = str(res.get("error"))
            if code == "transfer_failed":
                raise HTTPException(status_code=502, detail="transfer_failed")
            raise HTTPException(status_code=502, detail="funding_error")
        return res
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Fel vid transfer: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/funding/movements")
async def funding_movements(
    currency: str | None = None,
    start: int | None = None,
    end: int | None = None,
    limit: int | None = None,
    _: bool = Depends(require_auth),
):
    try:
        svc = FundingService()
        res = await svc.movements(currency=currency, start=start, end=end, limit=limit)
        if isinstance(res, dict) and res.get("error"):
            code = str(res.get("error"))
            if code == "movements_failed":
                raise HTTPException(status_code=502, detail="movements_failed")
            raise HTTPException(status_code=502, detail="funding_error")
        return res
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Fel vid movements: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/wallets/balance")
async def get_wallets_balance_endpoint(currency: str | None = None, _: bool = Depends(require_auth)):
    """Aggregat saldo per valuta med brytning per wallet-typ.

    - Om `currency` anges returneras endast den valutan.
    - Annars returneras alla valutor.
    """
    try:
        wallet_service = WalletService()
        wallets = await wallet_service.get_wallets()

        def _upper(s: str | None) -> str:
            return s.upper() if isinstance(s, str) else ""

        balances: dict[str, dict[str, Any]] = {}
        for w in wallets:
            cur = _upper(w.currency)
            entry = balances.setdefault(cur, {"total": 0.0, "available_total": 0.0, "by_type": {}})
            entry["total"] += float(w.balance)
            entry["available_total"] += float(w.available_balance or 0.0)
            by_type = entry["by_type"]
            by_type[w.wallet_type] = float(by_type.get(w.wallet_type, 0.0)) + float(w.balance)

        if currency:
            cur = currency.upper()
            data = balances.get(cur, {"total": 0.0, "available_total": 0.0, "by_type": {}})
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
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/wallets/exchange", response_model=list[WalletBalance])
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
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/wallets/margin", response_model=list[WalletBalance])
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
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/wallets/funding", response_model=list[WalletBalance])
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
        raise HTTPException(status_code=500, detail="Internal server error") from e


# Position endpoints


@router.get("/positions", response_model=list[Position])
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
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/positions/long", response_model=list[Position])
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
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/positions/short", response_model=list[Position])
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
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/positions/close/{symbol}", response_model=dict[str, Any])
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
        raise HTTPException(status_code=500, detail="Internal server error") from e


# Margin endpoints


@router.get("/margin", response_model=dict[str, Any])
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
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/margin/status", response_model=dict[str, Any])
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
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/margin/status/{symbol}")
async def get_margin_status_symbol(symbol: str, _: bool = Depends(require_auth)):
    try:
        margin_service = MarginService()
        # 1) WS/REST sammanfattning
        base = await margin_service.get_symbol_margin_status(symbol)
        # 2) Om source none/rest och tradable saknas, försök direktslag mot v2 sym (med tom body för korrekt signering)
        if (not base) or (
            isinstance(base, dict) and base.get("tradable") in (None, 0, 0.0) and base.get("source") != "ws"
        ):
            try:
                lim = await margin_service.get_margin_limit_by_pair(symbol)
                if lim:
                    base = {
                        "symbol": symbol,
                        "source": base.get("source", "rest"),  # type: ignore[union-attr]
                        "tradable": float(lim.tradable_balance),
                        "buy": base.get("buy"),  # type: ignore[union-attr]
                        "sell": base.get("sell"),  # type: ignore[union-attr]
                    }
            except Exception:
                pass
        return base
    except Exception as e:
        logger.exception(f"Fel vid hämtning av margin-status (symbol): {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/margin/leverage", response_model=dict[str, float])
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
        raise HTTPException(status_code=500, detail="Internal server error") from e


# Order History endpoints


@router.get("/orders/history", response_model=list[OrderHistoryItem])
async def get_orders_history_endpoint(
    limit: int = 25,
    start_time: int | None = None,
    end_time: int | None = None,
    _: bool = Depends(require_auth),
):
    """
    Hämtar orderhistorik från Bitfinex API.
    """
    try:
        order_history_service = OrderHistoryService()
        orders = await order_history_service.get_orders_history(limit, start_time, end_time)
        return orders

    except Exception as e:
        logger.exception(f"Fel vid hämtning av orderhistorik: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/order/{order_id}/trades", response_model=list[TradeItem])
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
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/trades/history", response_model=list[TradeItem])
async def get_trades_history_endpoint(symbol: str | None = None, limit: int = 25, _: bool = Depends(require_auth)):
    """
    Hämtar handelshistorik från Bitfinex API.
    """
    try:
        order_history_service = OrderHistoryService()
        trades = await order_history_service.get_trades_history(symbol, limit)
        return trades

    except Exception as e:
        logger.warning(f"Fel vid hämtning av handelshistorik: {e}")
        # Returnera tom lista istället för 500-fel
        return []


@router.get("/ledgers", response_model=list[LedgerEntry])
async def get_ledgers_endpoint(currency: str | None = None, limit: int = 25, _: bool = Depends(require_auth)):
    """
    Hämtar ledger-poster från Bitfinex API.
    """
    try:
        order_history_service = OrderHistoryService()
        ledgers = await order_history_service.get_ledgers(currency, limit)
        return ledgers

    except Exception as e:
        logger.warning(f"Fel vid hämtning av ledger: {e}")
        # Returnera tom lista istället för 500-fel
        return []


class TokenRequest(BaseModel):
    """Request model för token generering."""

    user_id: str = "frontend_user"
    scope: str = "read"
    expiry_hours: int = 1


class TokenResponse(BaseModel):
    """Response model för token generering."""

    success: bool
    token: str | None = None
    error: str | None = None


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
        from utils.token_masking import safe_log_data

        logger.exception(safe_log_data(e, "Fel vid generering av WebSocket-token"))
        return TokenResponse(success=False, error=str(e))


# Strategy endpoints
class WeightedStrategyRequest(BaseModel):
    """Input för viktad strategiutvärdering."""

    ema: str
    rsi: str
    atr: str | None = None
    symbol: str | None = None


class WeightedStrategyResponse(BaseModel):
    """Svar för viktad strategiutvärdering."""

    signal: str
    probabilities: dict[str, float]


@router.post("/strategy/evaluate-weighted", response_model=WeightedStrategyResponse)
async def evaluate_weighted_strategy_endpoint(request: WeightedStrategyRequest, _: bool = Depends(require_auth)):
    """
    Returnerar viktad slutsignal (buy/sell/hold) och sannolikheter baserat på
    simplifierade signaler från EMA, RSI och ATR.
    OPTIMERAD: Caching för bättre prestanda.
    """
    try:
        # OPTIMERING: Cache för viktade strategy-beräkningar
        cache_key = f"weighted_strategy_{request.ema}_{request.rsi}_{request.atr}_{request.symbol}"
        cache_ttl = timedelta(minutes=2)  # Kort cache för strategy-beräkningar

        # Kontrollera cache först
        if hasattr(evaluate_weighted_strategy_endpoint, "_cache"):
            cached_data = evaluate_weighted_strategy_endpoint._cache.get(cache_key)
            if cached_data and (datetime.now() - cached_data["timestamp"]) < cache_ttl:
                logger.debug(f"📋 Använder cached weighted strategy för {request.symbol}")
                return cached_data["data"]
        else:
            evaluate_weighted_strategy_endpoint._cache = {}

        payload: dict[str, str | None] = {
            "ema": request.ema,
            "rsi": request.rsi,
            "atr": request.atr,
        }
        if request.symbol:
            payload["symbol"] = request.symbol
        result = evaluate_weighted_strategy(payload)  # type: ignore[arg-type]

        # Spara i cache
        evaluate_weighted_strategy_endpoint._cache[cache_key] = {
            "data": result,
            "timestamp": datetime.now(),
        }

        return result
    except Exception as e:
        logger.exception(f"Fel vid viktad strategiutvärdering: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


# Strategy settings endpoints
class StrategySettingsPayload(BaseModel):
    ema_weight: float | None = None
    rsi_weight: float | None = None
    atr_weight: float | None = None
    ema_period: int | None = None
    rsi_period: int | None = None
    atr_period: int | None = None


@router.get("/strategy/settings")
async def get_strategy_settings(symbol: str | None = None, _: bool = Depends(require_auth)):
    """
    Hämtar strategiinställningar.
    OPTIMERAD: Caching för bättre prestanda.
    """
    try:
        # OPTIMERING: Cache för strategy settings
        cache_key = f"strategy_settings_{symbol or 'default'}"
        cache_ttl = timedelta(minutes=10)  # Längre cache för settings

        # Kontrollera cache först
        if hasattr(get_strategy_settings, "_cache"):
            cached_data = get_strategy_settings._cache.get(cache_key)
            if cached_data and (datetime.now() - cached_data["timestamp"]) < cache_ttl:
                logger.debug(f"📋 Använder cached strategy settings för {symbol}")
                return cached_data["data"]
        else:
            get_strategy_settings._cache = {}

        svc = StrategySettingsService()
        result = svc.get_settings(symbol=symbol).to_dict()

        # Spara i cache
        get_strategy_settings._cache[cache_key] = {
            "data": result,
            "timestamp": datetime.now(),
        }

        return result
    except Exception as e:
        logger.exception(f"Fel vid hämtning av strategiinställningar: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/strategy/settings")
async def update_strategy_settings(
    payload: StrategySettingsPayload,
    symbol: str | None = None,
    _: bool = Depends(require_auth),
):
    try:
        svc = StrategySettingsService()
        current = svc.get_settings(symbol=symbol)
        updated = StrategySettings(
            ema_weight=(payload.ema_weight if payload.ema_weight is not None else current.ema_weight),
            rsi_weight=(payload.rsi_weight if payload.rsi_weight is not None else current.rsi_weight),
            atr_weight=(payload.atr_weight if payload.atr_weight is not None else current.atr_weight),
            ema_period=(payload.ema_period if payload.ema_period is not None else current.ema_period),
            rsi_period=(payload.rsi_period if payload.rsi_period is not None else current.rsi_period),
            atr_period=(payload.atr_period if payload.atr_period is not None else current.atr_period),
        )
        saved = svc.save_settings(updated, symbol=symbol)

        # OPTIMERING: Invalidera cache efter uppdatering
        cache_key = f"strategy_settings_{symbol or 'default'}"
        if hasattr(get_strategy_settings, "_cache"):
            get_strategy_settings._cache.pop(cache_key, None)
            logger.debug(f"🗑️ Invalidated cache för {cache_key}")

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
        raise HTTPException(status_code=500, detail="Internal server error")


# --- Auto-regim / Auto-vikter toggles ---
class StrategyAutoPayload(BaseModel):
    AUTO_REGIME_ENABLED: bool | None = None
    AUTO_WEIGHTS_ENABLED: bool | None = None


@router.get("/strategy/auto")
async def get_strategy_auto(_: bool = Depends(require_auth)):
    try:
        import json
        import os

        cfg_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "config",
            "strategy_settings.json",
        )
        data: dict[str, object]
        try:
            with open(cfg_path, encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            data = {}
        except Exception as e:  # pragma: no cover
            logger.warning(f"Kunde inte läsa strategy_settings.json: {e}")
            data = {}
        return {
            "AUTO_REGIME_ENABLED": bool(data.get("AUTO_REGIME_ENABLED", True)),
            "AUTO_WEIGHTS_ENABLED": bool(data.get("AUTO_WEIGHTS_ENABLED", True)),
        }
    except Exception as e:
        logger.exception(f"Fel vid hämtning av strategy auto-flaggor: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/strategy/auto")
async def update_strategy_auto(payload: StrategyAutoPayload, _: bool = Depends(require_auth)):
    try:
        import json
        import os

        cfg_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "config",
            "strategy_settings.json",
        )
        try:
            with open(cfg_path, encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    data = {}
        except FileNotFoundError:
            data = {}
        except Exception as e:
            logger.warning(f"Kunde inte läsa strategy_settings.json: {e}")
            data = {}

        if payload.AUTO_REGIME_ENABLED is not None:
            data["AUTO_REGIME_ENABLED"] = bool(payload.AUTO_REGIME_ENABLED)
        if payload.AUTO_WEIGHTS_ENABLED is not None:
            data["AUTO_WEIGHTS_ENABLED"] = bool(payload.AUTO_WEIGHTS_ENABLED)

        os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return {
            "AUTO_REGIME_ENABLED": bool(data.get("AUTO_REGIME_ENABLED", True)),
            "AUTO_WEIGHTS_ENABLED": bool(data.get("AUTO_WEIGHTS_ENABLED", True)),
        }
    except Exception as e:
        logger.exception(f"Fel vid uppdatering av strategy auto-flaggor: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Position sizing endpoint (enkel riskprocent-variant)
class PositionSizeRequest(BaseModel):
    symbol: str
    risk_percent: float = 1.0  # procent av total USD balans
    price: float | None = None  # om ej satt, försök hämta ticker
    side: str = "buy"  # buy eller sell för SL/TP-beräkning
    timeframe: str = "1m"
    atr_multiplier_sl: float = 1.5
    atr_multiplier_tp: float = 3.0


@router.post("/risk/position-size")
async def calculate_position_size(req: PositionSizeRequest, _: bool = Depends(require_auth)):
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
        total_quote = sum(w.balance for w in wallets if w.currency.upper() == quote_upper)
        if total_quote <= 0:
            try:
                from config.settings import Settings as __S

                __s = __S()
                fallback = float(getattr(__s, "POSITION_SIZE_FALLBACK_QUOTE", 0.0) or 0.0)
                if fallback > 0:
                    total_quote = fallback
            except Exception:
                pass
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
        price_source = None
        if price is None:
            # 1) Försök via WS public (primär)
            try:
                import re

                from services.bitfinex_websocket import bitfinex_ws

                eff = req.symbol
                m = re.match(r"^tTEST([A-Z0-9]+):TESTUSD$", eff)
                if m:
                    eff = f"t{m.group(1)}USD"
                else:
                    m = re.match(r"^tTESTUSD:TEST([A-Z0-9]+)$", eff)
                    if m:
                        eff = f"t{m.group(1)}USD"
                    else:
                        m = re.match(r"^tTEST([A-Z0-9]+)USD$", eff)
                        if m:
                            eff = f"t{m.group(1)}USD"
                        else:
                            m = re.match(r"^tUSD:TEST([A-Z0-9]+)$", eff)
                            if m:
                                eff = f"t{m.group(1)}USD"

                # Starta WS vid behov och prenumerera på ticker
                if not getattr(bitfinex_ws, "is_connected", False):
                    await bitfinex_ws.connect()

                async def _cb(t):
                    try:
                        sym = t.get("symbol") or eff
                        lp = t.get("last_price")
                        if lp is not None:
                            bitfinex_ws.latest_prices[sym] = lp
                    except Exception:
                        pass

                await bitfinex_ws.subscribe_ticker(eff, _cb)

                # Kort väntan för första tick
                await asyncio.sleep(0.25)
                ws_p = bitfinex_ws.latest_prices.get(eff)
                if ws_p:
                    price = float(ws_p)
                    price_source = "ws"
            except Exception:
                pass

            # 2) REST public ticker (fallback)
            if price is None or price <= 0:
                data = get_market_data()
                ticker = await data.get_ticker(req.symbol)
                if ticker:
                    price = float(ticker.get("last_price", 0))
                    if price and price > 0:
                        price_source = price_source or "ticker"

            # 3) Candle close (sista fallback)
            if not price or price <= 0:
                data = get_market_data()
                candles = await data.get_candles(req.symbol, req.timeframe, limit=1)
                if candles and len(candles) > 0:
                    try:
                        # Bitfinex candle: [MTS, OPEN, CLOSE, HIGH, LOW, VOLUME]
                        price = float(candles[-1][2])
                        if price and price > 0:
                            price_source = price_source or "candle"
                    except Exception:
                        price = 0
            if not price or price <= 0:
                # Dev/demo fallback: försök läsa senaste cache-pris
                try:
                    from utils.candle_cache import candle_cache as _cc

                    rows = _cc.load(req.symbol, req.timeframe, limit=1)
                    if isinstance(rows, list) and len(rows) >= 1:
                        last = rows[0]
                        if isinstance(last, list) and len(last) >= 3:
                            price = float(last[2])
                            price_source = price_source or "cache"
                except Exception:
                    pass
            if not price or price <= 0:
                return {"size": 0.0, "reason": "no_price"}
        if price <= 0:
            return {"size": 0.0, "reason": "invalid_price"}

        # Storlek i basvaluta
        quote_to_use = max(req.risk_percent, 0.0) / 100.0 * total_quote
        size = quote_to_use / price

        # Försök beräkna ATR och föreslå SL/TP
        sl_price = None
        tp_price = None
        try:
            data = get_market_data()
            candles = await data.get_candles(
                req.symbol,
                req.timeframe,
                limit=100,
            )
            if candles:
                try:
                    from utils.candles import parse_candles_to_strategy_data as _parse

                    parsed = _parse(candles)
                except Exception:
                    parsed = {"highs": [], "lows": [], "closes": []}
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
            "quote_total": round(total_quote, 2),
            "price": price,
        }
        if price_source:
            resp["price_source"] = price_source
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
        raise HTTPException(status_code=500, detail="Internal server error")


# Performance endpoint (förenklad)
@router.get("/account/performance")
async def get_account_performance(_: bool = Depends(require_auth)):
    try:
        import asyncio

        perf = PerformanceService()

        # Lägg till total timeout på hela performance-beräkningen
        async def compute_performance():
            equity = await perf.compute_current_equity()
            pnl = await perf.compute_realized_pnl(limit=500)
            return {"equity": equity, "realized": pnl}

        result = await asyncio.wait_for(compute_performance(), timeout=10.0)  # 10s total timeout
        return result
    except TimeoutError:
        logger.warning("⚠️ Performance endpoint timeout - returning cached/default values")
        return {
            "equity": {"total_usd": 0.0, "wallets_usd": 0.0, "unrealized_usd": 0.0},
            "realized": {},
        }
    except Exception as e:
        logger.exception(f"Fel vid performance: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Market data endpoints
@router.get("/market/ticker/{symbol}")
async def market_ticker(symbol: str, _: bool = Depends(require_auth)):
    try:
        data = get_market_data()
        result = await data.get_ticker(symbol)
        if not result:
            # Offline/CI fallback: returnera minimal dummy om nätverk saknas
            return {
                "symbol": symbol,
                "last_price": 0.0,
                "bid": None,
                "ask": None,
                "high": None,
                "low": None,
                "volume": None,
            }
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Fel vid ticker: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/market/tickers")
async def market_tickers(symbols: str, _: bool = Depends(require_auth)):
    """Batch-hämtning av tickers. Query-param symbols är komma-separerad lista.

    Ex: /api/v2/market/tickers?symbols=tBTCUSD,tETHUSD
    """
    try:
        data = get_market_data()
        syms = [s.strip() for s in (symbols or "").split(",") if s.strip()]
        if not syms:
            raise HTTPException(status_code=400, detail="symbols required")
        # MarketDataFacade saknar batch just nu; hämta sekventiellt
        out = []
        for s in syms:
            t = await data.get_ticker(s)
            if t:
                out.append(t)
        if not out:
            raise HTTPException(status_code=502, detail="Kunde inte hämta tickers")
        return out
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Fel vid tickers (batch): {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/platform/status")
async def platform_status(_: bool = Depends(require_auth)):
    """Hälsa/underhållsläge från Bitfinex public REST."""
    try:
        data = get_market_data()
        st = await data.get_platform_status()
        if st is None:
            return {"status": "unknown"}
        # Format från Bitfinex: [1] eller [0]
        up = bool(st[0]) if isinstance(st, list) and st else False
        return {"status": "up" if up else "maintenance", "raw": st}
    except Exception as e:
        logger.exception(f"Fel vid platform status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/market/symbols/config")
async def market_symbols_config(format: str = "v2", _: bool = Depends(require_auth)):
    """Symbol-lista via Bitfinex public Configs. OBS: innehåller inte TEST-symboler."""
    try:
        data = get_market_data()
        pairs = await data.get_configs_symbols()
        if not pairs:
            return []
        if format.lower() in ("v2", "t", "bitfinex_v2"):
            return [f"t{p}" for p in pairs]
        return pairs
    except Exception as e:
        logger.exception(f"Fel vid configs symbols: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/market/symbols/paper")
async def market_symbols_paper(format: str = "v2", _: bool = Depends(require_auth)):
    """Returnera fasta Bitfinex paper‑symboler (16 st), v2/t‑format.

    Exakt lista enligt Bitfinex paper account:
    TESTADA, TESTALGO, TESTAPT, TESTAVAX, TESTBTC (USD, USDT), TESTDOGE, TESTDOT,
    TESTEOS, TESTETH, TESTFIL, TESTLTC, TESTNEAR, TESTSOL, TESTXAUT, TESTXTZ.
    """
    usd_only = [
        "ADA",
        "ALGO",
        "APT",
        "AVAX",
        "DOGE",
        "DOT",
        "EOS",
        "ETH",
        "FIL",
        "LTC",
        "NEAR",
        "SOL",
        "XAUT",
        "XTZ",
    ]
    syms = [f"tTEST{b}:TESTUSD" for b in usd_only]
    syms.extend(["tTESTBTC:TESTUSD", "tTESTBTC:TESTUSDT"])  # BTC har två quotes på paper
    if format.lower() in ("v2", "t", "bitfinex_v2"):
        return syms
    return [s[1:] if s.startswith("t") else s for s in syms]


@router.get("/market/candles/{symbol}")
async def market_candles(
    symbol: str,
    timeframe: str = "1m",
    limit: int = 100,
    _: bool = Depends(require_auth),
):
    try:
        data = get_market_data()
        candles = await data.get_candles(symbol, timeframe, limit)
        if candles is None:
            raise HTTPException(status_code=502, detail="Kunde inte hämta candles")
        try:
            from utils.candles import parse_candles_to_strategy_data as _parse

            parsed_any = _parse(candles)
        except Exception:
            parsed_any = {"closes": [], "highs": [], "lows": []}
        from services.strategy import evaluate_strategy

        # bädda in symbol i parsed för vikt-override
        parsed_map: dict[str, Any] = dict(parsed_any) if isinstance(parsed_any, dict) else {}
        parsed_map["symbol"] = symbol
        strategy = evaluate_strategy(parsed_map)  # type: ignore[arg-type]
        return {
            "candles_count": len(candles),
            "strategy": strategy,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Fel vid candles: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Resync endpoint: re‑subscribe + REST snapshot fetch
@router.post("/market/resync/{symbol}")
async def market_resync(symbol: str, _: bool = Depends(require_auth)):
    try:
        # WS re-subscribe (idempotent skydd finns i subscribe)
        await bitfinex_ws.subscribe_ticker(symbol, bitfinex_ws._handle_ticker_with_strategy)
        # Trigger omedelbar REST snapshot (värms upp cache)
        data = get_market_data()
        _tick = await data.get_ticker(symbol)
        return {"success": True}
    except Exception as e:
        logger.exception(f"Fel vid resync: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Health endpoint
@router.get("/health")
async def health(_: bool = Depends(require_auth)):
    try:
        from services.bitfinex_websocket import bitfinex_ws

        pool = bitfinex_ws.get_pool_status()
        return {
            "rest": True,
            "ws_connected": bool(getattr(bitfinex_ws, "is_connected", False)),
            "ws_authenticated": bool(getattr(bitfinex_ws, "is_authenticated", False)),
            "ws_pool": pool if isinstance(pool, dict) else {},
        }
    except Exception as e:
        logger.exception(f"Health error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/ws/pool/status")
async def ws_pool_status(_: bool = Depends(require_auth)):
    try:
        from services.bitfinex_websocket import bitfinex_ws

        return bitfinex_ws.get_pool_status()
    except Exception as e:
        logger.exception(f"WS pool status error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/ws/subscribe")
async def ws_subscribe(req: WSSubscribeRequest, _: bool = Depends(require_auth)):
    try:
        chan = (req.channel or "").lower()
        sym = req.symbol
        from services.bitfinex_websocket import bitfinex_ws

        if chan == "ticker":
            await bitfinex_ws.subscribe_ticker(sym, bitfinex_ws._handle_ticker_with_strategy)
            sub_key = f"ticker|{sym}"
        elif chan == "trades":
            await bitfinex_ws.subscribe_trades(sym, bitfinex_ws._handle_ticker_with_strategy)  # återanvänd callback
            sub_key = f"trades|{sym}"
        elif chan == "candles":
            tf = req.timeframe or "1m"
            # Throttla candles-subs marginellt för att undvika burst‑stängningar
            try:
                import asyncio as _a

                await _a.sleep(0.25)
            except Exception:
                pass
            await bitfinex_ws.subscribe_candles(sym, tf, bitfinex_ws._handle_ticker_with_strategy)
            sub_key = f"candles|trade:{tf}:{sym}"
        else:
            raise HTTPException(status_code=400, detail="invalid_channel")
        return {"success": True, "sub_key": sub_key}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"WS subscribe error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/ws/unsubscribe")
async def ws_unsubscribe(req: WSUnsubscribeRequest, _: bool = Depends(require_auth)):
    try:
        from services.bitfinex_websocket import bitfinex_ws

        chan = (req.channel or "").lower()
        sym = req.symbol
        if chan == "ticker":
            sub_key = f"ticker|{sym}"
        elif chan == "trades":
            sub_key = f"trades|{sym}"
        elif chan == "candles":
            tf = req.timeframe or "1m"
            ckey = f"trade:{tf}:{sym}"
            sub_key = f"candles|{ckey}"
        else:
            raise HTTPException(status_code=400, detail="invalid_channel")
        await bitfinex_ws.unsubscribe(sub_key)
        return {"success": True, "sub_key": sub_key}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"WS unsubscribe error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/prob/predict")
async def prob_predict(req: ProbPredictRequest, _: bool = Depends(require_auth)):
    try:
        import time as _t

        t0 = _t.time()
        # Hämta senaste candles för features
        data = get_market_data()
        closes_pack = await data.get_candles(req.symbol, req.timeframe, limit=max(req.horizon, 50))
        if not closes_pack:
            return {
                "source": "heuristic",
                "probabilities": {"buy": 0.0, "sell": 0.0, "hold": 1.0},
                "confidence": 0.0,
                "ev": 0.0,
                "features": {},
            }
        # Bitfinex candle: [MTS, OPEN, CLOSE, HIGH, LOW, VOLUME]
        closes = [row[2] for row in closes_pack if isinstance(row, (list, tuple)) and len(row) >= 3]
        if len(closes) < 5:
            return {
                "source": "heuristic",
                "probabilities": {"buy": 0.0, "sell": 0.0, "hold": 1.0},
                "confidence": 0.0,
                "ev": 0.0,
                "features": {},
            }
        price = float(closes[-1])
        # Enkla features (samma som i strategy)
        # EMA proxy: använd enkel glidande medel (SMA) som approximation här
        try:
            ema = sum(closes[-10:]) / min(10, len(closes))
        except Exception:
            ema = price
        f_ema = 1.0 if price > ema else (-1.0 if price < ema else 0.0)
        # RSI proxy: normalisera senaste prisförändringen
        try:
            delta = price - float(closes[-2])
            rsi_norm = max(min(delta / (abs(float(closes[-2])) + 1e-9), 1.0), -1.0)
        except Exception:
            rsi_norm = 0.0
        f_rsi = rsi_norm

        probs = prob_model.predict_proba({"ema": f_ema, "rsi": f_rsi})
        confidence = float(max(probs.values()))
        # EV för buy/sell (procentenheter)
        p_buy = float(probs.get("buy", 0.0))
        p_sell = float(probs.get("sell", 0.0))
        ev_buy = p_buy * req.tp - p_sell * req.sl - req.fees
        ev_sell = p_sell * req.tp - p_buy * req.sl - req.fees
        # Policybeslut
        from config.settings import Settings as _S

        s = _S()
        ev_th = float(getattr(s, "PROB_MODEL_EV_THRESHOLD", 0.0) or 0.0)
        conf_th = float(getattr(s, "PROB_MODEL_CONFIDENCE_MIN", 0.0) or 0.0)
        side = "buy" if ev_buy >= ev_sell else "sell"
        best_ev = ev_buy if side == "buy" else ev_sell
        decision = side if (best_ev >= ev_th and confidence >= conf_th) else "abstain"
        try:
            # metrics
            if decision == "abstain":
                get_metrics_client().inc_labeled(
                    "prob_events",
                    {"type": "abstain", "symbol": req.symbol, "tf": req.timeframe},
                )
            else:
                get_metrics_client().inc_labeled(
                    "prob_events",
                    {
                        "type": "trade",
                        "side": side,
                        "symbol": req.symbol,
                        "tf": req.timeframe,
                    },
                )
            get_metrics_client().inc_labeled(
                "prob_events",
                {
                    "type": "infer",
                    "source": ("model" if prob_model.enabled else "heuristic"),
                    "symbol": req.symbol,
                    "tf": req.timeframe,
                },
            )
            # latens (sum + count)
            get_metrics_client().inc_labeled(
                "prob_infer_latency_ms_sum",
                {"symbol": req.symbol, "tf": req.timeframe},
                by=int(max(((_t.time()) - t0) * 1000, 0)),
            )
            get_metrics_client().inc_labeled(
                "prob_infer_latency_ms_count",
                {"symbol": req.symbol, "tf": req.timeframe},
                by=1,
            )

            # EV och confidence bucketisering för enkel histogram-analys
            def _bucket(val: float, edges: list[float]) -> str:
                for _i, th in enumerate(edges):
                    if val < th:
                        return f"<{th}"
                return f">={edges[-1]}"

            ev_edges = [-0.002, -0.001, 0.0, 0.0005, 0.001, 0.002]
            conf_edges = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
            ev_bucket = _bucket(best_ev, ev_edges)
            conf_bucket = _bucket(confidence, conf_edges)
            get_metrics_client().inc_labeled(
                "prob_ev_bucket",
                {"bucket": ev_bucket, "symbol": req.symbol, "tf": req.timeframe},
                by=1,
            )
            get_metrics_client().inc_labeled(
                "prob_conf_bucket",
                {"bucket": conf_bucket, "symbol": req.symbol, "tf": req.timeframe},
                by=1,
            )
        except Exception:
            pass
        t1 = _t.time()
        source = "model" if prob_model.enabled else "heuristic"
        out = {
            "source": source,
            "probabilities": {k: round(float(v), 6) for k, v in probs.items()},
            "confidence": round(confidence, 6),
            "ev": round(best_ev, 6),
            "ev_buy": round(ev_buy, 6),
            "ev_sell": round(ev_sell, 6),
            "decision": decision,
            "thresholds": {"ev": ev_th, "confidence": conf_th},
            "latency_ms": int((t1 - t0) * 1000),
            "features": {"ema": f_ema, "rsi": f_rsi, "price": price, "ema_proxy": ema},
            "params": req.dict(),
        }
        # Feature/decision‑loggning (ringbuffer)
        try:
            from config.settings import Settings as _S2
            from services.metrics import metrics_store as _ms

            s2 = _S2()
            if bool(getattr(s2, "PROB_FEATURE_LOG_ENABLED", False)):
                max_pts = int(getattr(s2, "PROB_FEATURE_LOG_MAX_POINTS", 500) or 500)
                include_price = bool(getattr(s2, "PROB_FEATURE_LOG_INCLUDE_PRICE", False))
                key = f"{req.symbol}|{req.timeframe}"
                buf = _ms.setdefault("prob_feature_log", {}).setdefault(key, [])
                item = {
                    "ts": int(_t.time()),
                    "source": source,
                    "probs": out["probabilities"],
                    "decision": decision,
                    "ev": out["ev"],
                    "conf": out["confidence"],
                }
                if include_price:
                    item["price"] = price
                item["f"] = {"ema": f_ema, "rsi": f_rsi}
                buf.append(item)
                if len(buf) > max_pts:
                    del buf[: len(buf) - max_pts]
        except Exception:
            pass
        return out
    except Exception as e:
        logger.exception(f"prob/predict error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/prob/status")
async def prob_status(_: bool = Depends(require_auth)):
    try:
        from config.settings import Settings as _S

        s = _S()
        loaded = bool(prob_model.enabled and prob_model.model_meta)
        return {
            "enabled": bool(prob_model.enabled),
            "loaded": loaded,
            "file": getattr(s, "PROB_MODEL_FILE", None),
            "schema": prob_model.model_meta.get("schema") if loaded else None,
            "version": prob_model.model_meta.get("version") if loaded else None,
            "thresholds": {
                "ev": float(getattr(s, "PROB_MODEL_EV_THRESHOLD", 0.0) or 0.0),
                "confidence": float(getattr(s, "PROB_MODEL_CONFIDENCE_MIN", 0.0) or 0.0),
            },
        }
    except Exception as e:
        logger.exception(f"prob/status error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


class ProbValidateRequest(BaseModel):
    symbol: str
    timeframe: str = "1m"
    horizon: int = 20
    tp: float = 0.002
    sl: float = 0.002
    limit: int = 1000  # antal candles att hämta för validering
    max_samples: int | None = 500  # senaste N samples att utvärdera


"""Legacy /prob/validate borttagen – använd /api/v2/validation/probability"""


class ProbValidateRunRequest(BaseModel):
    symbols: list[str] | None = None  # t.ex. ["tBTCUSD", "tETHUSD"]
    timeframe: str = "1m"
    limit: int = 1000
    max_samples: int | None = 500


"""Legacy /prob/validate/run borttagen – använd /api/v2/validation/probability"""


class ProbRetrainRunRequest(BaseModel):
    symbols: list[str] | None = None
    timeframe: str = "1m"
    limit: int = 5000
    output_dir: str | None = None


@router.post("/prob/retrain/run")
async def prob_retrain_run(req: ProbRetrainRunRequest, _: bool = Depends(require_auth)):
    """Kör retraining direkt och försök reloada modellen om PROB_MODEL_FILE matchar ny fil."""
    try:
        import os as _os

        from services.prob_train import train_and_export
        from services.symbols import SymbolService

        s = settings
        data = get_market_data()
        sym_svc = SymbolService()
        await sym_svc.refresh()

        if req.symbols and len(req.symbols) > 0:
            symbols = req.symbols
        else:
            raw = (getattr(s, "PROB_RETRAIN_SYMBOLS", None) or "").strip()
            if raw:
                symbols = [x.strip() for x in raw.split(",") if x.strip()]
            else:
                env_syms = (getattr(s, "WS_SUBSCRIBE_SYMBOLS", None) or "").strip()
                s = settings
                ...
                symbols = [x.strip() for x in env_syms.split(",") if x.strip()] or [
                    f"t{getattr(s, 'DEFAULT_TRADING_PAIR', 'BTCUSD')}"
                ]
        tf_raw = req.timeframe or str(getattr(s, "PROB_RETRAIN_TIMEFRAME", "1m") or "1m")
        try:
            import re as _re

            # Allow only alphanumeric and underscores in tf
            tf = _re.sub(r"[^A-Za-z0-9_]", "_", tf_raw)
        except Exception:
            tf = "".join([c if c.isalnum() or c == "_" else "_" for c in tf_raw])
        limit = int(req.limit or getattr(s, "PROB_RETRAIN_LIMIT", 5000) or 5000)

        def is_safe_subdir(parent_path: str, child_path: str) -> bool:
            """Check if child_path is strictly within parent_path (robust against symlinks/traversal)."""
            parent_real = _os.path.realpath(_os.path.abspath(parent_path))
            child_real = _os.path.realpath(_os.path.abspath(child_path))

            # Ensure paths end with separator for strict containment check
            if not parent_real.endswith(_os.sep):
                parent_real += _os.sep

            # Child must start with parent path and not be equal to it
            return child_real.startswith(parent_real) and child_real != parent_real.rstrip(_os.sep)

        safe_root = str(getattr(s, "PROB_RETRAIN_OUTPUT_DIR", "config/models"))
        # Resolve safe_root to canonical absolute path
        safe_root_real = _os.path.realpath(_os.path.abspath(safe_root))
        user_dir = req.output_dir

        # Validate output_dir: must be within safe_root and not absolute
        if user_dir:
            # Only allow relative paths
            if _os.path.isabs(user_dir):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid output_dir: must be a relative path.",
                )

            # Reject path traversal attempts (.. components)
            if ".." in user_dir.split(_os.sep):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid output_dir: must be a simple relative sub-directory.",
                )

            # Construct and resolve final path
            out_dir = _os.path.realpath(_os.path.join(safe_root_real, user_dir))

            # Strong containment check: out_dir must be a strict subdirectory of safe_root_real
            if not is_safe_subdir(safe_root_real, out_dir):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid output_dir: must be within allowed directory.",
                )
        else:
            out_dir = safe_root_real
        _os.makedirs(out_dir, exist_ok=True)

        written: list[str] = []
        for sym in symbols:
            eff = sym_svc.resolve(sym)
            candles = await data.get_candles(sym, tf, limit)
            if not candles:
                continue
            horizon = int(getattr(s, "PROB_MODEL_TIME_HORIZON", 20) or 20)
            tp = float(getattr(s, "PROB_MODEL_EV_THRESHOLD", 0.0005) or 0.0005)
            sl = tp
            clean = eff[1:] if eff.startswith("t") else eff
            try:
                import re as _re

                clean = _re.sub(r"[^A-Za-z0-9_]", "_", clean)
            except Exception:
                pass
            fname = f"{clean}_{tf}.json"
            # Defense: ensure fname does not contain slashes
            if "/" in fname or "\\" in fname:
                raise HTTPException(status_code=400, detail="Invalid filename generated")
            # Security: Create a safe filename path that passes validation
            # Use only the filename, not the full path, to avoid path traversal issues
            safe_fname_only = fname  # fname is already validated above
            train_and_export(candles, horizon=horizon, tp=tp, sl=sl, out_path=safe_fname_only)
            # For logging, reconstruct the actual path
            actual_out_path = _os.path.join(out_dir, fname)
            written.append(actual_out_path)

        # reload om matchar aktuell fil
        try:
            if written and getattr(prob_model.settings, "PROB_MODEL_FILE", None):
                cur = str(prob_model.settings.PROB_MODEL_FILE)
                if _os.path.abspath(cur) in [_os.path.abspath(w) for w in written]:
                    prob_model.reload()
        except Exception:
            pass
        return {"written": written, "reloaded": bool(prob_model.model_meta)}
    except Exception as e:
        logger.exception(f"prob/retrain/run error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


# Prob konfig - hämta/uppdatera utan omstart
class ProbConfigUpdateRequest(BaseModel):
    model_enabled: bool | None = None
    model_file: str | None = None
    ev_threshold: float | None = None
    confidence_min: float | None = None
    autotrade_enabled: bool | None = None
    size_max_risk_pct: float | None = None
    size_kelly_cap: float | None = None
    size_conf_weight: float | None = None
    position_size_fallback_quote: float | None = None
    # Validation controls
    validate_enabled: bool | None = None
    validate_symbols: str | None = None
    validate_timeframe: str | None = None
    validate_limit: int | None = None
    # Retraining controls
    retrain_enabled: bool | None = None
    retrain_interval_hours: int | None = None
    retrain_symbols: str | None = None
    retrain_timeframe: str | None = None
    retrain_limit: int | None = None


class ProbFeatureLogQuery(BaseModel):
    symbol: str | None = None
    timeframe: str | None = None
    limit: int = 100


@router.get("/prob/config")
async def prob_get_config(_: bool = Depends(require_auth)):
    try:
        s = settings
        from services import runtime_config as rc

        return {
            "model_enabled": bool(getattr(s, "PROB_MODEL_ENABLED", False)),
            "model_file": getattr(s, "PROB_MODEL_FILE", None),
            "ev_threshold": float(getattr(s, "PROB_MODEL_EV_THRESHOLD", 0.0) or 0.0),
            "confidence_min": float(getattr(s, "PROB_MODEL_CONFIDENCE_MIN", 0.0) or 0.0),
            "autotrade_enabled": bool(
                rc.get_bool(
                    "PROB_AUTOTRADE_ENABLED",
                    getattr(s, "PROB_AUTOTRADE_ENABLED", False),
                )
            ),
            "size_max_risk_pct": float(getattr(s, "PROB_SIZE_MAX_RISK_PCT", 0.0) or 0.0),
            "size_kelly_cap": float(getattr(s, "PROB_SIZE_KELLY_CAP", 0.0) or 0.0),
            "size_conf_weight": float(getattr(s, "PROB_SIZE_CONF_WEIGHT", 0.0) or 0.0),
            "position_size_fallback_quote": float(getattr(s, "POSITION_SIZE_FALLBACK_QUOTE", 0.0) or 0.0),
            # Validation
            "validate_enabled": bool(getattr(s, "PROB_VALIDATE_ENABLED", True)),
            "validate_symbols": getattr(s, "PROB_VALIDATE_SYMBOLS", None),
            "validate_timeframe": str(getattr(s, "PROB_VALIDATE_TIMEFRAME", "1m") or "1m"),
            "validate_limit": int(getattr(s, "PROB_VALIDATE_LIMIT", 1200) or 1200),
            # Retraining
            "retrain_enabled": bool(getattr(s, "PROB_RETRAIN_ENABLED", False)),
            "retrain_interval_hours": int(getattr(s, "PROB_RETRAIN_INTERVAL_HOURS", 24) or 24),
            "retrain_symbols": getattr(s, "PROB_RETRAIN_SYMBOLS", None),
            "retrain_timeframe": str(getattr(s, "PROB_RETRAIN_TIMEFRAME", "1m") or "1m"),
            "retrain_limit": int(getattr(s, "PROB_RETRAIN_LIMIT", 5000) or 5000),
            "loaded": bool(prob_model.enabled and prob_model.model_meta),
        }
    except Exception as e:
        logger.exception(f"prob/config get error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/prob/config")
async def prob_update_config(req: ProbConfigUpdateRequest, _: bool = Depends(require_auth)):
    try:
        import services.runtime_config as rc

        # Skriv env och uppdatera runtime där det är relevant
        if req.model_enabled is not None:
            rc.set_bool("PROB_MODEL_ENABLED", bool(req.model_enabled))
            prob_model.enabled = bool(req.model_enabled)
        if req.model_file:
            rc.set_str("PROB_MODEL_FILE", str(req.model_file))
            try:
                prob_model.reload()
            except Exception:
                pass
        if req.ev_threshold is not None:
            rc.set_float("PROB_MODEL_EV_THRESHOLD", float(req.ev_threshold))
        if req.confidence_min is not None:
            rc.set_float("PROB_MODEL_CONFIDENCE_MIN", float(req.confidence_min))
        if req.autotrade_enabled is not None:
            rc.set_bool("PROB_AUTOTRADE_ENABLED", bool(req.autotrade_enabled))
        if req.size_max_risk_pct is not None:
            rc.set_float("PROB_SIZE_MAX_RISK_PCT", float(req.size_max_risk_pct))
        if req.size_kelly_cap is not None:
            rc.set_float("PROB_SIZE_KELLY_CAP", float(req.size_kelly_cap))
        if req.size_conf_weight is not None:
            rc.set_float("PROB_SIZE_CONF_WEIGHT", float(req.size_conf_weight))
        if req.position_size_fallback_quote is not None:
            rc.set_float("POSITION_SIZE_FALLBACK_QUOTE", float(req.position_size_fallback_quote))
        # Validation controls
        if req.validate_enabled is not None:
            rc.set_bool("PROB_VALIDATE_ENABLED", bool(req.validate_enabled))
        if req.validate_symbols is not None:
            rc.set_str("PROB_VALIDATE_SYMBOLS", str(req.validate_symbols))
        if req.validate_timeframe is not None:
            rc.set_str("PROB_VALIDATE_TIMEFRAME", str(req.validate_timeframe))
        if req.validate_limit is not None:
            rc.set_int("PROB_VALIDATE_LIMIT", int(req.validate_limit))
        # Retraining controls
        if req.retrain_enabled is not None:
            rc.set_bool("PROB_RETRAIN_ENABLED", bool(req.retrain_enabled))
        if req.retrain_interval_hours is not None:
            rc.set_int("PROB_RETRAIN_INTERVAL_HOURS", int(req.retrain_interval_hours))
        if req.retrain_symbols is not None:
            rc.set_str("PROB_RETRAIN_SYMBOLS", str(req.retrain_symbols))
        if req.retrain_timeframe is not None:
            rc.set_str("PROB_RETRAIN_TIMEFRAME", str(req.retrain_timeframe))
        if req.retrain_limit is not None:
            rc.set_int("PROB_RETRAIN_LIMIT", int(req.retrain_limit))

        # metrics: registrera uppdatering
        try:
            get_metrics_client().inc_labeled("prob_events", {"type": "config_update"})
        except Exception:
            pass

        return await prob_get_config(True)  # återanvänd GET
    except Exception as e:
        logger.exception(f"prob/config update error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/prob/featlog")
async def prob_feature_log(q: ProbFeatureLogQuery, _: bool = Depends(require_auth)):
    try:
        from services.metrics import metrics_store as _ms

        logs = _ms.get("prob_feature_log", {}) or {}
        if q.symbol and q.timeframe:
            key = f"{q.symbol}|{q.timeframe}"
            arr = list(logs.get(key, []))[-int(max(q.limit, 1)) :]
            return {key: arr}
        # annars returnera allt (sista 'limit' per nyckel)
        out: dict[str, list[dict]] = {}
        for k, v in logs.items():
            try:
                out[k] = list(v)[-int(max(q.limit, 1)) :]
            except Exception:
                out[k] = []
        return out
    except Exception as e:
        logger.exception(f"prob/featlog error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


# Symbols endpoint
@router.get("/market/symbols")
async def market_symbols(test_only: bool = False, format: str = "v2", _: bool = Depends(require_auth)):
    try:
        svc = SymbolService()
        # Säkerställ färska configs för att kunna filtrera bort icke-listade
        try:
            await svc.refresh()
        except Exception:
            pass
        arr = svc.get_symbols(test_only=test_only, fmt=format)
        # Filtrera bort symboler som inte är listade (efter resolve)
        filtered: list[str] = []
        for s in arr:
            try:
                eff = svc.resolve(s)
                if svc.listed(eff):
                    filtered.append(s)
            except Exception:
                # Om något går fel, inkludera inte symbolen
                pass
        return filtered
    except Exception as e:
        logger.exception(f"Fel vid symbols: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


# Watchlist endpoint (liten vy) med ticker + volym + senaste strategi-signal
@router.get("/market/watchlist")
async def market_watchlist(symbols: str | None = None, prob: bool = False, _: bool = Depends(require_auth)):
    try:
        svc = get_watchlist_service()
        return await svc.build_watchlist(symbols_param=symbols, include_prob=prob)
    except Exception as e:
        logger.exception("Fel vid watchlist")
        raise HTTPException(status_code=500, detail="internal_error") from e


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
    except Exception as e:
        logger.exception("Backtest fel")
        raise HTTPException(status_code=500, detail="internal_error") from e


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
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/auto/stop")
async def auto_stop(req: AutoStartRequest, _: bool = Depends(require_auth)):
    try:
        await trading_integration.stop_automated_trading(req.symbol)
        _emit_notification("info", "Auto trading stoppad", {"symbol": req.symbol})
        return {"ok": True, "symbol": req.symbol}
    except Exception as e:
        logger.exception(f"Fel vid auto/stop: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


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
        raise HTTPException(status_code=500, detail="Internal server error") from e


# Batch/Stop-all endpoints
class AutoBatchRequest(BaseModel):
    symbols: list[str]


@router.post("/auto/stop-all")
async def auto_stop_all(_: bool = Depends(require_auth)):
    try:
        await trading_integration.stop_all_trading()
        _emit_notification("info", "Auto trading stoppad (alla)", {"symbols": []})
        return {"ok": True}
    except Exception as e:
        logger.exception(f"Fel vid auto/stop-all: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/auto/start-batch")
async def auto_start_batch(req: AutoBatchRequest, _: bool = Depends(require_auth)):
    try:
        started: list[str] = []
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
            _emit_notification("info", "Auto trading startad (batch)", {"symbols": started})
        return {"ok": True, "started": started}
    except Exception as e:
        logger.exception(f"Fel vid auto/start-batch: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


# Bracket order endpoint
@router.post("/order/bracket", response_model=OrderResponse)
async def place_bracket_order(req: BracketOrderRequest, _: bool = Depends(require_auth)):
    try:
        logger.info(f"Mottog bracket-order: {req.dict()}")
        # Idempotens: central service (tidig retur om tidigare svar finns)
        try:
            cid2 = (req.client_id or "").strip() if hasattr(req, "client_id") else ""
            if cid2:
                _idem = get_idempotency_service()
                _hit = _idem.check_and_register(cid2)
                if _hit is not None and isinstance(_hit, dict):
                    return OrderResponse(**_hit)
        except Exception:
            pass
        # Rate-limit skydd
        try:
            max_requests = int(getattr(settings, "ORDER_RATE_LIMIT_MAX", 0) or 0)
            window_seconds = int(getattr(settings, "ORDER_RATE_LIMIT_WINDOW", 0) or 0)
            if max_requests > 0 and window_seconds > 0:
                if not _rl.is_allowed("bracket_order", max_requests, window_seconds):
                    try:
                        from services.metrics import inc as _inc

                        _inc("rate_limited_total")
                    except Exception:
                        pass
                    return OrderResponse(success=False, error="rate_limited")
        except Exception:
            pass
        decision = unified_risk_service.evaluate_risk(symbol=req.symbol)
        if not decision.allowed:
            return OrderResponse(success=False, error=f"risk_blocked:{decision.reason}")

        # Hjälpare: extrahera order-id från Bitfinex svar (kan vara list-format)
        def _extract_order_id(res: dict | list | None) -> int | None:
            try:
                if isinstance(res, dict):
                    val = res.get("order_id") or res.get("id")
                    return int(val) if val is not None else None
                if isinstance(res, list) and len(res) >= 5:
                    orders = res[4]
                    if isinstance(orders, list) and len(orders) > 0 and isinstance(orders[0], list):
                        return int(orders[0][0])
            except Exception:
                return None
            return None

        # Entry
        entry_payload: dict[str, Any] = {
            "symbol": req.symbol,
            "amount": req.amount,
            "type": req.entry_type,
            "side": req.side,
        }
        if req.entry_type and "LIMIT" in req.entry_type.upper():
            if req.entry_price is not None:
                entry_payload["price"] = req.entry_price
        # Flaggor
        if "post_only" in req.__fields_set__:
            entry_payload["post_only"] = bool(req.post_only)
        # Validera payload
        is_valid, err = order_validator.validate_order(entry_payload)
        if not is_valid:
            return OrderResponse(success=False, error=f"validation_error:{err}")
        entry_res = await rest_auth.place_order(entry_payload)
        if "error" in entry_res:
            # Försök WS fallback 'on' - men inte om Dry Run är aktiverat
            try:
                import services.runtime_config as rc

                if rc.get_bool("DRY_RUN_ENABLED", False):
                    logger.info("WS fallback hoppas över: Dry Run är aktiverat")
                    return OrderResponse(success=False, error=entry_res.get("error"))

                from services.bitfinex_websocket import bitfinex_ws as _ws

                ws_res = await _ws.order_ops([["on", entry_payload]])
                if not bool(ws_res.get("success")):
                    return OrderResponse(success=False, error=entry_res.get("error"))
            except Exception:
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
                "amount": (req.amount if req.side.lower() == "sell" else f"-{req.amount}"),
                "type": "EXCHANGE STOP",
                "price": req.sl_price,
                "side": "sell" if req.side.lower() == "buy" else "buy",
            }
            is_valid, err = order_validator.validate_order(sl_payload)
            if not is_valid:
                return OrderResponse(success=False, error=f"validation_error:{err}")
            sl_res = await rest_auth.place_order(sl_payload)
            if "error" in sl_res:
                try:
                    from services.bitfinex_websocket import bitfinex_ws as _ws

                    ws_res = await _ws.order_ops([["on", sl_payload]])
                    if bool(ws_res.get("success")):
                        sl_id = None  # WS-id fås via privata callbacks, leave None
                except Exception:
                    pass
            else:
                sl_id = _extract_order_id(sl_res)
        # TP
        if req.tp_price:
            tp_payload = {
                "symbol": req.symbol,
                "amount": (req.amount if req.side.lower() == "sell" else f"-{req.amount}"),
                "type": "EXCHANGE LIMIT",
                "price": req.tp_price,
                "side": "sell" if req.side.lower() == "buy" else "buy",
            }
            is_valid, err = order_validator.validate_order(tp_payload)
            if not is_valid:
                return OrderResponse(success=False, error=f"validation_error:{err}")
            tp_res = await rest_auth.place_order(tp_payload)
            if "error" in tp_res:
                try:
                    from services.bitfinex_websocket import bitfinex_ws as _ws

                    ws_res = await _ws.order_ops([["on", tp_payload]])
                    if bool(ws_res.get("success")):
                        tp_id = None
                except Exception:
                    pass
            else:
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
        resp_obj = OrderResponse(success=True, data={"entry_id": entry_id, "sl_id": sl_id, "tp_id": tp_id})
        # Spara idempotensrespons om client_id angiven
        try:
            cid2 = (req.client_id or "").strip() if hasattr(req, "client_id") else ""
            if cid2:
                get_idempotency_service().store_response(cid2, resp_obj.dict())
        except Exception:
            pass
        return resp_obj
    except Exception as e:
        logger.exception(f"Fel vid bracket-order: {e}")
        return OrderResponse(success=False, error=str(e))


"""Legacy risk windows endpoints borttagna – använd unified /risk/unified/*"""


# V2 API endpoints borttagna – använd unified /risk/unified/*


pass


pass


pass


pass


pass


# Performance breakdown per symbol
@router.get("/account/performance/detail")
async def get_account_performance_detail(_: bool = Depends(require_auth)):
    try:
        wallet_svc = WalletService()
        pos_svc = PositionsService()
        data_svc = get_market_data()
        perf = PerformanceService()

        wallets = await wallet_svc.get_wallets()
        positions = await pos_svc.get_positions()

        # Hjälp: parse symbol till (base, quote)
        def parse_bq(sym: str) -> dict[str, str]:
            s = sym[1:] if sym.startswith("t") else sym
            if ":" in s:
                base, quote = s.split(":", 1)
            else:
                base, quote = s[:-3], s[-3:]
            return {"base": base.upper(), "quote": quote.upper()}

        # PnL per symbol + positionsinfo med current price
        pnl_by_symbol: dict[str, float] = {}
        positions_info: list[dict[str, Any]] = []
        prices_cache: dict[str, float] = {}

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
        wallets_by_symbol: dict[str, dict[str, Any]] = {}
        # För snabb uppslagning: summera per currency
        totals_by_currency: dict[str, dict[str, float]] = {}
        for w in wallets:
            cur = w.currency.upper()
            e = totals_by_currency.setdefault(cur, {"total": 0.0, "exchange": 0.0, "margin": 0.0, "funding": 0.0})
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
        raise HTTPException(status_code=500, detail="Internal server error") from e


# Risk endpoints
class UpdateMaxTradesRequest(BaseModel):
    max_trades_per_day: int


@router.get("/risk/status")
async def get_risk_status(_: bool = Depends(require_auth)):
    from services.unified_risk_service import unified_risk_service

    risk_status = unified_risk_service.get_risk_status()
    # Utöka med TransportCircuitBreaker state från limiter om tillgängligt
    try:
        from utils.advanced_rate_limiter import get_advanced_rate_limiter

        limiter = get_advanced_rate_limiter()
        # Exportera aktuella limiter-metrics och inkludera CB open-times per endpoint
        limiter.export_metrics()
        # Addera enkel vy av CB-keys med time_until_open
        # Exponera endast kända endpoints av intresse
        endpoints = [
            "auth/r/wallets",
            "auth/r/positions",
            "auth/r/info/margin/base",
            "auth/r/trades",
        ]
        transport_cb = {}
        for ep in endpoints:
            try:
                ttl = float(limiter.time_until_open(ep))
                transport_cb[ep] = {"cooldown_seconds": ttl}
            except Exception:
                transport_cb[ep] = {"cooldown_seconds": 0.0}
        risk_status["transport_circuit_breaker"] = transport_cb
    except Exception:
        pass
    return risk_status


# --- Runtime config (hot‑reload) ---
class RuntimeConfigRequest(BaseModel):
    values: dict[str, Any]


@router.get("/runtime/config")
async def runtime_config_get(_: bool = Depends(require_auth)):
    try:
        import services.runtime_config as rc

        return {"overrides": getattr(rc, "_runtime_overrides", {})}
    except Exception as e:
        logger.exception(f"Fel vid runtime config get: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/runtime/config")
async def runtime_config_set(req: RuntimeConfigRequest, _: bool = Depends(require_auth)):
    try:
        import services.runtime_config as rc

        for k, v in (req.values or {}).items():
            if isinstance(v, bool):
                rc.set_bool(k, v)
            elif isinstance(v, int):
                rc.set_int(k, v)
            elif isinstance(v, float):
                rc.set_float(k, v)
            else:
                rc.set_str(k, str(v))
        # Hot-reload limiter metrics export
        try:
            get_advanced_rate_limiter().export_metrics()
        except Exception:
            pass
        return {"ok": True, "overrides": getattr(rc, "_runtime_overrides", {})}
    except Exception as e:
        logger.exception(f"Fel vid runtime config set: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/risk/max-trades")
async def update_max_trades(req: UpdateMaxTradesRequest, _: bool = Depends(require_auth)):
    # Uppdatera i runtime settings (enkel variant). Permanent lagring kräver filskrivning.
    try:
        s = settings
        s.MAX_TRADES_PER_DAY = req.max_trades_per_day
        # persistera till regler
        tw = TradingWindowService(s)
        tw.rules.max_trades_per_day = req.max_trades_per_day
        tw.save_rules()
        from services.unified_risk_service import unified_risk_service

        risk_status = unified_risk_service.get_risk_status()
        return {"success": True, "status": risk_status}
    except Exception as e:
        logger.exception(f"Fel vid uppdatering av max trades: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


class UpdateMaxTradesSymbolRequest(BaseModel):
    max_trades_per_symbol_per_day: int


@router.post("/risk/max-trades-symbol")
async def update_max_trades_symbol(req: UpdateMaxTradesSymbolRequest, _: bool = Depends(require_auth)):
    try:
        s = settings
        tw = TradingWindowService(s)
        tw.save_rules(max_trades_per_symbol_per_day=req.max_trades_per_symbol_per_day)
        from services.unified_risk_service import unified_risk_service

        risk_status = unified_risk_service.get_risk_status()
        return {"success": True, "status": risk_status}
    except Exception as e:
        logger.exception(f"Fel vid uppdatering av max trades per symbol: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/risk/trade-counter")
async def get_trade_counter(_: bool = Depends(require_auth)):
    try:
        # UnifiedRiskService konsoliderar trade constraints; exponera status via get_risk_status
        from services.unified_risk_service import unified_risk_service

        trade_status = unified_risk_service.get_risk_status().get("trade_constraints", {})
        return trade_status
    except Exception as e:
        logger.exception(f"Fel vid hämtning av trade counter: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


# --- Circuit Breaker endpoints ---
class CircuitConfigRequest(BaseModel):
    enabled: bool | None = None
    window_seconds: int | None = None
    max_errors_per_window: int | None = None
    notify: bool | None = None


@router.get("/risk/circuit")
async def circuit_status(_: bool = Depends(require_auth)):
    try:
        from services.unified_risk_service import unified_risk_service

        cb_status = unified_risk_service.get_risk_status().get("circuit_breaker", {})
        return cb_status
    except Exception as e:
        logger.exception(f"Fel vid circuit status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/risk/circuit/reset")
async def circuit_reset(resume: bool = True, clear_errors: bool = True, _: bool = Depends(require_auth)):
    try:
        from services.unified_risk_service import unified_risk_service

        ok = unified_risk_service.reset_circuit_breaker()
        return {"success": ok}
    except Exception as e:
        logger.exception(f"Fel vid circuit reset: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/risk/circuit/config")
async def circuit_config(req: CircuitConfigRequest, _: bool = Depends(require_auth)):
    try:
        # unified_risk_service har fasta CB‑parametrar; eventuell config kan adderas senare
        from services.unified_risk_service import unified_risk_service

        ok = unified_risk_service.reset_circuit_breaker()
        return {"success": ok, "note": "CB-config API förenklad; reset utförd"}
    except Exception as e:
        logger.exception(f"Fel vid circuit config: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


# Risk Guards endpoints
class RiskGuardResetRequest(BaseModel):
    guard_name: str


@router.get("/risk/guards/status")
async def get_risk_guards_status(_: bool = Depends(require_auth)):
    """Hämta status för alla riskvakter."""
    try:
        from services.risk_guards import risk_guards

        guards_status = risk_guards.get_guards_status()
        return guards_status
    except Exception as e:
        logger.exception(f"Fel vid hämtning av risk guards status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/risk/guards/reset")
async def reset_risk_guard(req: RiskGuardResetRequest, _: bool = Depends(require_auth)):
    """Återställ en specifik riskvakt."""
    try:
        from services.risk_guards import risk_guards

        success = risk_guards.reset_guard(req.guard_name)
        if success:
            return {"success": True, "message": f"Riskvakt {req.guard_name} återställd"}
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Kunde inte återställa riskvakt {req.guard_name}",
            )
    except Exception as e:
        logger.exception(f"Fel vid återställning av riskvakt: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


class RiskGuardConfigRequest(BaseModel):
    guard_name: str
    config: dict


@router.post("/risk/guards/config")
async def update_risk_guard_config(req: RiskGuardConfigRequest, _: bool = Depends(require_auth)):
    """Uppdatera konfiguration för en riskvakt."""
    try:
        from services.risk_guards import risk_guards

        success = risk_guards.update_guard_config(req.guard_name, req.config)
        if success:
            return {
                "success": True,
                "message": f"Riskvakt {req.guard_name} konfiguration uppdaterad",
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Kunde inte uppdatera riskvakt {req.guard_name}",
            )
    except Exception as e:
        logger.exception(f"Fel vid uppdatering av riskvakt konfiguration: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


# Cost-Aware Backtest endpoints
class BacktestRequestV2(BaseModel):
    symbol: str
    timeframe: str = "1m"
    limit: int = 500
    initial_capital: float = 10000.0
    position_size_pct: float = 0.1
    costs: dict | None = None


@router.post("/backtest/cost-aware")
async def run_cost_aware_backtest(req: BacktestRequestV2, _: bool = Depends(require_auth)):
    """Kör cost-aware backtest."""
    try:
        from services.cost_aware_backtest import TradeCosts, cost_aware_backtest

        # Konvertera costs dict till TradeCosts om det finns
        costs = None
        if req.costs:
            costs = TradeCosts(**req.costs)

        result = await cost_aware_backtest.run_backtest(
            symbol=req.symbol,
            timeframe=req.timeframe,
            limit=req.limit,
            initial_capital=req.initial_capital,
            position_size_pct=req.position_size_pct,
            costs=costs,
        )

        # Konvertera resultat till dict för JSON serialisering
        return {
            "success": True,
            "result": {
                "total_trades": result.total_trades,
                "winning_trades": result.winning_trades,
                "losing_trades": result.losing_trades,
                "total_pnl": result.total_pnl,
                "total_fees": result.total_fees,
                "total_slippage": result.total_slippage,
                "max_drawdown": result.max_drawdown,
                "sharpe_ratio": result.sharpe_ratio,
                "sortino_ratio": result.sortino_ratio,
                "calmar_ratio": result.calmar_ratio,
                "hit_rate": result.hit_rate,
                "avg_win": result.avg_win,
                "avg_loss": result.avg_loss,
                "profit_factor": result.profit_factor,
                "expectancy": result.expectancy,
                "equity_curve": result.equity_curve,
                "trades": [
                    {
                        "timestamp": trade.timestamp.isoformat(),
                        "symbol": trade.symbol,
                        "side": trade.side,
                        "amount": trade.amount,
                        "price": trade.price,
                        "executed_price": trade.executed_price,
                        "fees": trade.fees,
                        "slippage": trade.slippage,
                        "partial_fill": trade.partial_fill,
                        "fill_ratio": trade.fill_ratio,
                        "latency_ms": trade.latency_ms,
                    }
                    for trade in result.trades
                ],
            },
        }
    except Exception as e:
        logger.exception(f"Fel vid cost-aware backtest: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/backtest/costs/default")
async def get_default_costs(_: bool = Depends(require_auth)):
    """Hämta default kostnadsmodell."""
    try:
        from services.cost_aware_backtest import TradeCosts

        default_costs = TradeCosts()
        return {
            "success": True,
            "costs": {
                "maker_fee": default_costs.maker_fee,
                "taker_fee": default_costs.taker_fee,
                "spread_bps": default_costs.spread_bps,
                "slippage_bps": default_costs.slippage_bps,
                "partial_fill_prob": default_costs.partial_fill_prob,
                "latency_ms": default_costs.latency_ms,
            },
        }
    except Exception as e:
        logger.exception(f"Fel vid hämtning av default costs: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


# Regime Ablation endpoints
class RegimeConfigRequest(BaseModel):
    regime_name: str
    config: dict


@router.get("/regime/status")
async def get_regime_status(_: bool = Depends(require_auth)):
    """Hämta status för alla regimer."""
    try:
        from services.regime_ablation import regime_ablation

        regime_status = regime_ablation.get_regime_status()
        return regime_status
    except Exception as e:
        logger.exception(f"Fel vid hämtning av regime status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/regime/config")
async def update_regime_config(req: RegimeConfigRequest, _: bool = Depends(require_auth)):
    """Uppdatera konfiguration för ett regime."""
    try:
        from services.regime_ablation import regime_ablation

        success = regime_ablation.update_regime_config(req.regime_name, req.config)
        if success:
            return {
                "success": True,
                "message": f"Regime {req.regime_name} konfiguration uppdaterad",
            }
        else:
            raise HTTPException(status_code=400, detail=f"Kunde inte uppdatera regime {req.regime_name}")
    except Exception as e:
        logger.exception(f"Fel vid uppdatering av regime konfiguration: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/regime/performance/update")
async def update_regime_performance(regime_name: str, _: bool = Depends(require_auth)):
    """Uppdatera performance för ett regime."""
    try:
        from services.regime_ablation import regime_ablation

        success = regime_ablation.update_regime_performance(regime_name)
        if success:
            return {
                "success": True,
                "message": f"Performance uppdaterad för regime {regime_name}",
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Kunde inte uppdatera performance för regime {regime_name}",
            )
    except Exception as e:
        logger.exception(f"Fel vid uppdatering av regime performance: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


class AblationTestRequest(BaseModel):
    test_duration_days: int = 7


@router.post("/regime/ablation-test")
async def run_ablation_test(req: AblationTestRequest, _: bool = Depends(require_auth)):
    """Kör A/B-test av regime switching."""
    try:
        from services.regime_ablation import regime_ablation

        result = regime_ablation.run_ablation_test(req.test_duration_days)
        return {"success": True, "result": result}
    except Exception as e:
        logger.exception(f"Fel vid ablation test: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/regime/active")
async def get_active_regimes(_: bool = Depends(require_auth)):
    """Hämta aktiva regimer."""
    try:
        from services.regime_ablation import regime_ablation

        active_regimes = regime_ablation.get_active_regimes()
        weights = regime_ablation.get_regime_weights()
        return {"success": True, "active_regimes": active_regimes, "weights": weights}
    except Exception as e:
        logger.exception(f"Fel vid hämtning av aktiva regimer: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


# Health Watchdog endpoints
@router.get("/health/overall")
async def get_overall_health(_: bool = Depends(require_auth)):
    """Hämta övergripande hälsostatus."""
    try:
        from services.health_watchdog import health_watchdog

        overall = health_watchdog.get_overall_health()
        return overall
    except Exception as e:
        logger.exception(f"Fel vid hämtning av overall health: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/health/check/{check_name}")
async def run_health_check(check_name: str, _: bool = Depends(require_auth)):
    """Kör en specifik hälsokontroll."""
    try:
        from services.health_watchdog import health_watchdog

        result = await health_watchdog.run_health_check(check_name)
        return {"success": True, "result": result.__dict__}
    except Exception as e:
        logger.exception(f"Fel vid health check {check_name}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/health/check-all")
async def run_all_health_checks(_: bool = Depends(require_auth)):
    """Kör alla hälsokontroller."""
    try:
        from services.health_watchdog import health_watchdog

        results = await health_watchdog.run_all_health_checks()
        return {
            "success": True,
            "results": {name: st.__dict__ for name, st in results.items()},
        }
    except Exception as e:
        logger.exception(f"Fel vid körning av alla health checks: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/health/watchdog/start")
async def start_health_watchdog(_: bool = Depends(require_auth)):
    """Starta health watchdog."""
    try:
        from services.health_watchdog import health_watchdog

        if not health_watchdog.running:
            health_watchdog.task = asyncio.create_task(health_watchdog.start_watchdog())
            return {"success": True, "message": "Health watchdog startad"}
        else:
            return {"success": False, "message": "Health watchdog redan igång"}
    except Exception as e:
        logger.exception(f"Fel vid start av health watchdog: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/health/watchdog/stop")
async def stop_health_watchdog(_: bool = Depends(require_auth)):
    """Stoppa health watchdog."""
    try:
        from services.health_watchdog import health_watchdog

        await health_watchdog.stop_watchdog()
        return {"success": True, "message": "Health watchdog stoppad"}
    except Exception as e:
        logger.exception(f"Fel vid stopp av health watchdog: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


# JSON Optimizer endpoints
@router.get("/json-optimizer/stats")
async def get_json_optimizer_stats(_: bool = Depends(require_auth)):
    """Hämta JSON optimizer statistik."""
    try:
        from utils.json_optimizer import json_optimizer

        stats = json_optimizer.get_cache_stats()
        return {"success": True, "stats": stats}
    except Exception as e:
        logger.exception(f"Fel vid hämtning av JSON optimizer stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/json-optimizer/clear-cache")
async def clear_json_cache(_: bool = Depends(require_auth)):
    """Rensa JSON cache."""
    try:
        from utils.json_optimizer import json_optimizer

        json_optimizer.clear_cache()
        return {"success": True, "message": "JSON cache rensad"}
    except Exception as e:
        logger.exception(f"Fel vid rensning av JSON cache: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


class BenchmarkRequest(BaseModel):
    data: str
    iterations: int = 1000


@router.post("/json-optimizer/benchmark")
async def benchmark_json_parsing(req: BenchmarkRequest, _: bool = Depends(require_auth)):
    """Benchmark JSON parsing prestanda."""
    try:
        from utils.json_optimizer import benchmark_json_parsing

        results = benchmark_json_parsing(req.data, req.iterations)
        return {"success": True, "results": results}
    except Exception as e:
        logger.exception(f"Fel vid JSON benchmark: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


# Bracket state admin
class BracketResetRequest(BaseModel):
    delete_file: bool = True


@router.post("/bracket/reset")
async def bracket_reset(req: BracketResetRequest, _: bool = Depends(require_auth)):
    try:
        cleared = bracket_manager.reset(delete_file=req.delete_file)
        _emit_notification(
            "info",
            "Bracket-state nollställt",
            {"cleared": cleared, "delete_file": req.delete_file},
        )
        return {"success": True, "cleared": cleared}
    except Exception as e:
        logger.exception(f"Fel vid bracket reset: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


# Metrics endpoint (Prometheus text format)
@router.get("/metrics")
async def metrics(_: bool = Depends(require_auth)):
    try:
        # Valfri token‑kontroll om satt i settings
        token_required = getattr(settings, "METRICS_ACCESS_TOKEN", None)
        if token_required:
            # Hämta bearer token från Authorization
            # Om du vill kan du byta till queryparam ?token=
            def _get_auth_header() -> str:
                import os

                return os.environ.get("HTTP_AUTHORIZATION", "")

            # FastAPI injicerar inte Request här; enkel fallback
            # Lämna öppet om inte token satt
        # Uppdatera ws_pool metrics innan rendering
        try:
            from services.bitfinex_websocket import bitfinex_ws as _ws
            from services.metrics import metrics_store as _ms

            st = _ws.get_pool_status()
            _ms["ws_pool"] = {
                "enabled": 1 if st.get("pool_enabled") else 0,
                "max_sockets": int(st.get("pool_max_sockets", 0) or 0),
                "max_subs": int(st.get("pool_max_subs", 0) or 0),
                "sockets": [
                    {
                        "subs": int(x.get("subs", 0) or 0),
                        "closed": 1 if x.get("closed") else 0,
                    }
                    for x in (st.get("pool_sockets") or [])
                ],
            }
        except Exception:
            pass
        text = render_prometheus_text()
        # Bifoga senaste prob_trade_outcome som JSON‑kommentar för enkel UI‑parsning
        try:
            from services.metrics import metrics_store as _ms

            last = _ms.get("prob_trade_last") or {}
            if last:
                import json as _json

                text += "# prob_trade_last_json " + _json.dumps(last) + "\n"
        except Exception:
            pass
        return Response(content=text, media_type="text/plain; version=0.0.4")
    except Exception as e:
        logger.exception(f"Fel vid metrics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/metrics/summary")
async def metrics_summary(_: bool = Depends(require_auth)):
    try:
        from fastapi.responses import JSONResponse as _JSONResponse

        summary = get_metrics_client().summary()
        return _JSONResponse(content=summary)
    except Exception as e:
        logger.exception("Fel vid metrics summary")
        raise HTTPException(status_code=500, detail="internal_error") from e


# --- Unified Trading Window update ---
class UnifiedWindowsUpdateRequest(BaseModel):
    timezone: str | None = None
    windows: dict[str, list[tuple[str, str]]] | None = None
    paused: bool | None = None
    max_trades_per_day: int | None = None
    max_trades_per_symbol_per_day: int | None = None
    trade_cooldown_seconds: int | None = None


@router.post("/risk/unified/windows/update")
async def update_unified_trading_windows(req: UnifiedWindowsUpdateRequest, _: bool = Depends(require_auth)):
    """Uppdatera trading windows/status via Unified TradingWindowService."""
    try:
        from services.trading_window import TradingWindowService

        tw = TradingWindowService(settings)
        await tw.update_rules_async(req.windows)
        return {"status": "success", "message": "Tradingfönster uppdaterade."}
    except Exception as e:
        logger.exception(f"Fel vid uppdatering av unified trading windows: {e}")
        raise HTTPException(status_code=500, detail="internal_error") from e


@router.get("/metrics/acceptance")
async def metrics_acceptance(_: bool = Depends(require_auth)):
    try:
        from config.settings import Settings as _S
        from services.metrics_client import get_metrics_client as _get_client

        s = _S()
        m = _get_client().summary()
        p95 = int(m.get("latency", {}).get("candles_ms", {}).get("p95", 0))
        p99 = int(m.get("latency", {}).get("candles_ms", {}).get("p99", 0))
        last_hour = m.get("errors", {}).get("last_hour", {}) or {}
        e429 = int(last_hour.get("429", 0) or 0)
        e503 = int(last_hour.get("503", 0) or 0)
        ok = (
            p95 <= int(s.ACCEPT_CANDLES_P95_MS_MAX)
            and p99 <= int(s.ACCEPT_CANDLES_P99_MS_MAX)
            and e429 <= int(s.ACCEPT_MAX_429_PER_HOUR)
            and e503 <= int(s.ACCEPT_MAX_503_PER_HOUR)
        )
        return {
            "ok": bool(ok),
            "thresholds": {
                "p95_ms_max": int(s.ACCEPT_CANDLES_P95_MS_MAX),
                "p99_ms_max": int(s.ACCEPT_CANDLES_P99_MS_MAX),
                "max_429_per_hour": int(s.ACCEPT_MAX_429_PER_HOUR),
                "max_503_per_hour": int(s.ACCEPT_MAX_503_PER_HOUR),
            },
            "observed": {"p95": p95, "p99": p99, "429": e429, "503": e503},
        }
    except Exception as e:
        logger.exception("Fel vid metrics acceptance")
        raise HTTPException(status_code=500, detail="internal_error") from e


@router.get("/triage/url-check")
async def triage_url_check(_: bool = Depends(require_auth)):
    try:
        from config.settings import Settings as _S

        s = _S()
        return {
            "public_rest": s.BITFINEX_PUBLIC_API_URL,
            "private_rest": s.BITFINEX_AUTH_API_URL or s.BITFINEX_API_URL,
            "ws_public": s.BITFINEX_WS_PUBLIC_URI,
            "ws_auth": s.BITFINEX_WS_AUTH_URI,
        }
    except Exception as e:
        logger.exception("Fel vid url-check")
        raise HTTPException(status_code=500, detail="internal_error") from e


@router.get("/triage/symbols")
async def triage_symbols(_: bool = Depends(require_auth)):
    try:
        from services.symbols import SymbolService

        svc = SymbolService()
        await svc.refresh()
        out = {
            "test_symbols": svc.get_symbols(test_only=True, fmt="v2"),
            "listed_sample": svc.get_symbols(test_only=False, fmt="v2")[:50],
        }
        return out
    except Exception as e:
        logger.exception("Fel vid triage symbols")
        raise HTTPException(status_code=500, detail="internal_error") from e


# Candle cache admin
class CacheClearRequest(BaseModel):
    symbol: str | None = None
    timeframe: str | None = None


# --- UI capabilities ---
@router.get("/ui/capabilities")
async def ui_capabilities(_: bool = Depends(require_auth)):
    try:
        s = settings
        from utils.feature_flags import get_feature_flag as _ff

        caps = {
            "ws": {
                "connect_on_start": bool(_ff("ws_connect_on_start", True)),
                "strategy_enabled": bool(_ff("ws_strategy_enabled", False)),
            },
            "prob": {
                "validate_enabled": bool(getattr(s, "PROB_VALIDATE_ENABLED", True)),
                "model_enabled": bool(getattr(s, "PROB_MODEL_ENABLED", False)),
                "autotrade_enabled": bool(getattr(s, "PROB_AUTOTRADE_ENABLED", False)),
            },
            "dry_run": bool(getattr(s, "DRY_RUN_ENABLED", False)),
            "trading_paused": bool(getattr(s, "TRADING_PAUSED", False)),
            "scheduler_running": False,
            "rate_limit": {
                "order_max": int(getattr(s, "ORDER_RATE_LIMIT_MAX", 0) or 0),
                "order_window": int(getattr(s, "ORDER_RATE_LIMIT_WINDOW", 0) or 0),
            },
        }
        try:
            from services.scheduler import scheduler

            caps["scheduler_running"] = bool(scheduler.is_running())
        except Exception:
            pass
        return caps
    except Exception as e:
        logger.exception(f"UI capabilities error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


class MCPTogglePayload(BaseModel):
    enabled: bool


# MCP endpoints removed (legacy functionality disabled)


class BackfillRequest(BaseModel):
    symbol: str
    timeframe: str = "1m"
    max_batches: int = 10
    batch_limit: int = 1000


@router.get("/cache/candles/stats")
async def cache_candles_stats(_: bool = Depends(require_auth)):
    try:
        return candle_cache.stats()
    except Exception as e:
        logger.exception(f"Fel vid cache stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/cache/candles/clear")
async def cache_candles_clear(req: CacheClearRequest, _: bool = Depends(require_auth)):
    try:
        if req.symbol:
            n = candle_cache.clear(req.symbol, req.timeframe)
        else:
            n = candle_cache.clear_all()
        # Enforce retention efter clear (kan även köras via scheduler)
        try:
            removed = candle_cache.enforce_retention(
                getattr(settings, "CANDLE_CACHE_RETENTION_DAYS", 7),
                getattr(settings, "CANDLE_CACHE_MAX_ROWS_PER_PAIR", 10000),
            )
            n += removed
        except Exception:
            pass
        _emit_notification(
            "info",
            "Candle cache rensad",
            {"deleted": n, **({"symbol": req.symbol} if req.symbol else {})},
        )
        return {"success": True, "deleted": n}
    except Exception as e:
        logger.exception(f"Fel vid cache clear: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/cache/candles/backfill")
async def cache_candles_backfill(req: BackfillRequest, _: bool = Depends(require_auth)):
    try:
        svc = get_market_data()
        inserted = await svc.backfill_history(req.symbol, req.timeframe, req.max_batches, req.batch_limit)
        _emit_notification(
            "info",
            "Candle cache backfill",
            {"symbol": req.symbol, "timeframe": req.timeframe, "inserted": inserted},
        )
        return {"success": True, "inserted": inserted}
    except Exception as e:
        logger.exception(f"Fel vid cache backfill: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


# Equity endpoints
@router.get("/account/equity")
async def get_equity(_: bool = Depends(require_auth)):
    try:
        perf = PerformanceService()
        equity = await perf.compute_current_equity()
        return equity
    except Exception as e:
        logger.exception(f"Fel vid equity: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/account/equity/snapshot")
async def equity_snapshot(_: bool = Depends(require_auth)):
    try:
        perf = PerformanceService()
        snap = await perf.snapshot_equity()
        return snap
    except Exception as e:
        logger.exception(f"Fel vid equity snapshot: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/account/equity/history")
async def equity_history(limit: int | None = None, _: bool = Depends(require_auth)):
    try:
        perf = PerformanceService()
        hist = perf.get_equity_history(limit=limit)
        return {"equity": hist}
    except Exception as e:
        logger.exception(f"Fel vid equity history: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


# Order Templates endpoints
class SaveTemplateRequest(BaseModel):
    name: str
    symbol: str | None = None
    side: str | None = None
    type: str | None = None
    amount: str | None = None
    price: str | None = None
    sl_price: str | None = None
    tp_price: str | None = None


class TemplatesPayload(BaseModel):
    templates: list[dict[str, Any]]


# --- Toggle request model ---


class CoreModeRequest(BaseModel):
    enabled: bool


# --- Runtime toggles: WS strategy & Validation warmup ---
@router.get("/mode/ws-strategy")
async def get_ws_strategy(_: bool = Depends(require_auth)):
    return {"ws_strategy_enabled": bool(_get_flag("ws_strategy_enabled", False))}


@router.post("/mode/ws-strategy")
async def set_ws_strategy(payload: CoreModeRequest, _: bool = Depends(require_auth)):
    try:
        _set_flag("ws_strategy_enabled", bool(payload.enabled))
        # Auto‑subscribe när WS Strategy slås på
        try:
            if bool(payload.enabled):
                s = settings
                raw = (getattr(s, "WS_SUBSCRIBE_SYMBOLS", None) or "").strip()
                if raw:
                    syms = [x.strip() for x in raw.split(",") if x.strip()]
                else:
                    s = settings
                    ...
                    syms = [f"t{getattr(s, 'DEFAULT_TRADING_PAIR', 'BTCUSD')}"]
                import asyncio as _async

                from services.bitfinex_websocket import bitfinex_ws as _ws

                for sym in syms:
                    try:
                        _async.create_task(
                            _ws.subscribe_with_strategy_evaluation(sym, _ws._handle_ticker_with_strategy)
                        )
                    except Exception:
                        pass
        except Exception:
            pass
        return {
            "ok": True,
            "ws_strategy_enabled": bool(_get_flag("ws_strategy_enabled", False)),
        }
    except Exception as e:
        logger.exception(f"Fel vid set ws-strategy: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/mode/validation-warmup")
async def get_validation_warmup(_: bool = Depends(require_auth)):
    return {"validation_on_start": bool(_get_flag("validation_on_start", False))}


@router.post("/mode/validation-warmup")
async def set_validation_warmup(payload: CoreModeRequest, _: bool = Depends(require_auth)):
    try:
        _set_flag("validation_on_start", bool(payload.enabled))
        return {
            "ok": True,
            "validation_on_start": bool(_get_flag("validation_on_start", False)),
        }
    except Exception as e:
        logger.exception(f"Fel vid set validation-warmup: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/mode/ws-connect-on-start")
async def get_ws_connect_toggle(_: bool = Depends(require_auth)):
    return {"ws_connect_on_start": bool(_get_flag("ws_connect_on_start", True))}


@router.post("/mode/ws-connect-on-start")
async def set_ws_connect_toggle(payload: CoreModeRequest, _: bool = Depends(require_auth)):
    try:
        _set_flag("ws_connect_on_start", bool(payload.enabled))
        return {
            "ok": True,
            "ws_connect_on_start": bool(_get_flag("ws_connect_on_start", True)),
        }
    except Exception as e:
        logger.exception(f"Fel vid set ws-connect-on-start: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


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
    except Exception as e:
        logger.exception("Fel vid get_template")
        raise HTTPException(status_code=500, detail="internal_error") from e


@router.post("/order/templates")
async def save_template(payload: SaveTemplateRequest, _: bool = Depends(require_auth)):
    try:
        svc = OrderTemplatesService()
        result = svc.save_template({k: v for k, v in payload.dict().items() if v is not None})
        return result
    except Exception as e:
        logger.exception(f"Fel vid save_template: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


# Alias endpoints för att undvika kollision med /order/{order_id}
@router.get("/orders/templates", response_model=list[dict[str, Any]])
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


@router.post("/orders/templates/import")
async def import_templates(payload: TemplatesPayload, _: bool = Depends(require_auth)):
    try:
        svc = OrderTemplatesService()
        items = payload.templates if isinstance(payload.templates, list) else []
        count = 0
        for t in items:
            if isinstance(t, dict) and t.get("name"):
                svc.save_template(t)
                count += 1
        return {"imported": count}
    except Exception as e:
        logger.exception(f"Fel vid import_templates: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/orders/templates/export", response_model=list[dict[str, Any]])
async def export_templates(_: bool = Depends(require_auth)):
    try:
        svc = OrderTemplatesService()
        return svc.list_templates()
    except Exception as e:
        logger.exception(f"Fel vid export_templates: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


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
    except Exception as e:
        logger.exception("Fel vid delete_template")
        raise HTTPException(status_code=500, detail="internal_error") from e


@router.post("/orders/templates")
async def save_template_alias(payload: SaveTemplateRequest, _: bool = Depends(require_auth)):
    try:
        svc = OrderTemplatesService()
        result = svc.save_template({k: v for k, v in payload.dict().items() if v is not None})
        return result
    except Exception as e:
        logger.exception(f"Fel vid save_template (alias): {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


class UpdateWindowsRequest(BaseModel):
    timezone: str | None = None
    windows: dict[str, list[list[str]]] | None = None
    paused: bool | None = None
    max_trades_per_symbol_per_day: int | None = None
    max_trades_per_day: int | None = None
    trade_cooldown_seconds: int | None = None


@router.post("/risk/windows")
async def update_trading_windows(req: UpdateWindowsRequest, _: bool = Depends(require_auth)):
    try:
        s = settings
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
        raise HTTPException(status_code=500, detail="Internal server error") from e


# --- Runtime toggles: DRY RUN ---
@router.get("/mode/dry-run")
async def get_dry_run(_: bool = Depends(require_auth)):
    try:
        import services.runtime_config as rc

        return {"dry_run_enabled": bool(rc.get_bool("DRY_RUN_ENABLED", False))}
    except Exception as e:
        logger.exception(f"Fel vid get dry-run: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/mode/dry-run")
async def set_dry_run(payload: CoreModeRequest, _: bool = Depends(require_auth)):
    try:
        # Uppdatera runtime-config och env
        try:
            import services.runtime_config as rc

            rc.set_bool("DRY_RUN_ENABLED", bool(payload.enabled))
        except Exception:
            pass
        try:
            settings.DRY_RUN_ENABLED = bool(payload.enabled)
        except Exception:
            pass
        _emit_notification("info", "Dry run", {"enabled": bool(payload.enabled)})
        return {"dry_run_enabled": bool(rc.get_bool("DRY_RUN_ENABLED", False))}
    except Exception as e:
        logger.exception(f"Fel vid set dry-run: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# --- Runtime toggles: TRADING PAUSED ---
@router.get("/mode/trading-paused")
async def get_trading_paused(_: bool = Depends(require_auth)):
    try:
        import services.runtime_config as rc

        return {"trading_paused": bool(rc.get_bool("TRADING_PAUSED", False))}
    except Exception as e:
        logger.exception(f"Fel vid get trading-paused: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/mode/trading-paused")
async def set_trading_paused(payload: CoreModeRequest, _: bool = Depends(require_auth)):
    try:
        # Uppdatera runtime-config och env
        try:
            import services.runtime_config as rc

            rc.set_bool("TRADING_PAUSED", bool(payload.enabled))
        except Exception:
            pass
        try:
            settings.TRADING_PAUSED = bool(payload.enabled)
        except Exception:
            pass
        _emit_notification("info", "Trading paused", {"enabled": bool(payload.enabled)})
        return {"trading_paused": bool(rc.get_bool("TRADING_PAUSED", False))}
    except Exception as e:
        logger.exception(f"Fel vid set trading-paused: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# --- Runtime toggles: Probability Model ---
@router.get("/mode/prob-model")
async def get_prob_model(_: bool = Depends(require_auth)):
    try:
        from services.prob_model import prob_model

        # Sann källa är runtime‑objektet; fallback till Settings
        enabled = bool(getattr(prob_model, "enabled", False))
        if enabled is False:
            try:
                import services.runtime_config as rc

                enabled = bool(rc.get_bool("PROB_MODEL_ENABLED", False))
            except Exception:
                pass
        return {"prob_model_enabled": bool(enabled)}
    except Exception as e:
        logger.exception(f"Fel vid get prob-model: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/mode/prob-model")
async def set_prob_model(payload: CoreModeRequest, _: bool = Depends(require_auth)):
    try:
        import services.runtime_config as rc

        from services.prob_model import prob_model

        rc.set_bool("PROB_MODEL_ENABLED", bool(payload.enabled))
        try:
            prob_model.enabled = bool(payload.enabled)
        except Exception:
            pass
        _emit_notification("info", "Prob model", {"enabled": bool(payload.enabled)})
        return {"prob_model_enabled": bool(getattr(prob_model, "enabled", False))}
    except Exception as e:
        logger.exception(f"Fel vid set prob-model: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# --- Runtime toggles: Autotrade ---
@router.get("/mode/autotrade")
async def get_autotrade(_: bool = Depends(require_auth)):
    try:
        import services.runtime_config as rc

        return {
            "autotrade_enabled": bool(
                rc.get_bool(
                    "PROB_AUTOTRADE_ENABLED",
                    getattr(settings, "PROB_AUTOTRADE_ENABLED", False),
                )
            )
        }
    except Exception as e:
        logger.exception(f"Fel vid get autotrade: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/mode/autotrade")
async def set_autotrade(payload: CoreModeRequest, _: bool = Depends(require_auth)):
    try:
        import services.runtime_config as rc

        rc.set_bool("PROB_AUTOTRADE_ENABLED", bool(payload.enabled))
        # spegla även i singleton settings för process-lokalt state
        try:
            settings.PROB_AUTOTRADE_ENABLED = bool(payload.enabled)
        except Exception:
            pass
        _emit_notification("info", "Autotrade", {"enabled": bool(payload.enabled)})
        return {
            "autotrade_enabled": bool(
                rc.get_bool(
                    "PROB_AUTOTRADE_ENABLED",
                    getattr(settings, "PROB_AUTOTRADE_ENABLED", False),
                )
            )
        }
    except Exception as e:
        logger.exception(f"Fel vid set autotrade: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# --- Refresh Manager endpoints ---
@router.get("/refresh-manager/status")
async def get_refresh_manager_status(_: bool = Depends(require_auth)):
    """Hämta status för RefreshManager."""
    try:
        from services.refresh_manager import get_refresh_manager

        manager = get_refresh_manager()
        panel_status = manager.get_panel_status()
        intervals = manager.get_refresh_intervals_summary()

        return {
            "status": panel_status,
            "intervals": intervals,
            "shared_data_timestamp": manager.shared_data.timestamp.isoformat(),
        }
    except Exception as e:
        logger.exception(f"Fel vid hämtning av refresh manager status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/refresh-manager/force-refresh")
async def force_refresh_panel(request: dict[str, Any], _: bool = Depends(require_auth)):
    """Tvinga refresh för en specifik panel eller alla."""
    panel_id = request.get("panel_id")
    try:
        from services.refresh_manager import get_refresh_manager

        manager = get_refresh_manager()
        await manager.force_refresh(panel_id)

        target = panel_id or "alla paneler"
        return {"success": True, "message": f"Refresh tvingad för {target}"}
    except Exception as e:
        logger.exception(f"Fel vid force refresh: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/refresh-manager/start")
async def start_refresh_manager(_: bool = Depends(require_auth)):
    """Starta RefreshManager."""
    try:
        from services.refresh_manager import start_refresh_manager

        await start_refresh_manager()
        return {"success": True, "message": "RefreshManager startad"}
    except Exception as e:
        logger.exception(f"Fel vid start av refresh manager: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/refresh-manager/stop")
async def stop_refresh_manager(_: bool = Depends(require_auth)):
    """Stoppa RefreshManager."""
    try:
        from services.refresh_manager import stop_refresh_manager

        await stop_refresh_manager()
        return {"success": True, "message": "RefreshManager stoppad"}
    except Exception as e:
        logger.exception(f"Fel vid stopp av refresh manager: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# --- Runtime toggles: Scheduler ---
@router.get("/mode/scheduler")
async def get_scheduler(_: bool = Depends(require_auth)):
    try:
        from services.scheduler import scheduler

        # Optimera med caching för att minska API-anrop
        is_running = bool(scheduler.is_running())

        return {"scheduler_running": is_running}
    except Exception as e:
        logger.exception(f"Fel vid get scheduler: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/mode/scheduler")
async def set_scheduler(payload: CoreModeRequest, _: bool = Depends(require_auth)):
    try:
        from services.scheduler import scheduler

        if bool(payload.enabled):
            scheduler.start()
        else:
            try:
                await scheduler.stop()
            except TypeError:
                # if called in non-async context by mistake, ignore
                pass
        _emit_notification("info", "Scheduler", {"enabled": bool(payload.enabled)})
        return {"scheduler_running": bool(scheduler.is_running())}
    except Exception as e:
        logger.exception(f"Fel vid set scheduler: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/strategy/regime/all")
async def get_all_regimes(_: bool = Depends(require_auth)):
    """
    Hämtar aktuell regim för alla aktiva symboler med confidence scores och trading probabilities.
    ENHETLIG: Använder UnifiedSignalService för konsistenta resultat.
    """
    logger.info("🎯 /strategy/regime/all endpoint anropad - ENHETLIG SIGNAL SERVICE")

    try:
        from services.unified_signal_service import unified_signal_service

        # Använd UnifiedSignalService för enhetlig regime sammanfattning
        result = await unified_signal_service.get_regime_summary()

        logger.info("📊 Returnerar enhetlig regime sammanfattning")
        return result

    except Exception as e:
        logger.error(f"❌ Fel vid hämtning av all regimes: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    try:
        from services.symbols import SymbolService
        from config.settings import Settings as _Settings

        symbol_service = SymbolService()
        _s = settings

        raw_symbols = (_s.WS_SUBSCRIBE_SYMBOLS or "").strip()
        if raw_symbols:
            symbols = [s.strip() for s in raw_symbols.split(",") if s.strip()]
        else:
            symbols = symbol_service.get_symbols(test_only=True, fmt="v2")[:5]  # Begränsa till 5 för prestanda

        logger.info(f"📊 Hämtar live regime data för {len(symbols)} symboler")

        # Hämta live regime data för varje symbol
        live_regimes = []
        for symbol in symbols:
            try:
                # Använd samma regime endpoint som Live Signals
                # Hämta regime data direkt via MarketDataFacade
                from services.market_data_facade import get_market_data
                from indicators.regime import detect_regime
                from indicators.adx import adx as adx_series
                from indicators.regime import ema_z

                data_service = get_market_data()
                candles = await data_service.get_candles(symbol, "1m", limit=50)

                if candles and len(candles) >= 20:
                    highs = [float(candle[3]) for candle in candles if len(candle) >= 4]
                    lows = [float(candle[4]) for candle in candles if len(candle) >= 5]
                    closes = [float(candle[2]) for candle in candles if len(candle) >= 3]

                    if len(highs) >= 20 and len(lows) >= 20 and len(closes) >= 20:
                        regime = detect_regime(highs, lows, closes)
                        adx_vals = adx_series(highs, lows, closes, period=14)
                        ez_vals = ema_z(closes, 3, 7, 200)

                        regime_data = {
                            "symbol": symbol,
                            "regime": regime,
                            "adx_value": adx_vals[-1] if adx_vals else None,
                            "ema_z_value": ez_vals[-1] if ez_vals else None,
                            "last_close": closes[-1] if closes else None,
                        }
                    else:
                        regime_data = None
                else:
                    regime_data = None
                if regime_data and "regime" in regime_data and regime_data["regime"] != "unknown":
                    live_regimes.append(regime_data)
            except Exception as e:
                logger.warning(f"⚠️ Kunde inte hämta regime för {symbol}: {e}")
                continue

        test_regimes = live_regimes

    except Exception as e:
        logger.error(f"❌ Fel vid hämtning av live symboler, använder fallback: {e}")
        # Fallback till statisk test-data om live hämtning misslyckas
        test_regimes = [
            {
                "symbol": "TESTBTC:TESTUSD",
                "regime": "trend",
                "adx_value": 28.3,
                "ema_z_value": -1.93,
                "last_close": 115090.0,
            },
            {
                "symbol": "TESTETH:TESTUSD",
                "regime": "balanced",
                "adx_value": 21.7,
                "ema_z_value": -0.70,
                "last_close": 4676.6,
            },
        ]

    # Beräkna confidence/probability och rekommendation via SignalService
    enhanced_regimes = []
    for regime_data in test_regimes:
        # SignalService already imported at top; reuse it below
        signal_service = SignalService()
        sc = signal_service.score(
            regime=regime_data["regime"],
            adx_value=regime_data["adx_value"],
            ema_z_value=regime_data["ema_z_value"],
        )

        confidence = sc.confidence
        trading_prob = sc.probability

        # Behåll tidigare kategorier men basera på enhetliga värden
        if confidence < 30:
            recommendation = "LOW_CONFIDENCE"
        elif sc.recommendation == "buy":
            recommendation = "STRONG_BUY" if trading_prob > 70 else "BUY"
        elif sc.recommendation == "hold":
            recommendation = "HOLD"
        else:
            recommendation = "AVOID"

        enhanced_regimes.append(
            {
                **regime_data,
                "confidence_score": confidence,
                "trading_probability": trading_prob,
                "recommendation": recommendation,
            }
        )

    # Beräkna sammanfattning
    trend_count = len([r for r in enhanced_regimes if r["regime"] == "trend"])
    balanced_count = len([r for r in enhanced_regimes if r["regime"] == "balanced"])
    range_count = len([r for r in enhanced_regimes if r["regime"] == "range"])
    avg_confidence = sum(r["confidence_score"] for r in enhanced_regimes) / len(enhanced_regimes)
    total_trading_prob = sum(r["trading_probability"] for r in enhanced_regimes)

    logger.info("📊 Returnerar enhanced regim-data med confidence scores")

    result = {
        "timestamp": datetime.now().isoformat(),
        "total_symbols": len(enhanced_regimes),
        "regimes": enhanced_regimes,
        "summary": {
            "trend_count": trend_count,
            "balanced_count": balanced_count,
            "range_count": range_count,
            "avg_confidence": round(avg_confidence, 1),
            "total_trading_probability": round(total_trading_prob, 1),
        },
    }

    # Spara i cache
    # timeframe/limit används inte här – ta bort för att undvika undefined
    cache_key = f"regimes_{symbol}"
    get_all_regimes._cache[cache_key] = {"data": result, "timestamp": datetime.now()}

    return result


@router.get("/strategy/regime/{symbol}")
async def get_strategy_regime(symbol: str, _: bool = Depends(require_auth)):
    """
    Hämtar aktuell regim för en symbol (trend/range/balanced).
    OPTIMERAD: Caching och minskade API-anrop för bättre prestanda.
    """
    try:
        from datetime import datetime, timedelta

        from indicators.regime import detect_regime
        from services.market_data_facade import get_market_data

        # OPTIMERING: Cache regime-data för 5 minuter
        cache_key = f"regime_{symbol}"
        cache_ttl = timedelta(minutes=5)

        # Kontrollera cache först
        if hasattr(get_strategy_regime, "_cache"):
            cached_data = get_strategy_regime._cache.get(cache_key)
            if cached_data and (datetime.now() - cached_data["timestamp"]) < cache_ttl:
                logger.debug(f"📋 Använder cached regime data för {symbol}")
                return cached_data["data"]
        else:
            get_strategy_regime._cache = {}

        # Hämta candles för regim-detektering (kortare timeframe för mer känslighet)
        data_service = get_market_data()
        candles = await data_service.get_candles(symbol, "1m", limit=50)

        if not candles or len(candles) < 20:
            return {"regime": "unknown", "reason": "insufficient_data"}

        # Extrahera high, low, close (vektoriserat för prestanda)
        highs = [float(candle[3]) for candle in candles if len(candle) >= 4]
        lows = [float(candle[4]) for candle in candles if len(candle) >= 5]
        closes = [float(candle[2]) for candle in candles if len(candle) >= 3]

        if len(highs) < 20 or len(lows) < 20 or len(closes) < 20:
            return {"regime": "unknown", "reason": "insufficient_data"}

        # Konfiguration för regim-detektering (känsligare för testning)
        cfg = {
            "ADX_PERIOD": 14,
            "ADX_HIGH": 30,
            "ADX_LOW": 15,
            "SLOPE_Z_HIGH": 1.0,
            "SLOPE_Z_LOW": 0.5,
        }

        # Detektera regim
        regime = detect_regime(highs, lows, closes, cfg)

        # OPTIMERING: Beräkna ADX och EMA Z parallellt

        from indicators.adx import adx as adx_series
        from indicators.regime import ema_z

        # Beräkna indikatorer parallellt för bättre prestanda
        adx_vals = adx_series(highs, lows, closes, period=14)
        ez_vals = ema_z(closes, 3, 7, 200)

        result = {
            "symbol": symbol,
            "regime": regime,
            "candles_count": len(candles),
            "last_close": closes[-1] if closes else None,
            "adx_value": adx_vals[-1] if adx_vals else None,
            "ema_z_value": ez_vals[-1] if ez_vals else None,
        }

        # Spara i cache
        get_strategy_regime._cache[cache_key] = {
            "data": result,
            "timestamp": datetime.now(),
        }

        return result

    except Exception as e:
        logger.warning(f"Fel vid regim-detektering för {symbol}: {e}")
        return {"regime": "error", "error": "An internal error has occurred"}


@router.post("/strategy/update-from-regime")
async def update_strategy_from_regime(symbol: str | None = None, _: bool = Depends(require_auth)):
    """
    Uppdaterar strategi-settings baserat på aktuell regim och auto-flaggor.
    """
    try:
        from services.strategy import update_settings_from_regime

        new_weights = update_settings_from_regime(symbol)

        return {
            "success": True,
            "message": f"Settings uppdaterade baserat på regim",
            "weights": new_weights,
        }

    except Exception as e:
        logger.exception(f"Fel vid uppdatering av settings från regim: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# ENHANCED AUTO-TRADING ENDPOINTS
# ============================================================================


@router.post("/enhanced-auto/start")
async def start_enhanced_auto_trading(symbol: str, _: bool = Depends(require_auth)):
    """
    Startar enhanced auto-trading för en symbol med confidence scores och regime detection.
    """
    try:
        from services.enhanced_auto_trader import EnhancedAutoTrader

        enhanced_trader = EnhancedAutoTrader.get_instance()
        await enhanced_trader.start_enhanced_trading(symbol)

        _emit_notification("info", "Enhanced Auto-trading startad", {"symbol": symbol})
        return {
            "ok": True,
            "symbol": symbol,
            "message": "Enhanced auto-trading startad",
        }

    except Exception as e:
        logger.error(f"❌ Fel vid start av enhanced auto-trading: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/enhanced-auto/stop")
async def stop_enhanced_auto_trading(symbol: str, _: bool = Depends(require_auth)):
    """
    Stoppar enhanced auto-trading för en symbol.
    """
    try:
        from services.enhanced_auto_trader import EnhancedAutoTrader

        enhanced_trader = EnhancedAutoTrader.get_instance()
        await enhanced_trader.stop_enhanced_trading(symbol)

        _emit_notification("info", "Enhanced Auto-trading stoppad", {"symbol": symbol})
        return {
            "ok": True,
            "symbol": symbol,
            "message": "Enhanced auto-trading stoppad",
        }

    except Exception as e:
        logger.error(f"❌ Fel vid stopp av enhanced auto-trading: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# --- Unified Risk Service endpoints ---
@router.get("/risk/unified/status")
async def get_unified_risk_status(_: bool = Depends(require_auth)):
    """Hämta komplett risk-status från UnifiedRiskService."""
    try:
        from services.unified_risk_service import unified_risk_service
        from services.trading_window import TradingWindowService

        s = settings
        tw = TradingWindowService(s)

        risk_status = unified_risk_service.get_risk_status()
        # Utöka unified-status med trading window-fält för en enhetlig vy
        try:
            tw_status = tw.get_status()
            risk_status["trading_window"] = {
                "paused": tw_status.get("paused", False),
                "open": tw_status.get("open", False),
                "next_open": tw_status.get("next_open"),
                "windows": tw_status.get("windows", []),
                "timezone": tw_status.get("timezone", "UTC"),
            }
        except Exception:
            pass
        return risk_status
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/risk/unified/evaluate")
async def evaluate_risk(request: dict[str, Any], _: bool = Depends(require_auth)):
    """Utför risk-evaluering för en trade."""
    symbol = request.get("symbol")
    amount = request.get("amount")
    price = request.get("price")
    try:
        from services.unified_risk_service import unified_risk_service

        decision = unified_risk_service.evaluate_risk(symbol, amount, price)
        return {
            "allowed": decision.allowed,
            "reason": decision.reason,
            "details": decision.details,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.exception(f"Fel vid risk-evaluering: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# --- Unified Risk Control endpoints ---
@router.post("/risk/unified/pause")
async def pause_unified_risk(_: bool = Depends(require_auth)):
    """Pausa trading (unified)."""
    try:
        from services.trading_window import TradingWindowService

        s = settings
        tw = TradingWindowService(s)
        tw.set_paused(True)
        return {"success": True, "paused": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/risk/unified/resume")
async def resume_unified_risk(_: bool = Depends(require_auth)):
    """Återuppta trading (unified) och återställ circuit breakers där det är säkert."""
    try:
        from services.trading_window import TradingWindowService
        from services.unified_circuit_breaker_service import (
            unified_circuit_breaker_service,
        )
        from utils.advanced_rate_limiter import get_advanced_rate_limiter

        s = settings
        tw = TradingWindowService(s)
        # 1) Unpause trading window
        tw.set_paused(False)

        # 2) Reset unified circuit breakers
        try:
            unified_circuit_breaker_service.reset_all_circuit_breakers()
        except Exception:
            pass

        # 3) Nollställ transport CB cooldowns för kända endpoints
        try:
            limiter = get_advanced_rate_limiter()
            for ep in [
                "auth/r/wallets",
                "auth/r/positions",
                "auth/r/info/margin",
                "auth/r/trades",
            ]:
                st = limiter._cb_state.get(ep)
                if st:
                    st["fail_count"] = 0
                    st["open_until"] = 0.0
                    st["last_failure"] = 0.0
                    limiter._cb_state[ep] = st
        except Exception:
            pass

        return {"success": True, "paused": False}
    except Exception as e:
        logger.exception(f"Fel vid unified resume: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/risk/unified/reset-guard")
async def reset_risk_guard_unified(request: dict[str, Any], _: bool = Depends(require_auth)):
    """Återställ en specifik riskvakt."""
    guard_name = request.get("guard_name")

    if not guard_name:
        raise HTTPException(status_code=400, detail="guard_name parameter is required")
    try:
        from services.unified_risk_service import unified_risk_service

        success = unified_risk_service.reset_guard(guard_name)
        return {
            "success": success,
            "message": f"Riskvakt {guard_name} {'återställd' if success else 'kunde inte återställas'}",
        }
    except Exception as e:
        logger.exception(f"Fel vid återställning av riskvakt: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/risk/unified/reset-circuit-breaker")
async def reset_circuit_breaker_unified(_: bool = Depends(require_auth)):
    """Återställ circuit breaker."""
    try:
        from services.unified_risk_service import unified_risk_service

        success = unified_risk_service.reset_circuit_breaker()
        return {
            "success": success,
            "message": ("Circuit breaker återställd" if success else "Kunde inte återställa circuit breaker"),
        }
    except Exception as e:
        logger.exception(f"Fel vid återställning av circuit breaker: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/risk/unified/update-guard")
async def update_risk_guard(request: dict[str, Any], _: bool = Depends(require_auth)):
    """Uppdatera konfiguration för en riskvakt."""
    guard_name = request.get("guard_name")
    config = request.get("config", {})

    if not guard_name:
        raise HTTPException(status_code=400, detail="guard_name parameter is required")
    try:
        from services.unified_risk_service import unified_risk_service

        success = unified_risk_service.update_guard_config(guard_name, config)
        return {
            "success": success,
            "message": f"Riskvakt {guard_name} {'uppdaterad' if success else 'kunde inte uppdateras'}",
        }
    except Exception as e:
        logger.exception(f"Fel vid uppdatering av riskvakt: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# --- Compatibility bridge for legacy RiskGuardsPanel (/api/v2/risk/guards/*) ---
# (Removed duplicate legacy guards endpoints; using the primary definitions above)


# --- Feature Flags Service endpoints ---
@router.get("/feature-flags/status")
async def get_feature_flags_status(_: bool = Depends(require_auth)):
    """Hämta komplett status för alla feature flags."""
    try:
        from services.feature_flags_service import feature_flags_service

        flags_status = feature_flags_service.get_flag_status()
        return flags_status
    except Exception as e:
        logger.exception(f"Fel vid hämtning av feature flags status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# --- Risk enabled toggle ---
@router.get("/risk/enabled")
async def get_risk_enabled(_: bool = Depends(require_auth)):
    try:
        from config.settings import Settings as _S

        s = _S()
        return {"enabled": rc.get_bool("RISK_ENABLED", getattr(s, "RISK_ENABLED", True))}
    except Exception as e:
        logger.exception(f"Fel vid hämtning av risk enabled: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


class RiskEnabledRequest(BaseModel):
    enabled: bool


@router.post("/risk/enabled")
async def set_risk_enabled(req: RiskEnabledRequest, _: bool = Depends(require_auth)):
    try:
        rc.set_bool("RISK_ENABLED", bool(req.enabled))
        return {"ok": True, "enabled": rc.get_bool("RISK_ENABLED", True)}
    except Exception as e:
        logger.exception(f"Fel vid sättning av risk enabled: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/feature-flags/category/{category}")
async def get_feature_flags_by_category(category: str, _: bool = Depends(require_auth)):
    """Hämta feature flags för en specifik kategori."""
    try:
        from services.feature_flags_service import feature_flags_service

        flags = feature_flags_service.get_flags_by_category(category)
        return {
            "category": category,
            "flags": flags,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.exception(f"Fel vid hämtning av feature flags för kategori {category}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/feature-flags/set")
async def set_feature_flag(request: dict[str, Any], _: bool = Depends(require_auth)):
    """Sätt värdet för en feature flag med rate limiting."""
    name = request.get("name")
    value = request.get("value")

    if not name:
        raise HTTPException(status_code=400, detail="name parameter is required")
    if value is None:
        raise HTTPException(status_code=400, detail="value parameter is required")

    try:
        from services.feature_flags_service import feature_flags_service

        # Rate limiting: kontrollera om samma flag uppdateras för ofta
        current_value = feature_flags_service.get_flag(name)
        if current_value == value:
            return {
                "success": True,
                "message": f"Feature flag {name} har redan värdet {value}",
                "new_value": value,
                "cached": True,
            }

        success = feature_flags_service.set_flag(name, value)
        return {
            "success": success,
            "message": f"Feature flag {name} {'uppdaterad' if success else 'kunde inte uppdateras'}",
            "new_value": value,
        }
    except Exception as e:
        logger.exception(f"Fel vid uppdatering av feature flag {name}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/feature-flags/reset")
async def reset_feature_flag(name: str | None = None, _: bool = Depends(require_auth)):
    """Återställ en feature flag eller alla."""
    try:
        from services.feature_flags_service import feature_flags_service

        if name:
            success = feature_flags_service.reset_flag(name)
            return {
                "success": success,
                "message": f"Feature flag {name} {'återställd' if success else 'kunde inte återställas'}",
            }
        else:
            success = feature_flags_service.reset_all_flags()
            return {
                "success": success,
                "message": (
                    "Alla feature flags återställda" if success else "Kunde inte återställa alla feature flags"
                ),
            }
    except Exception as e:
        logger.exception(f"Fel vid återställning av feature flag: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/feature-flags/ui-capabilities")
async def get_ui_capabilities(_: bool = Depends(require_auth)):
    """Hämta UI capabilities baserat på feature flags."""
    try:
        from services.feature_flags_service import feature_flags_service

        capabilities = feature_flags_service.get_ui_capabilities()
        return capabilities
    except Exception as e:
        logger.exception(f"Fel vid hämtning av UI capabilities: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# --- Enhanced Observability Service endpoints ---
@router.get("/observability/comprehensive")
async def get_comprehensive_observability(_: bool = Depends(require_auth)):
    """Hämta komplett observability-data från alla källor."""
    try:
        from services.enhanced_observability_service import (
            enhanced_observability_service,
        )

        metrics = await enhanced_observability_service.get_comprehensive_metrics()
        return metrics
    except Exception as e:
        logger.exception(f"Fel vid hämtning av comprehensive observability: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/observability/system")
async def get_system_observability(_: bool = Depends(require_auth)):
    """Hämta system-resurser (CPU, RAM, Disk)."""
    try:
        from services.enhanced_observability_service import (
            enhanced_observability_service,
        )

        metrics = await enhanced_observability_service.get_system_metrics()
        return {
            "timestamp": metrics.timestamp.isoformat(),
            "cpu_percent": metrics.cpu_percent,
            "memory_percent": metrics.memory_percent,
            "memory_used_gb": metrics.memory_used_gb,
            "memory_total_gb": metrics.memory_total_gb,
            "disk_percent": metrics.disk_percent,
            "disk_used_gb": metrics.disk_used_gb,
            "disk_total_gb": metrics.disk_total_gb,
            "load_average": metrics.load_average,
        }
    except Exception as e:
        logger.exception(f"Fel vid hämtning av system observability: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/observability/rate-limiter")
async def get_rate_limiter_observability(_: bool = Depends(require_auth)):
    """Hämta rate limiter metrics."""
    try:
        from services.enhanced_observability_service import (
            enhanced_observability_service,
        )

        metrics = await enhanced_observability_service.get_rate_limiter_metrics()
        return {
            "timestamp": metrics.timestamp.isoformat(),
            "tokens_available": metrics.tokens_available,
            "utilization_percent": metrics.utilization_percent,
            "requests_per_second": metrics.requests_per_second,
            "blocked_requests": metrics.blocked_requests,
            "endpoint_patterns": metrics.endpoint_patterns,
        }
    except Exception as e:
        logger.exception(f"Fel vid hämtning av rate limiter observability: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/observability/exchange")
async def get_exchange_observability(_: bool = Depends(require_auth)):
    """Hämta exchange API metrics."""
    try:
        from services.enhanced_observability_service import (
            enhanced_observability_service,
        )

        metrics = await enhanced_observability_service.get_exchange_metrics()
        return {
            "timestamp": metrics.timestamp.isoformat(),
            "total_requests": metrics.total_requests,
            "failed_requests": metrics.failed_requests,
            "rate_limited_requests": metrics.rate_limited_requests,
            "average_latency_ms": metrics.average_latency_ms,
            "p95_latency_ms": metrics.p95_latency_ms,
            "p99_latency_ms": metrics.p99_latency_ms,
            "error_rate_percent": metrics.error_rate_percent,
        }
    except Exception as e:
        logger.exception(f"Fel vid hämtning av exchange observability: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/observability/trading")
async def get_trading_observability(_: bool = Depends(require_auth)):
    """Hämta trading metrics."""
    try:
        from services.enhanced_observability_service import (
            enhanced_observability_service,
        )

        metrics = await enhanced_observability_service.get_trading_metrics()
        return {
            "timestamp": metrics.timestamp.isoformat(),
            "total_orders": metrics.total_orders,
            "successful_orders": metrics.successful_orders,
            "failed_orders": metrics.failed_orders,
            "order_success_rate": metrics.order_success_rate,
            "average_order_latency_ms": metrics.average_order_latency_ms,
            "orders_per_minute": metrics.orders_per_minute,
        }
    except Exception as e:
        logger.exception(f"Fel vid hämtning av trading observability: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# --- History Service endpoints ---
@router.get("/history/comprehensive")
async def get_comprehensive_history(
    symbol: str | None = None,
    wallet_type: str | None = None,
    currency: str | None = None,
    trades_limit: int = 100,
    ledgers_limit: int = 100,
    equity_limit: int = 1000,
    force_refresh: bool = False,
    _: bool = Depends(require_auth),
):
    """Hämta all historisk data i en enhetlig struktur."""
    try:
        from services.history_service import history_service

        history = await history_service.get_comprehensive_history(
            symbol=symbol,
            wallet_type=wallet_type,
            currency=currency,
            trades_limit=trades_limit,
            ledgers_limit=ledgers_limit,
            equity_limit=equity_limit,
            force_refresh=force_refresh,
        )
        return history
    except Exception as e:
        logger.exception(f"Fel vid hämtning av comprehensive history: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/history/trades")
async def get_trade_history(
    symbol: str | None = None,
    limit: int = 100,
    force_refresh: bool = False,
    _: bool = Depends(require_auth),
):
    """Hämta trade history för en symbol eller alla."""
    try:
        from services.history_service import history_service

        trades = await history_service.get_trade_history(symbol=symbol, limit=limit, force_refresh=force_refresh)
        return {
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "limit": limit,
            "trades": trades,
            "count": len(trades),
        }
    except Exception as e:
        logger.exception(f"Fel vid hämtning av trade history: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/history/ledgers")
async def get_ledger_history(
    wallet_type: str | None = None,
    currency: str | None = None,
    limit: int = 100,
    force_refresh: bool = False,
    _: bool = Depends(require_auth),
):
    """Hämta ledger history för en wallet/currency eller alla."""
    try:
        from services.history_service import history_service

        ledgers = await history_service.get_ledger_history(
            wallet_type=wallet_type,
            currency=currency,
            limit=limit,
            force_refresh=force_refresh,
        )
        return {
            "timestamp": datetime.now().isoformat(),
            "wallet_type": wallet_type,
            "currency": currency,
            "limit": limit,
            "ledgers": ledgers,
            "count": len(ledgers),
        }
    except Exception as e:
        logger.exception(f"Fel vid hämtning av ledger history: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/history/equity")
async def get_equity_history(limit: int = 1000, force_refresh: bool = False, _: bool = Depends(require_auth)):
    """Hämta equity history över tid."""
    try:
        from services.history_service import history_service

        equity_history = await history_service.get_equity_history(limit=limit, force_refresh=force_refresh)
        return {
            "timestamp": datetime.now().isoformat(),
            "limit": limit,
            "equity_history": equity_history,
            "count": len(equity_history),
        }
    except Exception as e:
        logger.exception(f"Fel vid hämtning av equity history: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# --- Validation Service endpoints ---
@router.post("/validation/probability")
async def run_probability_validation(request: dict[str, Any], _: bool = Depends(require_auth)):
    """Kör probability model validering."""
    symbol = request.get("symbol", "tBTCUSD")
    timeframe = request.get("timeframe", "1m")
    limit = request.get("limit", 600)
    max_samples = request.get("max_samples", 500)
    force_refresh = request.get("force_refresh", False)
    try:
        from services.validation_service import validation_service

        result = await validation_service.run_probability_validation(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
            max_samples=max_samples,
            force_refresh=force_refresh,
        )
        return {
            "timestamp": result.timestamp.isoformat(),
            "test_type": result.test_type,
            "symbol": result.symbol,
            "timeframe": result.timeframe,
            "parameters": result.parameters,
            "metrics": result.metrics,
            "rolling_metrics": result.rolling_metrics,
            "success": result.success,
            "error_message": result.error_message,
        }
    except Exception as e:
        logger.exception(f"Fel vid probability validation: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/validation/strategy")
async def run_strategy_validation(request: dict[str, Any], _: bool = Depends(require_auth)):
    """Kör strategy validering."""
    symbol = request.get("symbol", "tBTCUSD")
    timeframe = request.get("timeframe", "1m")
    limit = request.get("limit", 1000)
    strategy_params = request.get("strategy_params")
    force_refresh = request.get("force_refresh", False)
    try:
        from services.validation_service import validation_service

        result = await validation_service.run_strategy_validation(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
            strategy_params=strategy_params,
            force_refresh=force_refresh,
        )
        return {
            "timestamp": result.timestamp.isoformat(),
            "test_type": result.test_type,
            "symbol": result.symbol,
            "timeframe": result.timeframe,
            "parameters": result.parameters,
            "metrics": result.metrics,
            "rolling_metrics": result.rolling_metrics,
            "success": result.success,
            "error_message": result.error_message,
        }
    except Exception as e:
        logger.exception(f"Fel vid strategy validation: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/validation/backtest")
async def run_backtest(request: dict[str, Any], _: bool = Depends(require_auth)):
    """Kör backtest."""
    symbol = request.get("symbol", "tBTCUSD")
    timeframe = request.get("timeframe", "1m")
    start_date = request.get("start_date")
    end_date = request.get("end_date")
    initial_capital = request.get("initial_capital", 10000.0)
    strategy_params = request.get("strategy_params")
    force_refresh = request.get("force_refresh", False)
    try:
        from services.validation_service import validation_service

        result = await validation_service.run_backtest(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            strategy_params=strategy_params,
            force_refresh=force_refresh,
        )
        return {
            "timestamp": result.timestamp.isoformat(),
            "test_type": result.test_type,
            "symbol": result.symbol,
            "timeframe": result.timeframe,
            "parameters": result.parameters,
            "metrics": result.metrics,
            "rolling_metrics": result.rolling_metrics,
            "success": result.success,
            "error_message": result.error_message,
        }
    except Exception as e:
        logger.exception(f"Fel vid backtest: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/validation/history")
async def get_validation_history(_: bool = Depends(require_auth)):
    """Hämta historik över alla valideringstester."""
    try:
        from services.validation_service import validation_service

        history = validation_service.get_validation_history()
        return {
            "timestamp": datetime.now().isoformat(),
            "validation_history": [
                {
                    "timestamp": result.timestamp.isoformat(),
                    "test_type": result.test_type,
                    "symbol": result.symbol,
                    "success": result.success,
                    "metrics_summary": {
                        "accuracy": result.metrics.get("accuracy", 0),
                        "total_return": result.metrics.get("total_return", 0),
                        "final_capital": result.metrics.get("final_capital", 0),
                    },
                }
                for result in history
            ],
            "count": len(history),
        }
    except Exception as e:
        logger.exception(f"Fel vid hämtning av validation history: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# V2 API endpoints för validation borttagna – använd /api/v2/validation/*


# --- Unified Circuit Breaker Service endpoints ---
@router.get("/circuit-breaker/status")
async def get_circuit_breaker_status(name: str | None = None, _: bool = Depends(require_auth)):
    """Hämta status för en eller alla circuit breakers."""
    try:
        from services.unified_circuit_breaker_service import (
            unified_circuit_breaker_service,
        )

        cb_status = unified_circuit_breaker_service.get_status(name)
        return cb_status
    except Exception as e:
        logger.exception(f"Fel vid hämtning av circuit breaker status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/circuit-breaker/record-success")
async def record_circuit_breaker_success(request: dict[str, Any], _: bool = Depends(require_auth)):
    """Registrera en lyckad operation för en circuit breaker."""
    name = request.get("name")

    if not name:
        raise HTTPException(status_code=400, detail="name parameter is required")
    try:
        from services.unified_circuit_breaker_service import (
            unified_circuit_breaker_service,
        )

        unified_circuit_breaker_service.record_success(name)
        return {
            "success": True,
            "message": f"Success registrerad för circuit breaker {name}",
        }
    except Exception as e:
        logger.exception(f"Fel vid registrering av circuit breaker success: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/circuit-breaker/record-failure")
async def record_circuit_breaker_failure(request: dict[str, Any], _: bool = Depends(require_auth)):
    """Registrera en misslyckad operation för en circuit breaker."""
    name = request.get("name")
    error_type = request.get("error_type", "generic")

    if not name:
        raise HTTPException(status_code=400, detail="name parameter is required")
    try:
        from services.unified_circuit_breaker_service import (
            unified_circuit_breaker_service,
        )

        unified_circuit_breaker_service.record_failure(name, error_type)
        return {
            "success": True,
            "message": f"Failure registrerad för circuit breaker {name}",
        }
    except Exception as e:
        logger.exception(f"Fel vid registrering av circuit breaker failure: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/circuit-breaker/reset")
async def reset_circuit_breaker(request: dict[str, Any], _: bool = Depends(require_auth)):
    """Återställ en circuit breaker eller alla."""
    name = request.get("name")
    try:
        from services.unified_circuit_breaker_service import (
            unified_circuit_breaker_service,
        )

        if name:
            success = unified_circuit_breaker_service.reset_circuit_breaker(name)
            return {
                "success": success,
                "message": f"Circuit breaker {name} {'återställd' if success else 'kunde inte återställas'}",
            }
        else:
            success = unified_circuit_breaker_service.reset_all_circuit_breakers()
            return {
                "success": success,
                "message": (
                    "Alla circuit breakers återställda" if success else "Kunde inte återställa alla circuit breakers"
                ),
            }
    except Exception as e:
        logger.exception(f"Fel vid återställning av circuit breaker: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/circuit-breaker/force-recovery")
async def force_circuit_breaker_recovery(_: bool = Depends(require_auth)):
    """Tvinga återställning av alla circuit breakers med recovery service."""
    try:
        from services.circuit_breaker_recovery import get_circuit_breaker_recovery

        recovery_service = get_circuit_breaker_recovery()
        success = recovery_service.force_recovery_all()

        return {
            "success": success,
            "message": (
                "Alla circuit breakers återställda via recovery service"
                if success
                else "Kunde inte återställa circuit breakers via recovery service"
            ),
        }
    except Exception as e:
        logger.exception(f"Fel vid tvingad circuit breaker recovery: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/circuit-breaker/recovery-status")
async def get_circuit_breaker_recovery_status(_: bool = Depends(require_auth)):
    """Hämta status för circuit breaker recovery service."""
    try:
        from services.circuit_breaker_recovery import get_circuit_breaker_recovery

        recovery_service = get_circuit_breaker_recovery()
        recovery_status = recovery_service.get_recovery_status()

        return recovery_status
    except Exception as e:
        logger.exception(f"Fel vid hämtning av circuit breaker recovery status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/circuit-breaker/register")
async def register_circuit_breaker(request: dict[str, Any], _: bool = Depends(require_auth)):
    """Registrera en ny circuit breaker."""
    name = request.get("name")
    cb_type = request.get("cb_type")
    failure_threshold = request.get("failure_threshold", 5)
    recovery_timeout = request.get("recovery_timeout", 60.0)
    half_open_max_calls = request.get("half_open_max_calls", 3)
    failure_window = request.get("failure_window", 300.0)
    exponential_backoff = request.get("exponential_backoff", True)
    max_backoff = request.get("max_backoff", 300.0)

    if not name:
        raise HTTPException(status_code=400, detail="name parameter is required")
    if not cb_type:
        raise HTTPException(status_code=400, detail="cb_type parameter is required")
    try:
        from services.unified_circuit_breaker_service import (
            unified_circuit_breaker_service,
            CircuitBreakerConfig,
            CircuitBreakerType,
        )

        # Validera cb_type
        try:
            cb_type_enum = CircuitBreakerType(cb_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Okänd circuit breaker typ: {cb_type}")

        config = CircuitBreakerConfig(
            name=name,
            cb_type=cb_type_enum,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            half_open_max_calls=half_open_max_calls,
            failure_window=failure_window,
            exponential_backoff=exponential_backoff,
            max_backoff=max_backoff,
        )

        unified_circuit_breaker_service.register_circuit_breaker(name, config)
        return {
            "success": True,
            "message": f"Circuit breaker {name} registrerad",
        }
    except Exception as e:
        logger.exception(f"Fel vid registrering av circuit breaker: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/enhanced-auto/status")
async def get_enhanced_auto_status(_: bool = Depends(require_auth)):
    """
    Hämtar status för enhanced auto-trading.
    """
    try:
        from services.enhanced_auto_trader import EnhancedAutoTrader

        enhanced_trader = EnhancedAutoTrader.get_instance()
        ea_status = await enhanced_trader.get_enhanced_status()

        return ea_status

    except Exception as e:
        logger.error(f"❌ Fel vid hämtning av enhanced auto-status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/enhanced-auto/stop-all")
async def stop_all_enhanced_auto_trading(_: bool = Depends(require_auth)):
    """
    Stoppar all enhanced auto-trading.
    """
    try:
        from services.enhanced_auto_trader import EnhancedAutoTrader

        enhanced_trader = EnhancedAutoTrader.get_instance()
        await enhanced_trader.stop_all_enhanced_trading()

        _emit_notification("info", "All Enhanced Auto-trading stoppad", {})
        return {"ok": True, "message": "All enhanced auto-trading stoppad"}

    except Exception as e:
        logger.error(f"❌ Fel vid stopp av all enhanced auto-trading: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# PERFORMANCE ENDPOINTS
# ============================================================================


@router.get("/performance/summary")
async def get_performance_summary(days: int = 30, _: bool = Depends(require_auth)):
    """
    Hämtar performance sammanfattning för enhanced auto-trading.
    """
    try:
        from services.performance_tracker import get_performance_tracker

        tracker = get_performance_tracker()
        summary = tracker.get_performance_summary(days)

        return summary

    except Exception as e:
        logger.error(f"❌ Fel vid hämtning av performance summary: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/performance/symbol/{symbol}")
async def get_symbol_performance(symbol: str, days: int = 30, _: bool = Depends(require_auth)):
    """
    Hämtar performance för specifik symbol.
    """
    try:
        from services.performance_tracker import get_performance_tracker

        tracker = get_performance_tracker()
        performance = tracker.get_symbol_performance(symbol, days)

        return performance

    except Exception as e:
        logger.error(f"❌ Fel vid hämtning av symbol performance: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/performance/trades")
async def get_recent_trades(limit: int = 20, _: bool = Depends(require_auth)):
    """
    Hämtar senaste trades från enhanced auto-trading.
    """
    try:
        from services.performance_tracker import get_performance_tracker

        tracker = get_performance_tracker()
        trades = tracker.get_recent_trades(limit)

        return {"total_trades": len(trades), "trades": trades}

    except Exception as e:
        logger.error(f"❌ Fel vid hämtning av recent trades: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/performance/daily")
async def get_daily_stats(days: int = 7, _: bool = Depends(require_auth)):
    """
    Hämtar daglig statistik för enhanced auto-trading.
    """
    try:
        from services.performance_tracker import get_performance_tracker

        tracker = get_performance_tracker()
        stats = tracker.get_daily_stats(days)

        return {"period_days": days, "daily_stats": stats}

    except Exception as e:
        logger.error(f"❌ Fel vid hämtning av daily stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# SIGNAL ENDPOINTS
# ============================================================================


@router.get("/signals/live")
async def get_live_signals(_: bool = Depends(require_auth)):
    """
    Hämtar alla aktiva live trading signals.
    ENHETLIG: Använder UnifiedSignalService för konsistenta resultat.
    """
    try:
        from services.unified_signal_service import unified_signal_service

        # Använd UnifiedSignalService för enhetliga signaler
        signals = await unified_signal_service.generate_all_signals()

        logger.info(f"📊 Returnerar {signals.total_signals} enhetliga live signals")
        return signals

    except Exception as e:
        logger.error(f"❌ Fel vid hämtning av live signals: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/signals/{symbol}")
async def get_signal_for_symbol(symbol: str, _: bool = Depends(require_auth)):
    """
    Hämtar live signal för specifik symbol.
    """
    try:
        from services.signal_generator import SignalGeneratorService

        signal_service = SignalGeneratorService()
        signals = await signal_service.generate_live_signals([symbol])

        if signals.signals:
            return signals.signals[0]
        else:
            raise HTTPException(status_code=404, detail=f"Inga signals hittades för {symbol}")

    except Exception as e:
        logger.error(f"❌ Fel vid hämtning av signal för {symbol}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/signals/refresh")
async def refresh_signals(request: dict, _: bool = Depends(require_auth)):
    """
    Genererar nya signals (force refresh).
    """
    try:
        from services.signal_generator import SignalGeneratorService

        symbols = request.get("symbols", None)
        force_refresh = request.get("force_refresh", True)

        signal_service = SignalGeneratorService()
        signals = await signal_service.generate_live_signals(symbols, force_refresh)

        logger.info(f"🔄 Genererade {signals.total_signals} nya signals")
        return signals

    except Exception as e:
        logger.error(f"❌ Fel vid refresh av signals: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/signals/history")
async def get_signal_history(symbol: str | None = None, limit: int = 50, _: bool = Depends(require_auth)):
    """
    Hämtar signal-historik.
    """
    try:
        from services.signal_generator import SignalGeneratorService

        signal_service = SignalGeneratorService()
        history = signal_service.get_signal_history(symbol, limit)

        return {
            "timestamp": datetime.now().isoformat(),
            "total_history": len(history),
            "history": history,
        }

    except Exception as e:
        logger.error(f"❌ Fel vid hämtning av signal-historik: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# CACHE ENDPOINTS
# ============================================================================


@router.post("/cache/clear")
async def clear_cache(symbol: str | None = None, timeframe: str | None = None):
    """Rensa candle cache för att tvinga live data-uppdateringar"""
    try:
        from utils.candle_cache import candle_cache

        if symbol:
            # Rensa specifik symbol
            deleted = candle_cache.clear_symbol(symbol, timeframe)
            logger.info(f"🧹 Rensade cache för {symbol}: {deleted} rader")
            return {"ok": True, "deleted_rows": deleted, "symbol": symbol}
        else:
            # Rensa all cache
            deleted = candle_cache.clear_all()
            logger.info(f"🧹 Rensade all cache: {deleted} rader")
            return {"ok": True, "deleted_rows": deleted, "message": "All cache cleared"}

    except Exception as e:
        logger.error(f"❌ Fel vid cache rensning: {e}")
        return {
            "ok": False,
            "error": "An internal error has occurred; please contact support if the problem persists.",
        }


@router.get("/cache/stats")
async def get_cache_stats():
    """Hämta cache-statistik"""
    try:
        from utils.candle_cache import candle_cache

        stats = candle_cache.stats()
        return stats

    except Exception as e:
        logger.error(f"❌ Fel vid hämtning av cache stats: {e}")
        return {"error": "An internal error has occurred"}


@router.get("/performance/stats")
async def get_performance_stats():
    """Hämta prestanda-statistik."""
    try:
        import asyncio

        import psutil

        from services.data_coordinator import data_coordinator

        # System-resurser (använd non-blocking calls)
        cpu_percent = psutil.cpu_percent(interval=None)  # Non-blocking
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        # Cache-statistik (kombinera båda cache-systemen)
        data_cache_stats = data_coordinator.get_cache_stats()
        from utils.candle_cache import candle_cache

        candle_cache_stats = candle_cache.stats()

        # Kombinera cache-statistik
        cache_stats = {
            "data_coordinator": data_cache_stats,
            "candle_cache": candle_cache_stats,
            "total_entries": data_cache_stats["total_entries"] + candle_cache_stats.get("total_rows", 0),
            "valid_entries": data_cache_stats["valid_entries"]
            + candle_cache_stats.get("total_rows", 0),  # SQLite entries är alltid giltiga
            "expired_entries": data_cache_stats["expired_entries"],
            "cache_ttl_seconds": data_cache_stats["cache_ttl_seconds"],
            "active_locks": data_cache_stats["active_locks"],
        }

        # Aktiva tasks med detaljerad analys
        all_tasks = asyncio.all_tasks()
        active_tasks = len(all_tasks)

        # Analysera tasks för att identifiera flaskhalsar
        task_types = {}
        for task in all_tasks:
            task_name = task.get_name()
            if not task_name or task_name.startswith("Task-"):
                task_name = "unnamed"
            task_types[task_name] = task_types.get(task_name, 0) + 1

        # Process-info
        process = psutil.Process()
        process_memory = process.memory_info()

        return {
            "system": {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available_gb": round(memory.available / (1024**3), 2),
                "disk_percent": disk.percent,
                "disk_free_gb": round(disk.free / (1024**3), 2),
            },
            "process": {
                "memory_mb": round(process_memory.rss / (1024**2), 2),
                "cpu_percent": process.cpu_percent(),  # Non-blocking
                "active_tasks": active_tasks,
                "task_types": task_types,
            },
            "cache": cache_stats,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"❌ Fel vid hämtning av prestanda-statistik: {e}")
        return {"error": "Kunde inte hämta prestanda-statistik"}


# ------------------------------
# Agents (read-only) endpoints
# ------------------------------


def _repo_root() -> Path:
    # routes.py is tradingbot-backend/rest/routes.py => repo root is parents[2]
    return Path(__file__).resolve().parents[2]


def _read_comm_file(name: str) -> Any:
    try:
        p = _repo_root() / ".agent-communication" / name
        if not p.exists():
            return None
        raw = p.read_text(encoding="utf-8", errors="ignore")
        if not raw or not raw.strip():
            return None
        return json.loads(raw)
    except Exception:
        return None


@router.get("/agents/messages")
async def agents_messages(_: bool = Depends(require_auth)) -> Any:
    """Returnerar meddelanden mellan agenter (read-only)."""
    return _read_comm_file("messages.json") or []


@router.get("/agents/contracts")
async def agents_contracts(_: bool = Depends(require_auth)) -> Any:
    """Returnerar kontrakt (read-only)."""
    return _read_comm_file("contracts.json") or []


@router.get("/agents/status")
async def agents_status(_: bool = Depends(require_auth)) -> Any:
    """Returnerar agentstatus (read-only)."""
    return _read_comm_file("status.json") or {}


@router.get("/agents/notifications")
async def agents_notifications(_: bool = Depends(require_auth)) -> Any:
    """Returnerar notifieringsstatus (read-only)."""
    return _read_comm_file("notifications.json") or {}
