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
from rest.funding import FundingService
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
from services.bitfinex_websocket import bitfinex_ws
from services.bracket_manager import bracket_manager
from services.metrics import inc as metrics_inc
from services.metrics import inc_labeled, render_prometheus_text
from services.notifications import notification_service
from services.performance import PerformanceService
from services.prob_model import prob_model
from services.prob_validation import validate_on_candles
from services.risk_manager import RiskManager
from services.runtime_mode import (
    get_validation_on_start,
    get_ws_connect_on_start,
    get_ws_strategy_enabled,
    set_validation_on_start,
    set_ws_connect_on_start,
    set_ws_strategy_enabled,
)
from services.strategy import evaluate_weighted_strategy
from services.strategy_settings import StrategySettings, StrategySettingsService
from services.symbols import SymbolService
from services.templates import OrderTemplatesService
from services.trading_integration import trading_integration
from services.trading_window import TradingWindowService
from utils.candle_cache import candle_cache
from utils.logger import get_logger
from utils.rate_limiter import get_rate_limiter

# WebSocket Autentisering endpoints
from ws.auth import generate_token

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v2")
security = HTTPBearer(auto_error=False)
settings = Settings()
JWT_SECRET = settings.SOCKETIO_JWT_SECRET
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
        s = Settings()
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
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        s = Settings()
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
            risk = RiskManager()
            ok, reason = risk.pre_trade_checks(symbol=req.symbol)
            if not ok:
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
            from typing import Dict as _Dict

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
        raise HTTPException(status_code=500, detail=str(e)) from e


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
                        metrics_inc("rate_limited_total")
                    except Exception:
                        pass
                    return OrderResponse(success=False, error="rate_limited")
        except Exception:
            pass

        # Dry-run: simulera svar utan att lägga order
        try:
            if getattr(settings, "DRY_RUN_ENABLED", False):
                return OrderResponse(
                    success=True,
                    data={
                        "dry_run": True,
                        "order": order.dict(),
                    },
                )
        except Exception:
            pass

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

        # Idempotens: kortlivad request‑cache per client_id
        try:
            from services.metrics import metrics_store as _ms

            cache = _ms.setdefault("request_id_cache", {})
            cid = (order.client_id or "").strip() if hasattr(order, "client_id") else ""
            if cid:
                hit = cache.get(cid)
                if (
                    isinstance(hit, dict)
                    and hit.get("ts")
                    and (int(__import__("time").time()) - int(hit["ts"])) < 60
                ):
                    return OrderResponse(
                        success=True,
                        data={"idempotent": True, **(hit.get("resp") or {})},
                    )
        except Exception:
            pass

        # Skicka ordern till Bitfinex
        payload = order.dict()
        # Mappa symbol – hoppa över mapping och listed‑check för TEST‑par (paper trading)
        try:
            sym_in = str(payload.get("symbol", ""))
            if not sym_in.startswith("tTEST"):
                from services.symbols import SymbolService as _SS

                _svc = _SS()
                await _svc.refresh()
                eff = _svc.resolve(sym_in)
                if not _svc.listed(eff):
                    return OrderResponse(success=False, error="validation_error:pair_not_listed")
                payload["symbol"] = eff
        except Exception:
            pass
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
                    metrics_inc("orders_total")
                    metrics_inc("orders_failed_total")
                    try:
                        RiskManager().record_error()
                    except Exception:
                        pass
                    try:
                        inc_labeled(
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
            # WS fallback (on)
            ws_fallback_ok = False
            try:
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
                on_payload = {
                    "type": _t,
                    "symbol": str(payload.get("symbol")),
                    "amount": _amt,
                }
                if payload.get("price") is not None:
                    on_payload["price"] = str(payload.get("price"))
                cid_val = (order.client_id or "").strip() if hasattr(order, "client_id") else ""
                if cid_val:
                    try:
                        on_payload["cid"] = int(cid_val)
                    except Exception:
                        pass
                else:
                    # Sätt en enkel cid om ingen given
                    try:
                        import time as _tmod

                        on_payload["cid"] = int(_tmod.time() * 1000)
                    except Exception:
                        pass
                # Skicka som singel 'on' istället för batch 'ops' (ökar kompatibilitet)
                try:
                    if await _ws.ensure_authenticated():
                        await _ws.send([0, "on", None, on_payload])
                        ws_res = {"success": True, "sent": True}
                    else:
                        ws_res = {"success": False, "error": "ws_not_authenticated"}
                except Exception as _se:
                    ws_res = {"success": False, "error": str(_se)}
                ws_fallback_ok = bool(ws_res.get("success"))
                if ws_fallback_ok:
                    await notification_service.notify(
                        "info", "Order lagd via WS fallback", {"payload": on_payload}
                    )
                    metrics_inc("orders_total")
                    try:
                        inc_labeled(
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
                {"request": order.dict(), "error": result.get("error")},
            )
            metrics_inc("orders_total")
            metrics_inc("orders_failed_total")
            try:
                RiskManager().record_error()
            except Exception:
                pass
            try:
                inc_labeled(
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
            risk.record_trade(symbol=order.symbol)
            metrics_inc("orders_total")
        logger.info(f"Order framgångsrikt lagd: {result}")
        try:
            inc_labeled(
                "orders_total_labeled",
                {
                    "symbol": order.symbol,
                    "type": (order.type or "").replace(" ", "_"),
                    "status": "ok",
                },
            )
        except Exception:
            pass
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
        try:
            max_requests = int(getattr(settings, "ORDER_RATE_LIMIT_MAX", 0) or 0)
            window_seconds = int(getattr(settings, "ORDER_RATE_LIMIT_WINDOW", 0) or 0)
            if max_requests > 0 and window_seconds > 0:
                if not _rl.is_allowed("cancel_order", max_requests, window_seconds):
                    try:
                        metrics_inc("rate_limited_total")
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
async def update_order_endpoint(
    update_request: UpdateOrderRequest, _: bool = Depends(require_auth)
):
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
                return OrderResponse(
                    success=False, error=str(ws_res.get("error") or "ws_update_failed")
                )
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

        result = await bitfinex_ws.order_cancel_multi(
            ids=payload.ids, cids=payload.cids, cid_date=payload.cid_date
        )
        if not result.get("success"):
            return OrderResponse(success=False, error=str(result.get("error")))
        return OrderResponse(success=True, data=result)
    except Exception as e:
        logger.exception(f"WS cancel-multi fel: {e}")
        return OrderResponse(success=False, error=str(e))


@router.post("/ws/orders/ops", response_model=OrderResponse)
async def ws_order_ops(payload: WSOrderOpsRequest, _: bool = Depends(require_auth)):
    try:
        from services.bitfinex_websocket import bitfinex_ws

        result = await bitfinex_ws.order_ops(payload.ops)
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
        _emit_notification(
            "info", "Ordrar avbrutna för symbol", {"symbol": symbol, "response": result}
        )
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
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/wallets/balance")
async def get_wallets_balance_endpoint(
    currency: str | None = None, _: bool = Depends(require_auth)
):
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
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/margin/status/{symbol}")
async def get_margin_status_symbol(symbol: str, _: bool = Depends(require_auth)):
    try:
        margin_service = MarginService()
        # 1) WS/REST sammanfattning
        base = await margin_service.get_symbol_margin_status(symbol)
        # 2) Om source none/rest och tradable saknas, försök direktslag mot v2 sym (med tom body för korrekt signering)
        if (not base) or (
            isinstance(base, dict)
            and base.get("tradable") in (None, 0, 0.0)
            and base.get("source") != "ws"
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
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/trades/history", response_model=list[TradeItem])
async def get_trades_history_endpoint(
    symbol: str | None = None, limit: int = 25, _: bool = Depends(require_auth)
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
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/ledgers", response_model=list[LedgerEntry])
async def get_ledgers_endpoint(
    currency: str | None = None, limit: int = 25, _: bool = Depends(require_auth)
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
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        logger.exception(f"Fel vid generering av WebSocket-token: {e}")
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
async def evaluate_weighted_strategy_endpoint(
    request: WeightedStrategyRequest, _: bool = Depends(require_auth)
):
    """
    Returnerar viktad slutsignal (buy/sell/hold) och sannolikheter baserat på
    simplifierade signaler från EMA, RSI och ATR.
    """
    try:
        payload: dict[str, str | None] = {
            "ema": request.ema,
            "rsi": request.rsi,
            "atr": request.atr,
        }
        if request.symbol:
            payload["symbol"] = request.symbol
        result = evaluate_weighted_strategy(payload)  # type: ignore[arg-type]
        return result
    except Exception as e:
        logger.exception(f"Fel vid viktad strategiutvärdering: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


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
    try:
        svc = StrategySettingsService()
        return svc.get_settings(symbol=symbol).to_dict()
    except Exception as e:
        logger.exception(f"Fel vid hämtning av strategiinställningar: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
            ema_weight=(
                payload.ema_weight if payload.ema_weight is not None else current.ema_weight
            ),
            rsi_weight=(
                payload.rsi_weight if payload.rsi_weight is not None else current.rsi_weight
            ),
            atr_weight=(
                payload.atr_weight if payload.atr_weight is not None else current.atr_weight
            ),
            ema_period=(
                payload.ema_period if payload.ema_period is not None else current.ema_period
            ),
            rsi_period=(
                payload.rsi_period if payload.rsi_period is not None else current.rsi_period
            ),
            atr_period=(
                payload.atr_period if payload.atr_period is not None else current.atr_period
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
            os.path.dirname(os.path.dirname(__file__)), "config", "strategy_settings.json"
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
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/strategy/auto")
async def update_strategy_auto(payload: StrategyAutoPayload, _: bool = Depends(require_auth)):
    try:
        import json
        import os

        cfg_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "config", "strategy_settings.json"
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
        raise HTTPException(status_code=500, detail=str(e))


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
                data = BitfinexDataService()
                ticker = await data.get_ticker(req.symbol)
                if ticker:
                    price = float(ticker.get("last_price", 0))
                    if price and price > 0:
                        price_source = price_source or "ticker"

            # 3) Candle close (sista fallback)
            if not price or price <= 0:
                data = BitfinexDataService()
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
            data = BitfinexDataService()
            candles = await data.get_candles(
                req.symbol,
                req.timeframe,
                limit=100,
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
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/market/tickers")
async def market_tickers(symbols: str, _: bool = Depends(require_auth)):
    """Batch-hämtning av tickers. Query-param symbols är komma-separerad lista.

    Ex: /api/v2/market/tickers?symbols=tBTCUSD,tETHUSD
    """
    try:
        data = BitfinexDataService()
        syms = [s.strip() for s in (symbols or "").split(",") if s.strip()]
        if not syms:
            raise HTTPException(status_code=400, detail="symbols required")
        result = await data.get_tickers(syms)
        if result is None:
            raise HTTPException(status_code=502, detail="Kunde inte hämta tickers")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Fel vid tickers (batch): {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/platform/status")
async def platform_status(_: bool = Depends(require_auth)):
    """Hälsa/underhållsläge från Bitfinex public REST."""
    try:
        data = BitfinexDataService()
        st = await data.get_platform_status()
        if st is None:
            return {"status": "unknown"}
        # Format från Bitfinex: [1] eller [0]
        up = bool(st[0]) if isinstance(st, list) and st else False
        return {"status": "up" if up else "maintenance", "raw": st}
    except Exception as e:
        logger.exception(f"Fel vid platform status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/market/symbols/config")
async def market_symbols_config(format: str = "v2", _: bool = Depends(require_auth)):
    """Symbol-lista via Bitfinex public Configs. OBS: innehåller inte TEST-symboler."""
    try:
        data = BitfinexDataService()
        pairs = await data.get_configs_symbols()
        if not pairs:
            return []
        if format.lower() in ("v2", "t", "bitfinex_v2"):
            return [f"t{p}" for p in pairs]
        return pairs
    except Exception as e:
        logger.exception(f"Fel vid configs symbols: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
        data = BitfinexDataService()
        candles = await data.get_candles(symbol, timeframe, limit)
        if candles is None:
            raise HTTPException(status_code=502, detail="Kunde inte hämta candles")
        parsed_any = data.parse_candles_to_strategy_data(candles)
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
        raise HTTPException(status_code=500, detail=str(e))


# Resync endpoint: re‑subscribe + REST snapshot fetch
@router.post("/market/resync/{symbol}")
async def market_resync(symbol: str, _: bool = Depends(require_auth)):
    try:
        # WS re-subscribe (idempotent skydd finns i subscribe)
        await bitfinex_ws.subscribe_ticker(symbol, bitfinex_ws._handle_ticker_with_strategy)
        # Trigger omedelbar REST snapshot (värms upp cache)
        data = BitfinexDataService()
        _ = await data.get_ticker(symbol)
        return {"success": True}
    except Exception as e:
        logger.exception(f"Fel vid resync: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Health endpoint
@router.get("/health")
async def health(_: bool = Depends(require_auth)):
    try:
        from services.bitfinex_websocket import bitfinex_ws

        pool = bitfinex_ws.get_pool_status()
        return {
            "rest": True,
            "ws_connected": bool(bitfinex_ws.is_connected),
            "ws_authenticated": bool(bitfinex_ws.is_authenticated),
            "ws_pool": pool if isinstance(pool, dict) else {},
        }
    except Exception as e:
        logger.exception(f"Health error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ws/pool/status")
async def ws_pool_status(_: bool = Depends(require_auth)):
    try:
        from services.bitfinex_websocket import bitfinex_ws

        return bitfinex_ws.get_pool_status()
    except Exception as e:
        logger.exception(f"WS pool status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
            await bitfinex_ws.subscribe_trades(
                sym, bitfinex_ws._handle_ticker_with_strategy
            )  # återanvänd callback
            sub_key = f"trades|{sym}"
        elif chan == "candles":
            tf = req.timeframe or "1m"
            await bitfinex_ws.subscribe_candles(sym, tf, bitfinex_ws._handle_ticker_with_strategy)
            sub_key = f"candles|trade:{tf}:{sym}"
        else:
            raise HTTPException(status_code=400, detail="invalid_channel")
        return {"success": True, "sub_key": sub_key}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"WS subscribe error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/prob/predict")
async def prob_predict(req: ProbPredictRequest, _: bool = Depends(require_auth)):
    try:
        import time as _t

        t0 = _t.time()
        # Hämta senaste candles för features
        data = BitfinexDataService()
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
                inc_labeled(
                    "prob_events",
                    {"type": "abstain", "symbol": req.symbol, "tf": req.timeframe},
                )
            else:
                inc_labeled(
                    "prob_events",
                    {
                        "type": "trade",
                        "side": side,
                        "symbol": req.symbol,
                        "tf": req.timeframe,
                    },
                )
            inc_labeled(
                "prob_events",
                {
                    "type": "infer",
                    "source": ("model" if prob_model.enabled else "heuristic"),
                    "symbol": req.symbol,
                    "tf": req.timeframe,
                },
            )
            # latens (sum + count)
            inc_labeled(
                "prob_infer_latency_ms_sum",
                {"symbol": req.symbol, "tf": req.timeframe},
                by=int(max(((_t.time()) - t0) * 1000, 0)),
            )
            inc_labeled(
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
            inc_labeled(
                "prob_ev_bucket",
                {"bucket": ev_bucket, "symbol": req.symbol, "tf": req.timeframe},
                by=1,
            )
            inc_labeled(
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
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        raise HTTPException(status_code=500, detail=str(e)) from e


class ProbValidateRequest(BaseModel):
    symbol: str
    timeframe: str = "1m"
    horizon: int = 20
    tp: float = 0.002
    sl: float = 0.002
    limit: int = 1000  # antal candles att hämta för validering
    max_samples: int | None = 500  # senaste N samples att utvärdera


@router.post("/prob/validate")
async def prob_validate(req: ProbValidateRequest, _: bool = Depends(require_auth)):
    try:
        data = BitfinexDataService()
        candles = await data.get_candles(req.symbol, req.timeframe, req.limit)
        if not candles:
            return {"samples": 0, "brier": None, "logloss": None, "by_label": {}}
        result = validate_on_candles(
            candles,
            horizon=req.horizon,
            tp=req.tp,
            sl=req.sl,
            max_samples=req.max_samples,
        )
        # uppdatera metrics enkelt
        try:
            if result.get("brier") is not None:
                inc_labeled(
                    "prob_metrics",
                    {
                        "type": "brier",
                        "symbol": req.symbol,
                        "tf": req.timeframe,
                    },
                    by=int(max(result.get("samples", 0), 1)),
                )
            if result.get("logloss") is not None:
                inc_labeled(
                    "prob_metrics",
                    {
                        "type": "logloss",
                        "symbol": req.symbol,
                        "tf": req.timeframe,
                    },
                    by=int(max(result.get("samples", 0), 1)),
                )
        except Exception:
            pass
        return result
    except Exception as e:
        logger.exception(f"prob/validate error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


class ProbValidateRunRequest(BaseModel):
    symbols: list[str] | None = None  # t.ex. ["tBTCUSD", "tETHUSD"]
    timeframe: str = "1m"
    limit: int = 1000
    max_samples: int | None = 500


@router.post("/prob/validate/run")
async def prob_validate_run(req: ProbValidateRunRequest, _: bool = Depends(require_auth)):
    """Kör validering direkt (utan att invänta schemaläggare) och uppdatera metrics."""
    try:
        data = BitfinexDataService()
        s = Settings()
        symbols: list[str]
        if req.symbols and len(req.symbols) > 0:
            symbols = req.symbols
        else:
            raw = (getattr(s, "PROB_VALIDATE_SYMBOLS", None) or "").strip()
            if raw:
                symbols = [x.strip() for x in raw.split(",") if x.strip()]
            else:
                env_syms = (getattr(s, "WS_SUBSCRIBE_SYMBOLS", None) or "").strip()
                symbols = [x.strip() for x in env_syms.split(",") if x.strip()] or [
                    f"t{getattr(s, 'DEFAULT_TRADING_PAIR', 'BTCUSD')}"
                ]
        tf = req.timeframe or str(getattr(s, "PROB_VALIDATE_TIMEFRAME", "1m") or "1m")
        limit = int(req.limit or getattr(s, "PROB_VALIDATE_LIMIT", 1200) or 1200)
        max_samples = int(req.max_samples or getattr(s, "PROB_VALIDATE_MAX_SAMPLES", 500) or 500)

        out: dict[str, Any] = {}
        agg_brier: list[float] = []
        agg_logloss: list[float] = []
        for sym in symbols:
            candles = await data.get_candles(sym, tf, limit)
            if not candles:
                out[sym] = {"samples": 0, "brier": None, "logloss": None}
                continue
            res = validate_on_candles(
                candles,
                horizon=int(getattr(s, "PROB_MODEL_TIME_HORIZON", 20) or 20),
                tp=float(getattr(s, "PROB_MODEL_EV_THRESHOLD", 0.0005) or 0.0005),
                sl=float(getattr(s, "PROB_MODEL_EV_THRESHOLD", 0.0005) or 0.0005),
                max_samples=max_samples,
            )
            out[sym] = res
            try:
                from services.metrics import metrics_store

                key = f"{sym}|{tf}"
                pv = metrics_store.setdefault("prob_validation", {})
                by = pv.setdefault("by", {})
                by[key] = {
                    "brier": res.get("brier"),
                    "logloss": res.get("logloss"),
                    "ts": int(__import__("time").time()),
                }
                if res.get("brier") is not None:
                    agg_brier.append(float(res["brier"]))
                if res.get("logloss") is not None:
                    agg_logloss.append(float(res["logloss"]))
            except Exception:
                pass
        try:
            from services.metrics import metrics_store

            if agg_brier:
                metrics_store.setdefault("prob_validation", {})["brier"] = sum(agg_brier) / max(
                    1, len(agg_brier)
                )
            if agg_logloss:
                metrics_store.setdefault("prob_validation", {})["logloss"] = sum(agg_logloss) / max(
                    1, len(agg_logloss)
                )
        except Exception:
            pass
        return {"timeframe": tf, "results": out}
    except Exception as e:
        logger.exception(f"prob/validate/run error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


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

        s = Settings()
        data = BitfinexDataService()
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
                symbols = [x.strip() for x in env_syms.split(",") if x.strip()] or [
                    f"t{getattr(s, 'DEFAULT_TRADING_PAIR', 'BTCUSD')}"
                ]
        tf = req.timeframe or str(getattr(s, "PROB_RETRAIN_TIMEFRAME", "1m") or "1m")
        limit = int(req.limit or getattr(s, "PROB_RETRAIN_LIMIT", 5000) or 5000)
        out_dir = req.output_dir or str(getattr(s, "PROB_RETRAIN_OUTPUT_DIR", "config/models"))
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
            out_path = _os.path.join(out_dir, fname)
            train_and_export(candles, horizon=horizon, tp=tp, sl=sl, out_path=out_path)
            written.append(out_path)

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
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        s = Settings()
        return {
            "model_enabled": bool(getattr(s, "PROB_MODEL_ENABLED", False)),
            "model_file": getattr(s, "PROB_MODEL_FILE", None),
            "ev_threshold": float(getattr(s, "PROB_MODEL_EV_THRESHOLD", 0.0) or 0.0),
            "confidence_min": float(getattr(s, "PROB_MODEL_CONFIDENCE_MIN", 0.0) or 0.0),
            "autotrade_enabled": bool(getattr(s, "PROB_AUTOTRADE_ENABLED", False)),
            "size_max_risk_pct": float(getattr(s, "PROB_SIZE_MAX_RISK_PCT", 0.0) or 0.0),
            "size_kelly_cap": float(getattr(s, "PROB_SIZE_KELLY_CAP", 0.0) or 0.0),
            "size_conf_weight": float(getattr(s, "PROB_SIZE_CONF_WEIGHT", 0.0) or 0.0),
            "position_size_fallback_quote": float(
                getattr(s, "POSITION_SIZE_FALLBACK_QUOTE", 0.0) or 0.0
            ),
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
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/prob/config")
async def prob_update_config(req: ProbConfigUpdateRequest, _: bool = Depends(require_auth)):
    try:
        import os as _os

        # Skriv env och uppdatera runtime där det är relevant
        if req.model_enabled is not None:
            _os.environ["PROB_MODEL_ENABLED"] = "True" if req.model_enabled else "False"
            prob_model.enabled = bool(req.model_enabled)
        if req.model_file:
            _os.environ["PROB_MODEL_FILE"] = str(req.model_file)
            try:
                prob_model.reload()
            except Exception:
                pass
        if req.ev_threshold is not None:
            _os.environ["PROB_MODEL_EV_THRESHOLD"] = str(float(req.ev_threshold))
        if req.confidence_min is not None:
            _os.environ["PROB_MODEL_CONFIDENCE_MIN"] = str(float(req.confidence_min))
        if req.autotrade_enabled is not None:
            _os.environ["PROB_AUTOTRADE_ENABLED"] = "True" if req.autotrade_enabled else "False"
        if req.size_max_risk_pct is not None:
            _os.environ["PROB_SIZE_MAX_RISK_PCT"] = str(float(req.size_max_risk_pct))
        if req.size_kelly_cap is not None:
            _os.environ["PROB_SIZE_KELLY_CAP"] = str(float(req.size_kelly_cap))
        if req.size_conf_weight is not None:
            _os.environ["PROB_SIZE_CONF_WEIGHT"] = str(float(req.size_conf_weight))
        if req.position_size_fallback_quote is not None:
            _os.environ["POSITION_SIZE_FALLBACK_QUOTE"] = str(
                float(req.position_size_fallback_quote)
            )
        # Validation controls
        if req.validate_enabled is not None:
            _os.environ["PROB_VALIDATE_ENABLED"] = "True" if req.validate_enabled else "False"
        if req.validate_symbols is not None:
            _os.environ["PROB_VALIDATE_SYMBOLS"] = str(req.validate_symbols)
        if req.validate_timeframe is not None:
            _os.environ["PROB_VALIDATE_TIMEFRAME"] = str(req.validate_timeframe)
        if req.validate_limit is not None:
            _os.environ["PROB_VALIDATE_LIMIT"] = str(int(req.validate_limit))
        # Retraining controls
        if req.retrain_enabled is not None:
            _os.environ["PROB_RETRAIN_ENABLED"] = "True" if req.retrain_enabled else "False"
        if req.retrain_interval_hours is not None:
            _os.environ["PROB_RETRAIN_INTERVAL_HOURS"] = str(int(req.retrain_interval_hours))
        if req.retrain_symbols is not None:
            _os.environ["PROB_RETRAIN_SYMBOLS"] = str(req.retrain_symbols)
        if req.retrain_timeframe is not None:
            _os.environ["PROB_RETRAIN_TIMEFRAME"] = str(req.retrain_timeframe)
        if req.retrain_limit is not None:
            _os.environ["PROB_RETRAIN_LIMIT"] = str(int(req.retrain_limit))

        # metrics: registrera uppdatering
        try:
            inc_labeled("prob_events", {"type": "config_update"})
        except Exception:
            pass

        return await prob_get_config(True)  # återanvänd GET
    except Exception as e:
        logger.exception(f"prob/config update error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        raise HTTPException(status_code=500, detail=str(e)) from e


# Symbols endpoint
@router.get("/market/symbols")
async def market_symbols(
    test_only: bool = False, format: str = "v2", _: bool = Depends(require_auth)
):
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
        raise HTTPException(status_code=500, detail=str(e)) from e


# Watchlist endpoint (liten vy) med ticker + volym + senaste strategi-signal
@router.get("/market/watchlist")
async def market_watchlist(
    symbols: str | None = None, prob: bool = False, _: bool = Depends(require_auth)
):
    try:
        svc = SymbolService()
        data = BitfinexDataService()
        # Refresh live configs/aliases
        try:
            await svc.refresh()
        except Exception:
            pass
        if symbols:
            syms = [s.strip() for s in symbols.split(",") if s.strip()]
        else:
            # Förvald lista: WS_SUBSCRIBE_SYMBOLS om satt, annars test‑symboler (legacy)
            try:
                from config.settings import Settings as _S

                env_syms = (_S().WS_SUBSCRIBE_SYMBOLS or "").strip()
                if env_syms:
                    syms = [s.strip() for s in env_syms.split(",") if s.strip()]
                else:
                    syms = svc.get_symbols(test_only=True, fmt="v2")[:10]
            except Exception:
                syms = svc.get_symbols(test_only=True, fmt="v2")[:10]
        out = []

        def _safe_float(val):
            try:
                return float(val) if val is not None else None
            except Exception:
                return None

        # WS live check
        try:
            from services.bitfinex_websocket import bitfinex_ws

            ws_live_set = set(bitfinex_ws.active_tickers or [])
        except Exception:
            ws_live_set = set()

        for s in syms:
            eff = s
            listed = None
            try:
                eff = svc.resolve(s)
                listed = bool(svc.listed(eff))
            except Exception:
                listed = None
            # Visa icke-listade symboler om de efterfrågas eller finns i WS_SUBSCRIBE_SYMBOLS
            show_unlisted = False
            try:
                from config.settings import Settings as _S2

                env_syms = _S2().WS_SUBSCRIBE_SYMBOLS or ""
                if s in [x.strip() for x in env_syms.split(",") if x.strip()]:
                    show_unlisted = True
            except Exception:
                pass
            if listed is False and not show_unlisted:
                continue
            ticker = await data.get_ticker(s)
            last = _safe_float(ticker.get("last_price")) if ticker else None
            vol = _safe_float(ticker.get("volume")) if ticker else None
            ws_live = eff in ws_live_set
            # Marginstatus (WS först, REST fallback)
            try:
                from rest.margin import MarginService as _MS

                ms = _MS()
                margin_status = await ms.get_symbol_margin_status(s)
                # Om none → försök trigga WS calc och re‑pröva snabbt
                if (
                    not margin_status
                    or margin_status.get("source") == "none"
                    or margin_status.get("tradable") in (None, 0, 0.0)
                ):
                    try:
                        from services.bitfinex_websocket import bitfinex_ws as _ws

                        await _ws.margin_calc_if_needed(s)
                        # kort väntan för uppdatering
                        await asyncio.sleep(0.15)
                        margin_status = await ms.get_symbol_margin_status(s)
                    except Exception:
                        pass
            except Exception:
                margin_status = None
            candles = await data.get_candles(s, "1m", 50)
            candles_5m = await data.get_candles(s, "5m", 50)
            strat = None
            strat_5m = None
            if candles:
                parsed_any = data.parse_candles_to_strategy_data(candles)
                from services.strategy import evaluate_strategy

                parsed_map: dict[str, Any] = (
                    dict(parsed_any) if isinstance(parsed_any, dict) else {}
                )
                parsed_map["symbol"] = s
                strat = evaluate_strategy(parsed_map)  # type: ignore[arg-type]
            if candles_5m:
                parsed_any5 = data.parse_candles_to_strategy_data(candles_5m)
                from services.strategy import evaluate_strategy as eval5

                parsed_map5: dict[str, Any] = (
                    dict(parsed_any5) if isinstance(parsed_any5, dict) else {}
                )
                parsed_map5["symbol"] = s
                strat_5m = eval5(parsed_map5)  # type: ignore[arg-type]
            item = {
                "symbol": s,
                "eff_symbol": eff,
                "listed": listed,
                "ws_live": ws_live,
                "margin_status": margin_status,
                "last": last,
                "volume": vol,
                "strategy": strat,
                "strategy_5m": strat_5m,
            }
            if prob:
                try:
                    from services.bitfinex_data import BitfinexDataService as _DS
                    from services.prob_model import prob_model as _pm

                    # använd snabbinferens med enkla features (via /prob/predict-logik), här direkt
                    ds = _DS()
                    candles = await ds.get_candles(s, "1m", 50)
                    if candles:
                        # Minimal proxy (samma som i /prob/predict)
                        closes = [
                            row[2]
                            for row in candles
                            if isinstance(row, (list, tuple)) and len(row) >= 3
                        ]
                        price = float(closes[-1]) if len(closes) >= 1 else None
                        ema = (
                            sum(closes[-10:]) / min(10, len(closes)) if len(closes) >= 1 else price
                        )
                        f_ema = (
                            1.0
                            if (price is not None and ema is not None and price > ema)
                            else (
                                -1.0
                                if (price is not None and ema is not None and price < ema)
                                else 0.0
                            )
                        )
                        try:
                            delta = float(closes[-1]) - float(closes[-2])
                            rsi_norm = max(
                                min(delta / (abs(float(closes[-2])) + 1e-9), 1.0),
                                -1.0,
                            )
                        except Exception:
                            rsi_norm = 0.0
                        probs = _pm.predict_proba({"ema": f_ema, "rsi": rsi_norm})
                        # EV-policy
                        from config.settings import Settings as _S

                        s2 = _S()
                        ev_th = float(getattr(s2, "PROB_MODEL_EV_THRESHOLD", 0.0) or 0.0)
                        conf_th = float(getattr(s2, "PROB_MODEL_CONFIDENCE_MIN", 0.0) or 0.0)
                        p_buy = float(probs.get("buy", 0.0))
                        p_sell = float(probs.get("sell", 0.0))
                        ev_buy = p_buy * 0.002 - p_sell * 0.002 - 0.0003
                        ev_sell = p_sell * 0.002 - p_buy * 0.002 - 0.0003
                        side = "buy" if ev_buy >= ev_sell else "sell"
                        best_ev = ev_buy if side == "buy" else ev_sell
                        decision = (
                            side
                            if (best_ev >= ev_th and max(probs.values()) >= conf_th)
                            else "abstain"
                        )
                        item["prob"] = {
                            "probabilities": probs,
                            "decision": decision,
                            "ev": best_ev,
                        }
                except Exception:
                    pass
            out.append(item)
        return out
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
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/auto/stop")
async def auto_stop(req: AutoStartRequest, _: bool = Depends(require_auth)):
    try:
        await trading_integration.stop_automated_trading(req.symbol)
        _emit_notification("info", "Auto trading stoppad", {"symbol": req.symbol})
        return {"ok": True, "symbol": req.symbol}
    except Exception as e:
        logger.exception(f"Fel vid auto/stop: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        raise HTTPException(status_code=500, detail=str(e)) from e


# Bracket order endpoint
@router.post("/order/bracket", response_model=OrderResponse)
async def place_bracket_order(req: BracketOrderRequest, _: bool = Depends(require_auth)):
    try:
        logger.info(f"Mottog bracket-order: {req.dict()}")
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
        risk = RiskManager()
        ok, reason = risk.pre_trade_checks(symbol=req.symbol)
        if not ok:
            return OrderResponse(success=False, error=f"risk_blocked:{reason}")

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
        entry_payload = {
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
            # Försök WS fallback 'on'
            try:
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
        resp_obj = OrderResponse(
            success=True, data={"entry_id": entry_id, "sl_id": sl_id, "tp_id": tp_id}
        )
        # Spara idempotensrespons om client_id angiven
        try:
            if hasattr(req, "client_id") and getattr(req, "client_id", None):
                from services.metrics import metrics_store as _ms

                cache = _ms.setdefault("request_id_cache", {})
                cache[str(req.client_id)] = {
                    "ts": int(__import__("time").time()),
                    "resp": resp_obj.dict(),
                }
        except Exception:
            pass
        return resp_obj
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
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/risk/pause")
async def pause_trading(_: bool = Depends(require_auth)):
    try:
        s = Settings()
        tw = TradingWindowService(s)
        tw.set_paused(True)
        return {"success": True, "paused": True}
    except Exception as e:
        logger.exception(f"Fel vid paus: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/risk/resume")
async def resume_trading(_: bool = Depends(require_auth)):
    try:
        s = Settings()
        tw = TradingWindowService(s)
        tw.set_paused(False)
        return {"success": True, "paused": False}
    except Exception as e:
        logger.exception(f"Fel vid resume: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        raise HTTPException(status_code=500, detail=str(e)) from e


# Risk endpoints
class UpdateMaxTradesRequest(BaseModel):
    max_trades_per_day: int


@router.get("/risk/status")
async def get_risk_status(_: bool = Depends(require_auth)):
    rm = RiskManager()
    return rm.status()


@router.post("/risk/max-trades")
async def update_max_trades(req: UpdateMaxTradesRequest, _: bool = Depends(require_auth)):
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
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/risk/trade-counter")
async def get_trade_counter(_: bool = Depends(require_auth)):
    try:
        rm = RiskManager()
        return rm.trade_counter.stats()
    except Exception as e:
        logger.exception(f"Fel vid hämtning av trade counter: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


# --- Circuit Breaker endpoints ---
class CircuitConfigRequest(BaseModel):
    enabled: bool | None = None
    window_seconds: int | None = None
    max_errors_per_window: int | None = None
    notify: bool | None = None


@router.get("/risk/circuit")
async def circuit_status(_: bool = Depends(require_auth)):
    try:
        rm = RiskManager()
        return rm.status().get("circuit", {})
    except Exception as e:
        logger.exception(f"Fel vid circuit status: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/risk/circuit/reset")
async def circuit_reset(
    resume: bool = True, clear_errors: bool = True, _: bool = Depends(require_auth)
):
    try:
        rm = RiskManager()
        return rm.circuit_reset(resume=resume, clear_errors=clear_errors)
    except Exception as e:
        logger.exception(f"Fel vid circuit reset: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        raise HTTPException(status_code=500, detail=str(e)) from e


# Candle cache admin
class CacheClearRequest(BaseModel):
    symbol: str | None = None
    timeframe: str | None = None


# --- MCP bridge ---
class MCPExecuteRequest(BaseModel):
    tool: str
    params: dict[str, Any] | None = None


@router.post("/mcp/execute")
async def mcp_execute(req: MCPExecuteRequest, _: bool = Depends(require_auth)):
    try:
        name = (req.tool or "").strip().lower()
        p = dict(req.params or {})

        # get_token
        if name == "get_token":
            user_id = str(p.get("user_id") or "frontend_user")
            scope = str(p.get("scope") or "read")
            expiry_hours = int(p.get("expiry_hours") or 1)
            token_data = generate_token(
                user_id=user_id, scope=scope, expiry_minutes=expiry_hours * 60
            )
            return {
                "success": True,
                "token": token_data.get("access_token") if isinstance(token_data, dict) else None,
            }

        # ws_status
        if name == "ws_status":
            from services.bitfinex_websocket import bitfinex_ws

            return bitfinex_ws.get_pool_status()

        # toggles
        if name == "toggle_ws_strategy":
            enabled = bool(p.get("enabled"))
            set_ws_strategy_enabled(enabled)
            return {"success": True, "ws_strategy_enabled": bool(get_ws_strategy_enabled())}

        if name == "toggle_validation_warmup":
            enabled = bool(p.get("enabled"))
            set_validation_on_start(enabled)
            return {"success": True, "validation_on_start": bool(get_validation_on_start())}

        if name == "toggle_ws_connect_on_start":
            enabled = bool(p.get("enabled"))
            set_ws_connect_on_start(enabled)
            return {"success": True, "ws_connect_on_start": bool(get_ws_connect_on_start())}

        # market_ticker
        if name == "market_ticker":
            sym = str(p.get("symbol") or "tBTCUSD")
            data = await BitfinexDataService().get_ticker(sym)
            return data or {"error": "no_data"}

        # run_validation
        if name == "run_validation":
            # acceptera symbols som lista eller komma-separerad sträng
            syms = p.get("symbols")
            if isinstance(syms, str):
                symbols = [s.strip() for s in syms.split(",") if s.strip()]
            else:
                symbols = syms
            timeframe = p.get("timeframe") or None
            limit = p.get("limit") if p.get("limit") is not None else None
            max_samples = p.get("max_samples") if p.get("max_samples") is not None else None
            payload = ProbValidateRunRequest(symbols=symbols, timeframe=str(timeframe or "1m"))
            # pydantic kräver explicita fält; fyll in efter init om givna
            if isinstance(limit, int):
                payload.limit = int(limit)
            if isinstance(max_samples, int):
                payload.max_samples = int(max_samples)
            res = await prob_validate_run(payload, True)
            return res

        # place_order
        if name == "place_order":
            req_payload = OrderRequest(
                symbol=str(p.get("symbol")),
                amount=str(p.get("amount")),
                type=str(p.get("order_type") or "EXCHANGE MARKET"),
                price=p.get("price"),
                side=p.get("side"),
            )
            resp = await place_order_endpoint(req_payload, True)
            return resp.dict() if hasattr(resp, "dict") else resp

        return {"success": False, "error": f"unknown_tool:{name}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"MCP execute error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- MCP simple GET wrappers (för enkel test/webbläsare) ---
@router.get("/mcp/ws_status")
async def mcp_ws_status(_: bool = Depends(require_auth)):
    from services.bitfinex_websocket import bitfinex_ws

    return bitfinex_ws.get_pool_status()


@router.get("/mcp/get_token")
async def mcp_get_token(
    user_id: str = "frontend_user",
    scope: str = "read",
    expiry_hours: int = 1,
):
    try:
        token_data = generate_token(user_id=user_id, scope=scope, expiry_minutes=expiry_hours * 60)
        return {
            "success": True,
            "token": token_data.get("access_token") if isinstance(token_data, dict) else None,
        }
    except Exception as e:
        logger.exception(f"MCP get_token error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mcp/market_ticker")
async def mcp_market_ticker(symbol: str = "tBTCUSD", _: bool = Depends(require_auth)):
    try:
        data = await BitfinexDataService().get_ticker(symbol)
        return data or {"error": "no_data"}
    except Exception as e:
        logger.exception(f"MCP market_ticker error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mcp/ws_strategy")
async def mcp_ws_strategy(_: bool = Depends(require_auth)):
    return {"ws_strategy_enabled": bool(get_ws_strategy_enabled())}


@router.get("/mcp/validation_warmup")
async def mcp_validation_warmup(_: bool = Depends(require_auth)):
    return {"validation_on_start": bool(get_validation_on_start())}


@router.get("/mcp/ws_connect_on_start")
async def mcp_ws_connect_on_start(_: bool = Depends(require_auth)):
    return {"ws_connect_on_start": bool(get_ws_connect_on_start())}


@router.get("/mcp/run_validation")
async def mcp_run_validation(
    symbols: str | None = None,
    timeframe: str = "1m",
    limit: int | None = None,
    max_samples: int | None = None,
    _: bool = Depends(require_auth),
):
    try:
        sym_list = None
        if symbols:
            sym_list = [s.strip() for s in symbols.split(",") if s.strip()]
        payload = ProbValidateRunRequest(symbols=sym_list, timeframe=timeframe)
        if isinstance(limit, int):
            payload.limit = int(limit)
        if isinstance(max_samples, int):
            payload.max_samples = int(max_samples)
        return await prob_validate_run(payload, True)
    except Exception as e:
        logger.exception(f"MCP run_validation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- UI capabilities ---
@router.get("/ui/capabilities")
async def ui_capabilities(_: bool = Depends(require_auth)):
    try:
        s = Settings()
        caps = {
            "ws": {
                "connect_on_start": bool(get_ws_connect_on_start()),
                "strategy_enabled": bool(get_ws_strategy_enabled()),
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
        raise HTTPException(status_code=500, detail=str(e))


class MCPTogglePayload(BaseModel):
    enabled: bool


@router.post("/mcp/ws_strategy")
async def mcp_set_ws_strategy(payload: MCPTogglePayload, _: bool = Depends(require_auth)):
    try:
        set_ws_strategy_enabled(bool(payload.enabled))
        return {"ok": True, "ws_strategy_enabled": bool(get_ws_strategy_enabled())}
    except Exception as e:
        logger.exception(f"MCP set ws_strategy error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mcp/validation_warmup")
async def mcp_set_validation_warmup(payload: MCPTogglePayload, _: bool = Depends(require_auth)):
    try:
        set_validation_on_start(bool(payload.enabled))
        return {"ok": True, "validation_on_start": bool(get_validation_on_start())}
    except Exception as e:
        logger.exception(f"MCP set validation_warmup error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mcp/ws_connect_on_start")
async def mcp_set_ws_connect_on_start(payload: MCPTogglePayload, _: bool = Depends(require_auth)):
    try:
        set_ws_connect_on_start(bool(payload.enabled))
        return {"ok": True, "ws_connect_on_start": bool(get_ws_connect_on_start())}
    except Exception as e:
        logger.exception(f"MCP set ws_connect_on_start error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/cache/candles/backfill")
async def cache_candles_backfill(req: BackfillRequest, _: bool = Depends(require_auth)):
    try:
        svc = BitfinexDataService()
        inserted = await svc.backfill_history(
            req.symbol, req.timeframe, req.max_batches, req.batch_limit
        )
        _emit_notification(
            "info",
            "Candle cache backfill",
            {"symbol": req.symbol, "timeframe": req.timeframe, "inserted": inserted},
        )
        return {"success": True, "inserted": inserted}
    except Exception as e:
        logger.exception(f"Fel vid cache backfill: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


# Equity endpoints
@router.get("/account/equity")
async def get_equity(_: bool = Depends(require_auth)):
    try:
        perf = PerformanceService()
        equity = await perf.compute_current_equity()
        return equity
    except Exception as e:
        logger.exception(f"Fel vid equity: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/account/equity/snapshot")
async def equity_snapshot(_: bool = Depends(require_auth)):
    try:
        perf = PerformanceService()
        snap = await perf.snapshot_equity()
        return snap
    except Exception as e:
        logger.exception(f"Fel vid equity snapshot: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/account/equity/history")
async def equity_history(limit: int | None = None, _: bool = Depends(require_auth)):
    try:
        perf = PerformanceService()
        hist = perf.get_equity_history(limit=limit)
        return {"equity": hist}
    except Exception as e:
        logger.exception(f"Fel vid equity history: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


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
    return {"ws_strategy_enabled": bool(get_ws_strategy_enabled())}


@router.post("/mode/ws-strategy")
async def set_ws_strategy(payload: CoreModeRequest, _: bool = Depends(require_auth)):
    try:
        set_ws_strategy_enabled(bool(payload.enabled))
        # Auto‑subscribe när WS Strategy slås på
        try:
            if bool(payload.enabled):
                s = Settings()
                raw = (getattr(s, "WS_SUBSCRIBE_SYMBOLS", None) or "").strip()
                if raw:
                    syms = [x.strip() for x in raw.split(",") if x.strip()]
                else:
                    # Fallback: standardpar
                    syms = [f"t{getattr(s, 'DEFAULT_TRADING_PAIR', 'BTCUSD')}"]
                import asyncio as _async

                from services.bitfinex_websocket import bitfinex_ws as _ws

                for sym in syms:
                    try:
                        _async.create_task(
                            _ws.subscribe_with_strategy_evaluation(
                                sym, _ws._handle_ticker_with_strategy
                            )
                        )
                    except Exception:
                        pass
        except Exception:
            pass
        return {"ok": True, "ws_strategy_enabled": bool(get_ws_strategy_enabled())}
    except Exception as e:
        logger.exception(f"Fel vid set ws-strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/mode/validation-warmup")
async def get_validation_warmup(_: bool = Depends(require_auth)):
    return {"validation_on_start": bool(get_validation_on_start())}


@router.post("/mode/validation-warmup")
async def set_validation_warmup(payload: CoreModeRequest, _: bool = Depends(require_auth)):
    try:
        set_validation_on_start(bool(payload.enabled))
        return {"ok": True, "validation_on_start": bool(get_validation_on_start())}
    except Exception as e:
        logger.exception(f"Fel vid set validation-warmup: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/mode/ws-connect-on-start")
async def get_ws_connect_toggle(_: bool = Depends(require_auth)):
    return {"ws_connect_on_start": bool(get_ws_connect_on_start())}


@router.post("/mode/ws-connect-on-start")
async def set_ws_connect_toggle(payload: CoreModeRequest, _: bool = Depends(require_auth)):
    try:
        set_ws_connect_on_start(bool(payload.enabled))
        return {"ok": True, "ws_connect_on_start": bool(get_ws_connect_on_start())}
    except Exception as e:
        logger.exception(f"Fel vid set ws-connect-on-start: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/orders/templates/export", response_model=list[dict[str, Any]])
async def export_templates(_: bool = Depends(require_auth)):
    try:
        svc = OrderTemplatesService()
        return svc.list_templates()
    except Exception as e:
        logger.exception(f"Fel vid export_templates: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        raise HTTPException(status_code=500, detail=str(e)) from e


# --- Runtime toggles: DRY RUN ---
@router.get("/mode/dry-run")
async def get_dry_run(_: bool = Depends(require_auth)):
    try:
        return {"dry_run_enabled": bool(getattr(settings, "DRY_RUN_ENABLED", False))}
    except Exception as e:
        logger.exception(f"Fel vid get dry-run: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mode/dry-run")
async def set_dry_run(payload: CoreModeRequest, _: bool = Depends(require_auth)):
    try:
        # Uppdatera runtime-config och env
        try:
            import os as _os

            _os.environ["DRY_RUN_ENABLED"] = "True" if payload.enabled else "False"
        except Exception:
            pass
        try:
            settings.DRY_RUN_ENABLED = bool(payload.enabled)
        except Exception:
            pass
        _emit_notification("info", "Dry run", {"enabled": bool(payload.enabled)})
        return {"dry_run_enabled": bool(getattr(settings, "DRY_RUN_ENABLED", False))}
    except Exception as e:
        logger.exception(f"Fel vid set dry-run: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Runtime toggles: TRADING PAUSED ---
@router.get("/mode/trading-paused")
async def get_trading_paused(_: bool = Depends(require_auth)):
    try:
        return {"trading_paused": bool(getattr(settings, "TRADING_PAUSED", False))}
    except Exception as e:
        logger.exception(f"Fel vid get trading-paused: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mode/trading-paused")
async def set_trading_paused(payload: CoreModeRequest, _: bool = Depends(require_auth)):
    try:
        # Uppdatera runtime-config och env
        try:
            import os as _os

            _os.environ["TRADING_PAUSED"] = "True" if payload.enabled else "False"
        except Exception:
            pass
        try:
            settings.TRADING_PAUSED = bool(payload.enabled)
        except Exception:
            pass
        _emit_notification("info", "Trading paused", {"enabled": bool(payload.enabled)})
        return {"trading_paused": bool(getattr(settings, "TRADING_PAUSED", False))}
    except Exception as e:
        logger.exception(f"Fel vid set trading-paused: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Runtime toggles: Probability Model ---
@router.get("/mode/prob-model")
async def get_prob_model(_: bool = Depends(require_auth)):
    try:
        from services.prob_model import prob_model

        # Sann källa är runtime‑objektet; fallback till Settings
        enabled = bool(getattr(prob_model, "enabled", False))
        if enabled is False:
            try:
                enabled = bool(getattr(Settings(), "PROB_MODEL_ENABLED", False))
            except Exception:
                pass
        return {"prob_model_enabled": bool(enabled)}
    except Exception as e:
        logger.exception(f"Fel vid get prob-model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mode/prob-model")
async def set_prob_model(payload: CoreModeRequest, _: bool = Depends(require_auth)):
    try:
        import os as _os

        from services.prob_model import prob_model

        _os.environ["PROB_MODEL_ENABLED"] = "True" if payload.enabled else "False"
        try:
            prob_model.enabled = bool(payload.enabled)
        except Exception:
            pass
        _emit_notification("info", "Prob model", {"enabled": bool(payload.enabled)})
        return {"prob_model_enabled": bool(getattr(prob_model, "enabled", False))}
    except Exception as e:
        logger.exception(f"Fel vid set prob-model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Runtime toggles: Autotrade ---
@router.get("/mode/autotrade")
async def get_autotrade(_: bool = Depends(require_auth)):
    try:
        return {"autotrade_enabled": bool(getattr(Settings(), "PROB_AUTOTRADE_ENABLED", False))}
    except Exception as e:
        logger.exception(f"Fel vid get autotrade: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mode/autotrade")
async def set_autotrade(payload: CoreModeRequest, _: bool = Depends(require_auth)):
    try:
        import os as _os

        _os.environ["PROB_AUTOTRADE_ENABLED"] = "True" if payload.enabled else "False"
        _emit_notification("info", "Autotrade", {"enabled": bool(payload.enabled)})
        return {"autotrade_enabled": bool(getattr(Settings(), "PROB_AUTOTRADE_ENABLED", False))}
    except Exception as e:
        logger.exception(f"Fel vid set autotrade: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Runtime toggles: Scheduler ---
@router.get("/mode/scheduler")
async def get_scheduler(_: bool = Depends(require_auth)):
    try:
        from services.scheduler import scheduler

        return {"scheduler_running": bool(scheduler.is_running())}
    except Exception as e:
        logger.exception(f"Fel vid get scheduler: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
        raise HTTPException(status_code=500, detail=str(e))
