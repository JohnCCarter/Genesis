# Account API - TradingBot Backend

Detta dokument beskriver de olika account-relaterade API-endpoints som finns tillgängliga i tradingboten.

## Innehåll

1. [Wallet API](#wallet-api)
2. [Positions API](#positions-api)
3. [Margin API](#margin-api)
4. [Order History API](#order-history-api)
5. [Trades History API](#trades-history-api)
6. [Ledgers API](#ledgers-api)

## Autentisering

- När `AUTH_REQUIRED=True` måste alla anrop innehålla HTTP-headern `Authorization: Bearer <access_token>`.
- Hämta token via `POST /api/v2/auth/ws-token` med `{ "user_id": "frontend_user", "scope": "read", "expiry_hours": 1 }`.

## Wallet API

Wallet API:et används för att hämta plånboksinformation från Bitfinex.

### Endpoints

- `GET /api/v2/wallets` - Hämtar alla plånböcker
- `GET /api/v2/wallets/exchange` - Hämtar alla exchange-plånböcker
- `GET /api/v2/wallets/margin` - Hämtar alla margin-plånböcker
- `GET /api/v2/wallets/funding` - Hämtar alla funding-plånböcker

### Exempel

```python
from rest.wallet import get_wallets, get_wallet_by_type_and_currency

# Hämta alla plånböcker
wallets = await get_wallets()

# Hämta en specifik plånbok
btc_exchange = await get_wallet_by_type_and_currency("exchange", "BTC")
```

## Positions API

Positions API:et används för att hämta positionsinformation från Bitfinex.

### Endpoints

- `GET /api/v2/positions` - Hämtar alla aktiva positioner
- `GET /api/v2/positions/long` - Hämtar alla long-positioner
- `GET /api/v2/positions/short` - Hämtar alla short-positioner
- `POST /api/v2/positions/close/{symbol}` - Stänger en position för en specifik symbol

### Exempel

```python
from rest.positions import get_positions, get_position_by_symbol

# Hämta alla positioner
positions = await get_positions()

# Hämta en specifik position
btc_position = await get_position_by_symbol("tBTCUSD")
```

## Margin API

Margin API:et används för att hämta margin-information från Bitfinex.

### Endpoints

- `GET /api/v2/margin` - Hämtar margin-information
- `GET /api/v2/margin/status` - Hämtar en sammanfattning av margin-status
- `GET /api/v2/margin/leverage` - Hämtar nuvarande hävstång (leverage)

### Exempel

```python
from rest.margin import get_margin_info, get_leverage

# Hämta margin info
margin_info = await get_margin_info()

# Hämta hävstång
leverage = await get_leverage()
```

## Order History API

Order History API:et används för att hämta orderhistorik från Bitfinex.

### Endpoints

- `GET /api/v2/orders/history` - Hämtar orderhistorik
- `GET /api/v2/order/{order_id}/trades` - Hämtar alla trades för en specifik order

### Exempel

```python
from rest.order_history import get_orders_history, get_order_trades

# Hämta de senaste 10 ordrarna
orders = await get_orders_history(10)

# Hämta trades för en specifik order
trades = await get_order_trades(order_id)
```

## Trades History API

Trades History API:et används för att hämta handelshistorik från Bitfinex.

### Endpoints

- `GET /api/v2/trades/history` - Hämtar handelshistorik

### Exempel

```python
from rest.order_history import get_trades_history

# Hämta de senaste 10 trades
trades = await get_trades_history(limit=10)

# Hämta trades för en specifik symbol
btc_trades = await get_trades_history(symbol="tBTCUSD", limit=5)
```

## Ledgers API

Ledgers API:et används för att hämta ledger-poster från Bitfinex.

### Endpoints

- `GET /api/v2/ledgers` - Hämtar ledger-poster

### Exempel

```python
from rest.order_history import get_ledgers

# Hämta de senaste 10 ledger-posterna
ledgers = await get_ledgers(limit=10)

# Hämta ledger-poster för en specifik valuta
usd_ledgers = await get_ledgers(currency="USD", limit=5)
```

## Felhantering

Alla API-anrop kan returnera fel. Dessa fel kan vara:

- `400 Bad Request` - Felaktiga parametrar eller ogiltigt format
- `401 Unauthorized` - Ogiltiga API-nycklar eller signatur
- `404 Not Found` - Resursen hittades inte
- `500 Internal Server Error` - Serverfel

För att hantera fel, använd try/except:

```python
try:
    wallets = await get_wallets()
except Exception as e:
    print(f"Fel vid hämtning av plånböcker: {e}")
```

## Modeller

Alla API-svar returneras som Pydantic-modeller:

- `WalletBalance` - Plånbokssaldo
- `Position` - Position
- `MarginInfo` - Margin-information
- `OrderHistoryItem` - Orderhistorik
- `TradeItem` - Trade
- `LedgerEntry` - Ledger-post

## Testning

Se `docs/legacy/examples/account_examples.py` för exempel på manuella körningar.

## Kända begränsningar

- Margin API:et fungerar endast om ditt konto har margin aktiverat
- Order History API:et kan returnera 500 Internal Server Error om ditt konto inte har några ordrar
- Trades History API:et kan returnera 500 Internal Server Error om ditt konto inte har några trades
- Ledgers API:et kan returnera 500 Internal Server Error om ditt konto inte har några ledger-poster

## Framtida förbättringar

- Implementera bättre felhantering för API-anrop
- Lägga till stöd för fler endpoints
- Förbättra dokumentationen med mer exempel
- Lägga till stöd för paginering
