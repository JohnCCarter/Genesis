# Order API - TradingBot Backend

Detta dokument beskriver de olika API-endpoints och funktioner som är tillgängliga för att hantera ordrar i tradingboten.

## Innehåll

1. [Aktiva Ordrar](#aktiva-ordrar)
2. [Orderhantering](#orderhantering)
3. [Orderhistorik](#orderhistorik)
4. [Trades och Ledgers](#trades-och-ledgers)
5. [Exempel](#exempel)

## Autentisering

- När `AUTH_REQUIRED=True` måste alla anrop innehålla HTTP-headern:
  - `Authorization: Bearer <access_token>`
- Hämta token via `POST /api/v2/auth/ws-token` med body `{ "user_id": "frontend_user", "scope": "read", "expiry_hours": 1 }`.

## Aktiva Ordrar

### Hämta alla aktiva ordrar

```python
from rest.active_orders import get_active_orders

# Hämta alla aktiva ordrar
orders = await get_active_orders()
```

**Beskrivning:** Hämtar alla aktiva ordrar från Bitfinex.

**Endpoint:** `auth/r/orders`

**Returvärde:** En lista med `OrderResponse`-objekt som innehåller information om aktiva ordrar.

### Hämta aktiva ordrar för en specifik symbol

```python
from rest.active_orders import get_active_orders_by_symbol

# Hämta aktiva ordrar för en specifik symbol
orders = await get_active_orders_by_symbol("tBTCUSD")
```

**Beskrivning:** Hämtar aktiva ordrar för en specifik symbol.

**Endpoint:** `auth/r/orders`

**Parametrar:**

- `symbol`: Handelssymbol (t.ex. "tBTCUSD")

**Returvärde:** En lista med `OrderResponse`-objekt för den angivna symbolen.

### Hämta aktiva ordrar av en specifik typ

```python
from rest.active_orders import get_active_orders_by_type
from models.api_models import OrderType

# Hämta aktiva ordrar av en specifik typ
orders = await get_active_orders_by_type(OrderType.LIMIT)
```

**Beskrivning:** Hämtar aktiva ordrar av en specifik typ.

**Endpoint:** `auth/r/orders`

**Parametrar:**

- `order_type`: Ordertyp (t.ex. OrderType.LIMIT, OrderType.MARKET)

**Returvärde:** En lista med `OrderResponse`-objekt för den angivna ordertypen.

### Hämta aktiva ordrar för en specifik sida (köp/sälj)

```python
from rest.active_orders import get_active_orders_by_side
from models.api_models import OrderSide

# Hämta aktiva köpordrar
buy_orders = await get_active_orders_by_side(OrderSide.BUY)

# Hämta aktiva säljordrar
sell_orders = await get_active_orders_by_side(OrderSide.SELL)
```

**Beskrivning:** Hämtar aktiva ordrar för en specifik sida (köp/sälj).

**Endpoint:** `auth/r/orders`

**Parametrar:**

- `side`: Ordersida (OrderSide.BUY eller OrderSide.SELL)

**Returvärde:** En lista med `OrderResponse`-objekt för den angivna sidan.

### Hämta en specifik order baserat på ID

```python
from rest.active_orders import get_order_by_id

# Hämta en specifik order baserat på ID
order = await get_order_by_id(123456)
```

**Beskrivning:** Hämtar en specifik order baserat på ID.

**Endpoint:** `auth/r/orders`

**Parametrar:**

- `order_id`: Order-ID

**Returvärde:** Ett `OrderResponse`-objekt eller `None` om ordern inte hittas.

### Hämta en specifik order baserat på klient-ID

```python
from rest.active_orders import get_order_by_client_id

# Hämta en specifik order baserat på klient-ID
order = await get_order_by_client_id(789)
```

**Beskrivning:** Hämtar en specifik order baserat på klient-ID.

**Endpoint:** `auth/r/orders`

**Parametrar:**

- `client_order_id`: Klient-order-ID

**Returvärde:** Ett `OrderResponse`-objekt eller `None` om ordern inte hittas.

## Orderhantering

### Lägga en order

```python
from rest.auth import place_order

# Lägg en order
order_data = {
    "symbol": "tBTCUSD",
    "amount": "0.001",  # Positivt för köp, negativt för sälj
    "price": "50000",
    "type": "EXCHANGE LIMIT"
}
result = await place_order(order_data)
```

**Beskrivning:** Lägger en order via Bitfinex API.

**Endpoint:** `auth/w/order/submit`

**Parametrar:**

- `order_data`: Ett dictionary med orderdata

**Returvärde:** Ett dictionary med information om den lagda ordern.

### Uppdatera en order

```python
from rest.active_orders import update_order

# Uppdatera en order
result = await update_order(123456, price=51000, amount=0.002)
```

**Beskrivning:** Uppdaterar en aktiv order.

**Endpoint:** `auth/w/order/update`

**Parametrar:**

- `order_id`: Order-ID
- `price`: Nytt pris (valfritt)
- `amount`: Ny mängd (valfritt)

**Returvärde:** Ett dictionary med information om den uppdaterade ordern.

### Avbryta en order

```python
from rest.auth import cancel_order

# Avbryt en order
result = await cancel_order(123456)
```

**Beskrivning:** Avbryter en order via Bitfinex API.

**Endpoint:** `auth/w/order/cancel`

**Parametrar:**

- `order_id`: Order-ID

**Returvärde:** Ett dictionary med information om den avbrutna ordern.

### Avbryta alla ordrar

```python
from rest.active_orders import cancel_all_orders

# Avbryt alla ordrar
result = await cancel_all_orders()
```

**Beskrivning:** Avbryter alla aktiva ordrar.

**Endpoint:** `auth/w/order/cancel/all`

**Returvärde:** Ett dictionary med information om de avbrutna ordrarna.

Notera: I vissa miljöer (t.ex. simulator/sub-account) kan `cancel/all` inte vara tillgänglig och ge 404. Backend har därför fallback som hämtar alla aktiva ordrar och avbryter dem en och en.

### Avbryta ordrar för en specifik symbol

```python
from rest.active_orders import cancel_orders_by_symbol

# Avbryt alla ordrar för en specifik symbol
result = await cancel_orders_by_symbol("tBTCUSD")
```

**Beskrivning:** Avbryter alla aktiva ordrar för en specifik symbol.

**Endpoint:** `auth/w/order/cancel`

**Parametrar:**

- `symbol`: Handelssymbol (t.ex. "tBTCUSD")

**Returvärde:** Ett dictionary med information om de avbrutna ordrarna.

## Orderhistorik

### Hämta orderhistorik

```python
from rest.order_history import get_orders_history

# Hämta de senaste 25 ordrarna
orders = await get_orders_history(25)

# Hämta ordrar inom ett tidsintervall
start_time = int(datetime.now().timestamp() * 1000) - 86400000  # 24 timmar sedan
end_time = int(datetime.now().timestamp() * 1000)
orders = await get_orders_history(25, start_time, end_time)
```

**Beskrivning:** Hämtar orderhistorik från Bitfinex.

**Endpoint:** `auth/r/orders/hist`

**Parametrar:**

- `limit`: Maximalt antal ordrar att hämta
- `start_time`: Starttid i millisekunder sedan epoch (valfritt)
- `end_time`: Sluttid i millisekunder sedan epoch (valfritt)

**Returvärde:** En lista med `OrderHistoryItem`-objekt.

### Hämta trades för en specifik order

```python
from rest.order_history import get_order_trades

# Hämta trades för en specifik order
trades = await get_order_trades(123456)
```

**Beskrivning:** Hämtar alla trades för en specifik order.

**Endpoint:** `auth/r/order/{order_id}/trades`

**Parametrar:**

- `order_id`: Order-ID

**Returvärde:** En lista med `TradeItem`-objekt.

## Trades och Ledgers

### Hämta handelshistorik

```python
from rest.order_history import get_trades_history

# Hämta de senaste 25 trades
trades = await get_trades_history(limit=25)

# Hämta trades för en specifik symbol
trades = await get_trades_history(symbol="tBTCUSD", limit=25)
```

**Beskrivning:** Hämtar handelshistorik från Bitfinex.

**Endpoint:** `auth/r/trades/hist` eller `auth/r/trades/{symbol}/hist`

**Parametrar:**

- `symbol`: Handelssymbol (t.ex. "tBTCUSD") (valfritt)
- `limit`: Maximalt antal trades att hämta

**Returvärde:** En lista med `TradeItem`-objekt.

### Hämta ledger-poster

```python
from rest.order_history import get_ledgers

# Hämta de senaste 25 ledger-posterna
ledgers = await get_ledgers(limit=25)

# Hämta ledger-poster för en specifik valuta
ledgers = await get_ledgers(currency="BTC", limit=25)
```

**Beskrivning:** Hämtar ledger-poster från Bitfinex.

**Endpoint:** `auth/r/ledgers/hist` eller `auth/r/ledgers/{currency}/hist`

**Parametrar:**

- `currency`: Valutakod (t.ex. "BTC", "USD") (valfritt)
- `limit`: Maximalt antal poster att hämta

**Returvärde:** En lista med `LedgerEntry`-objekt.

## Exempel

Se `docs/legacy/examples/active_orders_examples.py` för fullständiga exempel.

### Exempel på hur man hämtar aktiva ordrar

```python
async def get_active_orders_example():
    """Exempel på hur man hämtar aktiva ordrar."""
    try:
        # Hämta alla aktiva ordrar
        orders = await get_active_orders()

        print("\n=== Aktiva Ordrar ===")
        if orders:
            for order in orders:
                print(f"{order.id}: {order.symbol} - {order.amount} @ {order.price} ({order.status})")
        else:
            print("Inga aktiva ordrar")

    except Exception as e:
        logger.error(f"Fel vid hämtning av aktiva ordrar: {e}")
        print(f"Fel: {e}")
```

### Exempel på hur man lägger och uppdaterar en order

```python
async def place_and_update_order_example():
    """Exempel på hur man lägger och uppdaterar en order."""
    try:
        # Lägg en order
        order_data = {
            "symbol": "tBTCUSD",
            "amount": "0.001",  # Positivt för köp, negativt för sälj
            "price": "20000",  # Pris långt från marknadspris för att undvika exekvering
            "type": "EXCHANGE LIMIT"
        }

        print("\n=== Lägger Order ===")
        result = await place_order(order_data)

        if "error" in result:
            print(f"Fel vid orderläggning: {result['error']}")
            return

        print(f"Order lagd: {result}")

        # Hämta order ID från resultatet
        order_id = result["id"]

        # Uppdatera ordern
        new_price = 21000.0
        print(f"\n=== Uppdaterar Order {order_id} ===")
        print(f"Nytt pris: {new_price}")

        update_result = await update_order(order_id, price=new_price)
        print(f"Uppdateringsresultat: {update_result}")

    except Exception as e:
        logger.error(f"Fel vid orderläggning och uppdatering: {e}")
        print(f"Fel: {e}")
```

### Exempel på hur man avbryter ordrar

```python
async def cancel_orders_example():
    """Exempel på hur man avbryter ordrar."""
    try:
        # Hämta aktiva ordrar
        orders = await get_active_orders()

        if not orders:
            print("\n=== Avbryta Ordrar ===")
            print("Inga aktiva ordrar att avbryta")
            return

        # Välj en symbol att avbryta ordrar för
        symbol = orders[0].symbol

        print(f"\n=== Avbryter Ordrar för {symbol} ===")
        result = await cancel_orders_by_symbol(symbol)
        print(f"Avbrytningsresultat: {result}")

    except Exception as e:
        logger.error(f"Fel vid avbrytning av ordrar: {e}")
        print(f"Fel: {e}")
```
