from datetime import datetime

from pydantic import BaseModel, Field


class SignalResponse(BaseModel):
    """Response model för enskild trading signal"""

    symbol: str = Field(..., description="Trading symbol (t.ex. tBTCUSD)")
    signal_type: str = Field(..., description="Signal typ: BUY, SELL, HOLD")
    confidence_score: float = Field(..., description="Confidence score 0-100")
    trading_probability: float = Field(..., description="Trading probability 0-100")
    recommendation: str = Field(
        ...,
        description="Rekommendation: STRONG_BUY, BUY, WEAK_BUY, HOLD, AVOID, LOW_CONFIDENCE",
    )
    timestamp: datetime = Field(..., description="När signalen genererades")
    strength: str = Field(..., description="Signal styrka: STRONG, MEDIUM, WEAK")
    reason: str = Field(..., description="Anledning till signal")
    current_price: float | None = Field(None, description="Aktuellt pris")
    adx_value: float | None = Field(None, description="ADX värde")
    ema_z_value: float | None = Field(None, description="EMA Z-score")
    regime: str | None = Field(None, description="Marknadsregim: trend, balanced, range")


class SignalHistory(BaseModel):
    """Model för signal-historik"""

    signal_id: str = Field(..., description="Unikt ID för signalen")
    symbol: str = Field(..., description="Trading symbol")
    signal_type: str = Field(..., description="Signal typ")
    confidence_score: float = Field(..., description="Confidence score")
    trading_probability: float = Field(..., description="Trading probability")
    timestamp: datetime = Field(..., description="När signalen genererades")
    executed: bool = Field(False, description="Om signalen utfördes")
    executed_at: datetime | None = Field(None, description="När signalen utfördes")
    profit_loss: float | None = Field(None, description="Vinst/förlust från signalen")
    status: str = Field("ACTIVE", description="Status: ACTIVE, EXECUTED, CANCELLED, EXPIRED")


class LiveSignalsResponse(BaseModel):
    """Response model för alla live signals"""

    timestamp: datetime = Field(..., description="När signals genererades")
    total_signals: int = Field(..., description="Totalt antal signals")
    active_signals: int = Field(..., description="Antal aktiva signals")
    signals: list[SignalResponse] = Field(..., description="Lista av live signals")
    summary: dict = Field(..., description="Sammanfattning av signals")


class SignalGenerationRequest(BaseModel):
    """Request model för att generera nya signals"""

    symbols: list[str] | None = Field(None, description="Specifika symboler att analysera")
    force_refresh: bool = Field(False, description="Tvinga ny signal generation")
    include_history: bool = Field(False, description="Inkludera signal-historik")


class SignalExecutionRequest(BaseModel):
    """Request model för att utföra en signal"""

    signal_id: str = Field(..., description="ID för signalen att utföra")
    auto_execute: bool = Field(False, description="Automatisk execution")
    position_size: float | None = Field(None, description="Position storlek (override)")
    stop_loss: float | None = Field(None, description="Stop-loss (override)")
    take_profit: float | None = Field(None, description="Take-profit (override)")


class SignalStrength(BaseModel):
    """Model för signal-styrka beräkning"""

    confidence_weight: float = Field(0.4, description="Vikt för confidence score")
    probability_weight: float = Field(0.3, description="Vikt för trading probability")
    regime_weight: float = Field(0.2, description="Vikt för marknadsregim")
    volatility_weight: float = Field(0.1, description="Vikt för volatilitet")


class SignalThresholds(BaseModel):
    """Model för signal-trösklar"""

    strong_signal_min: float = Field(80.0, description="Minimum för STRONG signal")
    medium_signal_min: float = Field(60.0, description="Minimum för MEDIUM signal")
    weak_signal_min: float = Field(40.0, description="Minimum för WEAK signal")
    auto_execute_min: float = Field(85.0, description="Minimum för auto-execution")
    manual_confirm_min: float = Field(70.0, description="Minimum för manuell bekräftelse")
