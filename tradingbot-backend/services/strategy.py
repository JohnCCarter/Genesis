"""
Strategy Service - TradingBot Backend

Denna modul hanterar tradingstrategier och signalgenerering.
Inkluderar strategiutvärdering och orderhantering.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime

from indicators.rsi import calculate_rsi
from indicators.ema import calculate_ema
from indicators.atr import calculate_atr
from utils.logger import get_logger

logger = get_logger(__name__)

def evaluate_weighted_strategy(data: Dict[str, str]) -> Dict[str, Any]:
    """
    Beräknar en viktad signal baserat på förberäknade indikator-signaler.

    - EMA väger 40%
    - RSI väger 40%
    - ATR väger 20%

    Mappning till poäng:
    - "buy" -> +1
    - "sell" -> -1
    - "neutral" -> 0
    - ATR-specifika värden som "high"/"low" tolkas som neutral (0) då de beskriver volatilitet, inte riktning

    Args:
        data: Dict med nycklarna "ema", "rsi", "atr" där värdena är str-signaler

    Returns:
        Dict med:
            - signal: "buy" | "sell" | "hold"
            - probabilities: {"buy": float, "sell": float, "hold": float}
    """

    def map_signal_to_score(label: Optional[str]) -> int:
        if label is None:
            return 0
        normalized = str(label).strip().lower()
        if normalized in ("buy",):
            return 1
        if normalized in ("sell",):
            return -1
        # ATR-specifika värden – behandlas som neutral riktning
        if normalized in ("high", "low", "volatile", "calm"):
            return 0
        return 0

    # Hämta dynamiska vikter om tillgängligt
    try:
        from services.strategy_settings import StrategySettingsService
        settings_service = StrategySettingsService()
        s = settings_service.get_settings()
        weights = {"ema": s.ema_weight, "rsi": s.rsi_weight, "atr": s.atr_weight}
    except Exception:
        weights = {"ema": 0.4, "rsi": 0.4, "atr": 0.2}

    ema_score = map_signal_to_score(data.get("ema"))
    rsi_score = map_signal_to_score(data.get("rsi"))
    atr_score = map_signal_to_score(data.get("atr"))

    weighted_score = (
        weights["ema"] * ema_score
        + weights["rsi"] * rsi_score
        + weights["atr"] * atr_score
    )

    if weighted_score > 0:
        final_signal = "buy"
    elif weighted_score < 0:
        final_signal = "sell"
    else:
        final_signal = "hold"

    confidence = abs(max(min(weighted_score, 1.0), -1.0))  # 0..1
    p_hold = max(0.0, 1.0 - confidence)
    p_buy = confidence if final_signal == "buy" else 0.0
    p_sell = confidence if final_signal == "sell" else 0.0

    # Säkerställ normaliserade sannolikheter
    total = p_buy + p_sell + p_hold
    if total > 0:
        p_buy /= total
        p_sell /= total
        p_hold /= total

    return {
        "signal": final_signal,
        "probabilities": {
            "buy": round(p_buy, 6),
            "sell": round(p_sell, 6),
            "hold": round(p_hold, 6),
        },
    }

def evaluate_strategy(data: Dict[str, List[float]]) -> Dict[str, Any]:
    """
    Kombinerar RSI, EMA och ATR för att returnera en sannolikhetssignal.
    
    Args:
        data: Dictionary med prisdata
            - closes: Lista med slutpriser
            - highs: Lista med högsta priser
            - lows: Lista med lägsta priser
            
    Returns:
        Dict med indikatorvärden och trading-signal
    """
    prices = data.get("closes", [])
    highs = data.get("highs", [])
    lows = data.get("lows", [])
    
    if not prices:
        logger.warning("Ingen prisdata tillgänglig för strategiutvärdering")
        return {
            "ema": None,
            "rsi": None,
            "atr": None,
            "signal": "WAIT",
            "reason": "Ingen prisdata"
        }
    
    # Beräkna indikatorer
    ema = calculate_ema(prices)
    rsi = calculate_rsi(prices)
    atr = calculate_atr(highs, lows, prices)

    signal = "WAIT"
    reason = "Standardvärde"

    if ema and rsi and atr:
        current_price = prices[-1]
        
        # Trading-logik
        if rsi < 30 and current_price > ema:
            signal = "BUY"
            reason = f"RSI översåld ({rsi:.2f}) och pris över EMA ({current_price:.4f} > {ema:.4f})"
        elif rsi > 70 and current_price < ema:
            signal = "SELL"
            reason = f"RSI överköpt ({rsi:.2f}) och pris under EMA ({current_price:.4f} < {ema:.4f})"
        elif 40 < rsi < 60:
            signal = "HOLD"
            reason = f"RSI neutral ({rsi:.2f}) - vänta på tydligare signal"
        else:
            signal = "WAIT"
            reason = f"Otydlig signal - RSI: {rsi:.2f}, EMA: {ema:.4f}, ATR: {atr:.4f}"

        # Härleder enkla riktade signaler och använder viktad strategi
        try:
            ema_sig = "buy" if current_price > ema else ("sell" if current_price < ema else "neutral")
            rsi_sig = (
                "buy" if rsi < 30 else ("sell" if rsi > 70 else "neutral")
            )
            # ATR beskriver volatilitet – markera som "high" eller "low" (riktningsneutral för viktningen)
            # Enkel heuristik: hög volatilitet om ATR > 2% av priset
            atr_vol = "high" if (atr / current_price) > 0.02 else "low"
            weighted = evaluate_weighted_strategy({
                "ema": ema_sig,
                "rsi": rsi_sig,
                "atr": atr_vol,
            })
        except Exception as e:
            logger.warning(f"Kunde inte beräkna viktad strategi: {e}")
            weighted = {
                "signal": "hold",
                "probabilities": {"buy": 0.0, "sell": 0.0, "hold": 1.0},
            }
    else:
        reason = f"Otillräcklig data - EMA: {ema}, RSI: {rsi}, ATR: {atr}"
        weighted = {
            "signal": "hold",
            "probabilities": {"buy": 0.0, "sell": 0.0, "hold": 1.0},
        }

    result = {
        "ema": ema,
        "rsi": rsi,
        "atr": atr,
        "signal": signal,
        "reason": reason,
        "timestamp": datetime.now().isoformat(),
        "weighted": weighted,
    }
    
    logger.info(f"Strategiutvärdering: {signal} - {reason}")
    return result 