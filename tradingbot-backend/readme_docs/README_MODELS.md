# Pydantic Models - TradingBot Backend

Detta dokument beskriver de centraliserade Pydantic-modellerna som används i tradingboten.

## Innehåll

1. [Översikt](#översikt)
2. [Enums](#enums)
3. [Wallet-modeller](#wallet-modeller)
4. [Margin-modeller](#margin-modeller)
5. [Position-modeller](#position-modeller)
6. [Order-modeller](#order-modeller)
7. [Marknadsdata-modeller](#marknadsdata-modeller)
8. [WebSocket-modeller](#websocket-modeller)
9. [API-svar-modeller](#api-svar-modeller)
10. [Användningsexempel](#användningsexempel)

## Översikt

Tradingboten använder Pydantic-modeller för att strukturera och validera data som hämtas från och skickas till Bitfinex API. Genom att använda Pydantic får vi:

- Automatisk validering av data
- Automatisk konvertering mellan olika datatyper
- Tydlig dokumentation av datastrukturer
- Enkelt att serialisera och deserialisera data till/från JSON

Alla modeller är samlade i modulen `models.api_models` för att göra dem enkla att återanvända och underhålla.

Observera att projektet använder Pydantic v1 (kompatibelt med FastAPI-versionen i detta repo). `BaseSettings` importeras från `pydantic` och `.env` läses via `Settings` i `config/settings.py`.

## Enums

Enums används för att definiera konstanta värden som kan användas i modellerna.

```python
class WalletType(str, Enum):
    """Enum för plånbokstyper."""
    EXCHANGE = "exchange"
    MARGIN = "margin"
    FUNDING = "funding"

class OrderType(str, Enum):
    """Enum för ordertyper."""
    LIMIT = "LIMIT"
    MARKET = "MARKET"
    # ... fler ordertyper ...

class OrderSide(str, Enum):
    """Enum för ordersidor."""
    BUY = "buy"
    SELL = "sell"

class OrderStatus(str, Enum):
    """Enum för orderstatus."""
    ACTIVE = "ACTIVE"
    EXECUTED = "EXECUTED"
    # ... fler statusar ...

class PositionStatus(str, Enum):
    """Enum för positionsstatus."""
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"

class TimeFrame(str, Enum):
    """Enum för tidsramar."""
    ONE_MINUTE = "1m"
    FIVE_MINUTES = "5m"
    # ... fler tidsramar ...
```

## Wallet-modeller

Modeller för att hantera plånboksinformation.

```python
class WalletBalance(BaseModel):
    """Modell för plånbokssaldo."""
    wallet_type: WalletType
    currency: str
    balance: float
    unsettled_interest: float = 0.0
    available_balance: Optional[float] = None

    @classmethod
    def from_bitfinex_data(cls, data: List) -> 'WalletBalance':
        """Skapar en WalletBalance från Bitfinex API-data."""
        # ... implementation ...

class WalletSummary(BaseModel):
    """Sammanfattning av plånböcker."""
    total_balance_usd: float
    exchange_wallets: List[WalletBalance]
    margin_wallets: List[WalletBalance]
    funding_wallets: List[WalletBalance]
```

## Margin-modeller

Modeller för att hantera margin-information.

```python
class MarginLimitInfo(BaseModel):
    """Modell för margin-begränsningar för ett handelssymbol."""
    on_pair: str
    initial_margin: float
    tradable_balance: float
    margin_requirements: float

    @classmethod
    def from_bitfinex_data(cls, data: Dict[str, Any]) -> 'MarginLimitInfo':
        """Skapar ett MarginLimitInfo-objekt från Bitfinex API-data."""
        # ... implementation ...

class MarginInfo(BaseModel):
    """Modell för margin-information."""
    margin_balance: float
    unrealized_pl: float
    unrealized_swap: float
    net_value: float
    required_margin: float
    leverage: Optional[float] = None
    margin_limits: List[Dict[str, Any]] = []

    @classmethod
    def from_bitfinex_data(cls, data: List) -> 'MarginInfo':
        """Skapar ett MarginInfo-objekt från Bitfinex API-data."""
        # ... implementation ...

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
```

## Position-modeller

Modeller för att hantera positionsinformation.

```python
class Position(BaseModel):
    """Modell för en position."""
    symbol: str
    status: PositionStatus
    amount: float
    base_price: float
    funding: float = 0.0
    funding_type: int = Field(0, description="0 för daily, 1 för term")
    profit_loss: Optional[float] = None
    profit_loss_percentage: Optional[float] = None
    liquidation_price: Optional[float] = None

    @property
    def is_long(self) -> bool:
        """Returnerar True om positionen är long."""
        return self.amount > 0

    @property
    def is_short(self) -> bool:
        """Returnerar True om positionen är short."""
        return self.amount < 0

    @classmethod
    def from_bitfinex_data(cls, data: List) -> 'Position':
        """Skapar en Position från Bitfinex API-data."""
        # ... implementation ...

class PositionHistory(BaseModel):
    """Modell för en historisk position."""
    id: Optional[int] = None
    symbol: str
    status: PositionStatus
    amount: float
    base_price: float
    # ... fler fält ...

    @classmethod
    def from_bitfinex_data(cls, data: List) -> 'PositionHistory':
        """Skapar en PositionHistory från Bitfinex API-data."""
        # ... implementation ...

class ClosePositionResponse(BaseModel):
    """Svar från API:et vid stängning av position."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
```

## Order-modeller

Modeller för att hantera orderinformation.

```python
class OrderRequest(BaseModel):
    """Modell för en orderförfrågan."""
    symbol: str
    amount: float
    price: Optional[float] = None
    side: OrderSide
    type: OrderType = OrderType.LIMIT
    # ... fler fält ...

    @validator('amount')
    def validate_amount(cls, v, values):
        """Validerar att beloppet är positivt och justerar för sidan."""
        # ... implementation ...

class OrderResponse(BaseModel):
    """Svar från API:et vid orderläggning."""
    id: int
    client_order_id: Optional[int] = None
    symbol: str
    # ... fler fält ...

    @classmethod
    def from_bitfinex_data(cls, data: List) -> 'OrderResponse':
        """Skapar en OrderResponse från Bitfinex API-data."""
        # ... implementation ...

class OrderHistoryItem(BaseModel):
    """Modell för ett objekt i orderhistoriken."""
    id: int
    client_order_id: Optional[int] = None
    symbol: str
    # ... fler fält ...

    @classmethod
    def from_bitfinex_data(cls, data: List) -> 'OrderHistoryItem':
        """Skapar en OrderHistoryItem från Bitfinex API-data."""
        # ... implementation ...

class TradeItem(BaseModel):
    """Modell för ett handelsobjekt."""
    id: int
    symbol: str
    order_id: int
    # ... fler fält ...

    @classmethod
    def from_bitfinex_data(cls, data: List) -> 'TradeItem':
        """Skapar en TradeItem från Bitfinex API-data."""
        # ... implementation ...

class LedgerEntry(BaseModel):
    """Modell för en post i huvudboken."""
    id: int
    currency: str
    amount: float
    # ... fler fält ...

    @classmethod
    def from_bitfinex_data(cls, data: List) -> 'LedgerEntry':
        """Skapar en LedgerEntry från Bitfinex API-data."""
        # ... implementation ...
```

## Marknadsdata-modeller

Modeller för att hantera marknadsdata.

```python
class Ticker(BaseModel):
    """Modell för ticker-data."""
    symbol: str
    bid: float
    bid_size: float
    ask: float
    ask_size: float
    # ... fler fält ...

    @classmethod
    def from_bitfinex_data(cls, symbol: str, data: List) -> 'Ticker':
        """Skapar en Ticker från Bitfinex API-data."""
        # ... implementation ...

class Candle(BaseModel):
    """Modell för ljusstake-data."""
    timestamp: datetime
    open: float
    close: float
    high: float
    low: float
    volume: float

    @classmethod
    def from_bitfinex_data(cls, data: List) -> 'Candle':
        """Skapar en Candle från Bitfinex API-data."""
        # ... implementation ...

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
    def from_bitfinex_data(cls, data: List) -> 'OrderBookEntry':
        """Skapar en OrderBookEntry från Bitfinex API-data."""
        # ... implementation ...

class OrderBook(BaseModel):
    """Modell för en orderbok."""
    symbol: str
    bids: List[OrderBookEntry]
    asks: List[OrderBookEntry]

    @classmethod
    def from_bitfinex_data(cls, symbol: str, data: List[List]) -> 'OrderBook':
        """Skapar en OrderBook från Bitfinex API-data."""
        # ... implementation ...
```

## WebSocket-modeller

Modeller för att hantera WebSocket-kommunikation.

```python
class WebSocketAuthRequest(BaseModel):
    """Modell för en autentiseringsförfrågan via WebSocket."""
    api_key: str
    auth_sig: str
    auth_payload: str
    auth_nonce: int

class WebSocketSubscriptionRequest(BaseModel):
    """Modell för en prenumerationsförfrågan via WebSocket."""
    channel: str
    symbol: str
```

## API-svar-modeller

Modeller för att hantera API-svar.

```python
class ApiResponse(BaseModel):
    """Generisk modell för API-svar."""
    success: bool
    message: str
    data: Optional[Any] = None

class PaginatedResponse(BaseModel):
    """Modell för paginerade API-svar."""
    success: bool
    message: str
    data: List[Any]
    page: int
    page_size: int
    total: int
    total_pages: int
```

## Användningsexempel

### Skapa en modell från rådata

```python
# Skapa en WalletBalance från rådata
raw_data = ["exchange", "BTC", 0.5, 0.0, 0.5]
wallet = WalletBalance.from_bitfinex_data(raw_data)

print(f"Wallet Type: {wallet.wallet_type}")
print(f"Currency: {wallet.currency}")
print(f"Balance: {wallet.balance}")
```

### Skapa en modell direkt

```python
# Skapa en Position direkt
position = Position(
    symbol="tETHUSD",
    status=PositionStatus.ACTIVE,
    amount=-2.0,  # Short position
    base_price=3000.0,
    profit_loss=-50.0,
    profit_loss_percentage=-0.83,
    liquidation_price=3500.0
)

print(f"Symbol: {position.symbol}")
print(f"Is Short: {position.is_short}")  # True
```

### Konvertera till dict och JSON

```python
# Konvertera till dict
wallet_dict = wallet.model_dump()
print(f"Wallet as Dict: {wallet_dict}")

# Konvertera till JSON
wallet_json = wallet.model_dump_json()
print(f"Wallet as JSON: {wallet_json}")
```

### Validering

```python
# Validering sker automatiskt
try:
    invalid_order = OrderRequest(
        symbol="tBTCUSD",
        amount=-1.0,  # Negativt belopp, kommer att valideras
        price=50000.0,
        side=OrderSide.BUY
    )
except ValueError as e:
    print(f"Validation error: {e}")
```

För fler exempel, se `docs/legacy/examples/models_example.py`.
