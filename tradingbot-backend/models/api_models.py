"""
API Models - TradingBot Backend

Detta är en centraliserad modul för alla Pydantic-modeller som används i API:et.
Genom att samla alla modeller på ett ställe blir det enklare att återanvända och underhålla dem.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, validator


# Gemensamma enums och konstanter
class WalletType(str, Enum):
    """Enum för plånbokstyper."""

    EXCHANGE = "exchange"
    MARGIN = "margin"
    FUNDING = "funding"


class OrderType(str, Enum):
    """Enum för ordertyper."""

    LIMIT = "LIMIT"
    MARKET = "MARKET"
    STOP = "STOP"
    STOP_LIMIT = "STOP LIMIT"
    TRAILING_STOP = "TRAILING STOP"
    FOK = "FOK"
    IOC = "IOC"
    EXCHANGE_LIMIT = "EXCHANGE LIMIT"
    EXCHANGE_MARKET = "EXCHANGE MARKET"
    EXCHANGE_STOP = "EXCHANGE STOP"
    EXCHANGE_STOP_LIMIT = "EXCHANGE STOP LIMIT"
    EXCHANGE_TRAILING_STOP = "EXCHANGE TRAILING STOP"
    EXCHANGE_FOK = "EXCHANGE FOK"
    EXCHANGE_IOC = "EXCHANGE IOC"


class OrderSide(str, Enum):
    """Enum för ordersidor."""

    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    """Enum för orderstatus."""

    ACTIVE = "ACTIVE"
    EXECUTED = "EXECUTED"
    PARTIALLY_FILLED = "PARTIALLY FILLED"
    CANCELED = "CANCELED"
    POSTONLY_CANCELED = "POSTONLY CANCELED"


class PositionStatus(str, Enum):
    """Enum för positionsstatus."""

    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class TimeFrame(str, Enum):
    """Enum för tidsramar."""

    ONE_MINUTE = "1m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    THIRTY_MINUTES = "30m"
    ONE_HOUR = "1h"
    THREE_HOURS = "3h"
    SIX_HOURS = "6h"
    TWELVE_HOURS = "12h"
    ONE_DAY = "1D"
    ONE_WEEK = "1W"
    TWO_WEEKS = "2W"
    ONE_MONTH = "1M"


# Wallet-modeller
class WalletBalance(BaseModel):
    """Modell för plånbokssaldo."""

    wallet_type: WalletType
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


class WalletSummary(BaseModel):
    """Sammanfattning av plånböcker."""

    total_balance_usd: float
    exchange_wallets: list[WalletBalance]
    margin_wallets: list[WalletBalance]
    funding_wallets: list[WalletBalance]


# Margin-modeller
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
            margin_limits=(
                data[5] if len(data) > 5 and isinstance(data[5], list) else []
            ),
        )


class MarginStatus(BaseModel):
    """Modell för margin-status."""

    margin_balance: float
    net_value: float
    unrealized_pl: float
    required_margin: float
    margin_usage_percent: float
    margin_level: float
    leverage: float
    status: str  # "healthy", "warning", "danger"


# Position-modeller
class Position(BaseModel):
    """Modell för en position."""

    symbol: str
    status: PositionStatus
    amount: float
    base_price: float
    funding: float = 0.0
    funding_type: int = Field(0, description="0 för daily, 1 för term")
    profit_loss: float | None = None
    profit_loss_percentage: float | None = None
    liquidation_price: float | None = None

    @property
    def is_long(self) -> bool:
        """Returnerar True om positionen är long."""
        return self.amount > 0

    @property
    def is_short(self) -> bool:
        """Returnerar True om positionen är short."""
        return self.amount < 0

    @classmethod
    def from_bitfinex_data(cls, data: list) -> "Position":
        """Skapar en Position från Bitfinex API-data."""
        if len(data) < 6:
            raise ValueError(f"Ogiltig positionsdata: {data}")

        return cls(
            symbol=data[0],
            status=data[1],
            amount=float(data[2]),
            base_price=float(data[3]),
            funding=float(data[4]) if len(data) > 4 else 0.0,
            funding_type=int(data[5]) if len(data) > 5 else 0,
            profit_loss=float(data[6]) if len(data) > 6 else None,
            profit_loss_percentage=float(data[7]) if len(data) > 7 else None,
            liquidation_price=float(data[8]) if len(data) > 8 else None,
        )


class PositionHistory(BaseModel):
    """Modell för en historisk position."""

    id: int | None = None
    symbol: str
    status: PositionStatus
    amount: float
    base_price: float
    funding: float = 0.0
    funding_type: int = Field(0, description="0 för daily, 1 för term")
    profit_loss: float | None = None
    profit_loss_percentage: float | None = None
    liquidation_price: float | None = None
    created_at: datetime | None = None
    closed_at: datetime | None = None

    @property
    def is_long(self) -> bool:
        """Returnerar True om positionen är long."""
        return self.amount > 0

    @property
    def is_short(self) -> bool:
        """Returnerar True om positionen är short."""
        return self.amount < 0

    @classmethod
    def from_bitfinex_data(cls, data: list) -> "PositionHistory":
        """Skapar en PositionHistory från Bitfinex API-data."""
        if len(data) < 6:
            raise ValueError(f"Ogiltig positionsdata: {data}")

        # Skapa en grundläggande position
        position = cls(
            symbol=data[0],
            status=data[1],
            amount=float(data[2]) if data[2] is not None else 0.0,
            base_price=float(data[3]) if data[3] is not None else 0.0,
            funding=float(data[4]) if len(data) > 4 and data[4] is not None else 0.0,
            funding_type=int(data[5]) if len(data) > 5 and data[5] is not None else 0,
        )

        # Lägg till ytterligare fält om de finns
        if len(data) > 6 and data[6] is not None:
            position.profit_loss = float(data[6])
        if len(data) > 7 and data[7] is not None:
            position.profit_loss_percentage = float(data[7])
        if len(data) > 8 and data[8] is not None:
            position.liquidation_price = float(data[8])
        if len(data) > 9 and data[9] is not None:
            position.created_at = datetime.fromtimestamp(data[9] / 1000)
        if len(data) > 10 and data[10] is not None:
            position.closed_at = datetime.fromtimestamp(data[10] / 1000)
        if len(data) > 11 and data[11] is not None:
            position.id = int(data[11])

        return position


class ClosePositionResponse(BaseModel):
    """Svar från API:et vid stängning av position."""

    success: bool
    message: str
    data: dict[str, Any] | None = None


# Order-modeller
class OrderRequest(BaseModel):
    """Modell för en orderförfrågan."""

    symbol: str
    amount: float
    price: float | None = None
    side: OrderSide
    type: OrderType = OrderType.LIMIT
    client_order_id: int | None = None
    flags: int | None = None
    price_trailing: float | None = None
    price_aux_limit: float | None = None
    price_oco_stop: float | None = None
    tif: datetime | None = None
    leverage: int | None = None

    @validator("amount")
    def validate_amount(cls, v, values):
        """Validerar att beloppet är positivt och justerar för sidan."""
        if v <= 0:
            raise ValueError("Belopp måste vara positivt")

        # Justera inte beloppet här, det hanteras av API-klienten
        return v


class OrderResponse(BaseModel):
    """Svar från API:et vid orderläggning."""

    id: int
    client_order_id: int | None = None
    symbol: str
    amount: float
    original_amount: float
    type: str
    status: str
    price: float
    average_price: float | None = None
    created_at: datetime
    updated_at: datetime
    is_live: bool
    is_cancelled: bool

    @classmethod
    def from_bitfinex_data(cls, data: list) -> "OrderResponse":
        """Skapar en OrderResponse från Bitfinex API-data."""
        if len(data) < 12:
            raise ValueError(f"Ogiltig orderdata: {data}")

        return cls(
            id=data[0],
            client_order_id=data[2] if data[2] > 0 else None,
            symbol=data[3],
            amount=float(data[6]),
            original_amount=float(data[7]),
            type=data[8],
            status=data[13],
            price=float(data[16]),
            average_price=float(data[17]) if data[17] > 0 else None,
            created_at=datetime.fromtimestamp(data[4] / 1000),
            updated_at=datetime.fromtimestamp(data[5] / 1000),
            is_live=data[13] == "ACTIVE",
            is_cancelled=data[13] == "CANCELED",
        )


class OrderHistoryItem(BaseModel):
    """Modell för ett objekt i orderhistoriken."""

    id: int
    client_order_id: int | None = None
    symbol: str
    created_at: datetime
    updated_at: datetime
    amount: float
    original_amount: float
    order_type: str
    price: float
    average_price: float | None = None
    status: str

    @classmethod
    def from_bitfinex_data(cls, data: list) -> "OrderHistoryItem":
        """Skapar en OrderHistoryItem från Bitfinex API-data."""
        if len(data) < 18:
            raise ValueError(f"Ogiltig orderhistorikdata: {data}")

        return cls(
            id=data[0],
            client_order_id=data[2] if data[2] > 0 else None,
            symbol=data[3],
            created_at=datetime.fromtimestamp(data[4] / 1000),
            updated_at=datetime.fromtimestamp(data[5] / 1000),
            amount=float(data[6]),
            original_amount=float(data[7]),
            order_type=data[8],
            price=float(data[16]),
            average_price=float(data[17]) if data[17] > 0 else None,
            status=data[13],
        )


class TradeItem(BaseModel):
    """Modell för ett handelsobjekt."""

    id: int
    symbol: str
    order_id: int
    executed_amount: float
    executed_price: float
    fee: float | None = None
    fee_currency: str | None = None
    created_at: datetime

    @classmethod
    def from_bitfinex_data(cls, data: list) -> "TradeItem":
        """Skapar en TradeItem från Bitfinex API-data."""
        if len(data) < 11:
            raise ValueError(f"Ogiltig handelsdata: {data}")

        return cls(
            id=data[0],
            symbol=data[1],
            order_id=data[3],
            executed_amount=float(data[4]),
            executed_price=float(data[5]),
            fee=float(data[9]) if len(data) > 9 else None,
            fee_currency=data[10] if len(data) > 10 else None,
            created_at=datetime.fromtimestamp(data[2] / 1000),
        )


class LedgerEntry(BaseModel):
    """Modell för en post i huvudboken."""

    id: int
    currency: str
    amount: float
    balance: float
    description: str
    created_at: datetime
    wallet_type: str | None = None

    @classmethod
    def from_bitfinex_data(cls, data: list) -> "LedgerEntry":
        """Skapar en LedgerEntry från Bitfinex API-data."""
        if len(data) < 6:
            raise ValueError(f"Ogiltig huvudboksdata: {data}")

        # Extrahera wallet_type från beskrivningen om det finns
        wallet_type = None
        description = data[5]
        if "exchange" in description.lower():
            wallet_type = "exchange"
        elif "margin" in description.lower():
            wallet_type = "margin"
        elif "funding" in description.lower():
            wallet_type = "funding"

        return cls(
            id=data[0],
            currency=data[1],
            amount=float(data[2]),
            balance=float(data[3]),
            description=description,
            created_at=datetime.fromtimestamp(data[4] / 1000),
            wallet_type=wallet_type,
        )


# Marknadsdata-modeller
class Ticker(BaseModel):
    """Modell för ticker-data."""

    symbol: str
    bid: float
    bid_size: float
    ask: float
    ask_size: float
    daily_change: float
    daily_change_percentage: float
    last_price: float
    volume: float
    high: float
    low: float

    @classmethod
    def from_bitfinex_data(cls, symbol: str, data: list) -> "Ticker":
        """Skapar en Ticker från Bitfinex API-data."""
        if len(data) < 10:
            raise ValueError(f"Ogiltig ticker-data: {data}")

        return cls(
            symbol=symbol,
            bid=float(data[0]),
            bid_size=float(data[1]),
            ask=float(data[2]),
            ask_size=float(data[3]),
            daily_change=float(data[4]),
            daily_change_percentage=float(data[5]),
            last_price=float(data[6]),
            volume=float(data[7]),
            high=float(data[8]),
            low=float(data[9]),
        )


class Candle(BaseModel):
    """Modell för ljusstake-data."""

    timestamp: datetime
    open: float
    close: float
    high: float
    low: float
    volume: float

    @classmethod
    def from_bitfinex_data(cls, data: list) -> "Candle":
        """Skapar en Candle från Bitfinex API-data."""
        if len(data) < 6:
            raise ValueError(f"Ogiltig ljusstake-data: {data}")

        return cls(
            timestamp=datetime.fromtimestamp(data[0] / 1000),
            open=float(data[1]),
            close=float(data[2]),
            high=float(data[3]),
            low=float(data[4]),
            volume=float(data[5]),
        )


class OrderBookEntry(BaseModel):
    """Modell för en post i orderboken."""

    price: float
    count: int
    amount: float  # Positivt för bud, negativt för utbud

    @property
    def is_bid(self) -> bool:
        """Returnerar True om posten är ett bud."""
        return self.amount > 0

    @property
    def is_ask(self) -> bool:
        """Returnerar True om posten är ett utbud."""
        return self.amount < 0

    @classmethod
    def from_bitfinex_data(cls, data: list) -> "OrderBookEntry":
        """Skapar en OrderBookEntry från Bitfinex API-data."""
        if len(data) < 3:
            raise ValueError(f"Ogiltig orderbok-data: {data}")

        return cls(price=float(data[0]), count=int(data[1]), amount=float(data[2]))


class OrderBook(BaseModel):
    """Modell för en orderbok."""

    symbol: str
    bids: list[OrderBookEntry]
    asks: list[OrderBookEntry]

    @classmethod
    def from_bitfinex_data(cls, symbol: str, data: list[list]) -> "OrderBook":
        """Skapar en OrderBook från Bitfinex API-data."""
        entries = [OrderBookEntry.from_bitfinex_data(entry) for entry in data]
        bids = [entry for entry in entries if entry.is_bid]
        asks = [entry for entry in entries if entry.is_ask]

        return cls(
            symbol=symbol,
            bids=sorted(bids, key=lambda x: x.price, reverse=True),
            asks=sorted(asks, key=lambda x: x.price),
        )


# Websocket-modeller
class WebSocketAuthRequest(BaseModel):
    """Modell för en autentiseringsförfrågan via WebSocket."""

    api_key: str
    auth_sig: str
    auth_payload: str
    auth_nonce: int

    model_config = {
        "json_schema_extra": {
            "example": {
                "api_key": "your-api-key",
                "auth_sig": "generated-signature",
                "auth_payload": "auth-payload",
                "auth_nonce": 1234567890,
            }
        }
    }


class WebSocketSubscriptionRequest(BaseModel):
    """Modell för en prenumerationsförfrågan via WebSocket."""

    channel: str
    symbol: str

    model_config = {
        "json_schema_extra": {"example": {"channel": "ticker", "symbol": "tBTCUSD"}}
    }


# API-svar-modeller
class ApiResponse(BaseModel):
    """Generisk modell för API-svar."""

    success: bool
    message: str
    data: Any | None = None


class PaginatedResponse(BaseModel):
    """Modell för paginerade API-svar."""

    success: bool
    message: str
    data: list[Any]
    page: int
    page_size: int
    total: int
    total_pages: int
