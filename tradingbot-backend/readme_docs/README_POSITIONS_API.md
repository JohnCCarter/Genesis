# Positions API - TradingBot Backend

Detta dokument beskriver de olika API-endpoints och funktioner som är tillgängliga för att hantera positioner i tradingboten.

## Innehåll

1. [Aktiva Positioner](#aktiva-positioner)
2. [Positionshistorik](#positionshistorik)
3. [Positionsoperationer](#positionsoperationer)
4. [Exempel](#exempel)

## Autentisering

- När `AUTH_REQUIRED=True` måste alla anrop innehålla HTTP-headern `Authorization: Bearer <access_token>`.
- Hämta token via `POST /api/v2/auth/ws-token` med `{ "user_id": "frontend_user", "scope": "read", "expiry_hours": 1 }`.

## Aktiva Positioner

### Hämta alla aktiva positioner

```python
from rest.positions import get_positions

# Hämta alla aktiva positioner
positions = await get_positions()
```

**Beskrivning:** Hämtar alla aktiva positioner från Bitfinex.

**Endpoint:** `auth/r/positions`

**Returvärde:** En lista med `Position`-objekt som innehåller information om aktiva positioner.

### Hämta en specifik position

```python
from rest.positions import get_position_by_symbol

# Hämta en specifik position baserat på symbol
position = await get_position_by_symbol("tBTCUSD")
```

**Beskrivning:** Hämtar en specifik position baserat på symbol.

**Endpoint:** `auth/r/positions`

**Parametrar:**

- `symbol`: Handelssymbol (t.ex. "tBTCUSD")

**Returvärde:** Ett `Position`-objekt eller `None` om positionen inte hittas.

### Hämta long-positioner

```python
from rest.positions import get_long_positions

# Hämta alla long-positioner
long_positions = await get_long_positions()
```

**Beskrivning:** Hämtar alla long-positioner.

**Endpoint:** `auth/r/positions`

**Returvärde:** En lista med `Position`-objekt för long-positioner.

### Hämta short-positioner

```python
from rest.positions import get_short_positions

# Hämta alla short-positioner
short_positions = await get_short_positions()
```

**Beskrivning:** Hämtar alla short-positioner.

**Endpoint:** `auth/r/positions`

**Returvärde:** En lista med `Position`-objekt för short-positioner.

## Positionshistorik

### Hämta positionshistorik

```python
from rest.positions_history import get_positions_history
from datetime import datetime, timedelta

# Beräkna tidsintervall (senaste 30 dagarna)
end_time = int(datetime.now().timestamp() * 1000)  # Millisekunder
start_time = int((datetime.now() - timedelta(days=30)).timestamp() * 1000)  # Millisekunder

# Hämta positionshistorik
positions = await get_positions_history(start_time, end_time, 50)
```

**Beskrivning:** Hämtar positionshistorik från Bitfinex.

**Endpoint:** `auth/r/positions/hist`

**Parametrar:**

- `start`: Starttid i millisekunder sedan epoch (valfritt)
- `end`: Sluttid i millisekunder sedan epoch (valfritt)
- `limit`: Maximalt antal positioner att hämta (standard: 50)

**Returvärde:** En lista med `PositionHistory`-objekt som innehåller information om historiska positioner.

### Hämta positionsögonblicksbild

```python
from rest.positions_history import get_positions_snapshot

# Hämta positionsögonblicksbild
positions = await get_positions_snapshot()
```

**Beskrivning:** Hämtar en ögonblicksbild av positioner från Bitfinex.

**Endpoint:** `auth/r/positions/snap`

**Returvärde:** En lista med `PositionHistory`-objekt som innehåller information om positioner i ögonblicksbilden.

### Hämta positionsrevision

```python
from rest.positions_history import get_positions_audit
from datetime import datetime, timedelta

# Beräkna tidsintervall (senaste 30 dagarna)
end_time = int(datetime.now().timestamp() * 1000)  # Millisekunder
start_time = int((datetime.now() - timedelta(days=30)).timestamp() * 1000)  # Millisekunder

# Hämta positionsrevision för en specifik symbol
symbol = "tBTCUSD"
positions = await get_positions_audit(symbol, start_time, end_time, 50)
```

**Beskrivning:** Hämtar positionsrevision från Bitfinex.

**Endpoint:** `auth/r/positions/audit`

**Parametrar:**

- `symbol`: Handelssymbol (t.ex. "tBTCUSD")
- `start`: Starttid i millisekunder sedan epoch (valfritt)
- `end`: Sluttid i millisekunder sedan epoch (valfritt)
- `limit`: Maximalt antal positioner att hämta (standard: 50)

**Returvärde:** En lista med `PositionHistory`-objekt som innehåller information om positionsrevisioner.

## Positionsoperationer

### Stäng en position

```python
from rest.positions import close_position

# Stäng en position
result = await close_position("tBTCUSD")
```

**Beskrivning:** Stänger en position genom att skicka en motsatt order via Bitfinex API.

**Endpoint:** `auth/w/position/close`

**Parametrar:**

- `symbol`: Handelssymbol för positionen som ska stängas

**Returvärde:** Ett svar från API:et som innehåller information om den stängda positionen.

### Gör anspråk på en position

```python
from rest.positions_history import claim_position

# Gör anspråk på en position
result = await claim_position("tBTCUSD")
```

**Beskrivning:** Gör anspråk på en position.

**Endpoint:** `auth/w/position/claim`

**Parametrar:**

- `position_id`: ID för positionen som ska göras anspråk på

**Returvärde:** Ett svar från API:et som innehåller information om anspråket.

### Uppdatera finansieringstyp för en position

```python
from rest.positions_history import update_position_funding_type

# Uppdatera finansieringstyp för en position
# 0 för daily, 1 för term
result = await update_position_funding_type("tBTCUSD", 1)
```

**Beskrivning:** Uppdaterar finansieringstypen för en position.

**Endpoint:** `auth/w/position/funding/type`

**Parametrar:**

- `symbol`: Handelssymbol (t.ex. "tBTCUSD")
- `funding_type`: Finansieringstyp (0 för daily, 1 för term)

**Returvärde:** Ett svar från API:et som innehåller information om uppdateringen.

## Exempel

Se `docs/legacy/examples/positions_examples.py` för fullständiga exempel.

### Exempel på hur man hämtar aktiva positioner

```python
async def get_positions_example():
    """Exempel på hur man hämtar aktiva positioner."""
    try:
        # Hämta alla positioner
        positions = await get_positions()

        print("\n=== Aktiva Positioner ===")
        if positions:
            for position in positions:
                direction = "LONG" if position.is_long else "SHORT"
                print(f"{position.symbol} {direction}: {abs(position.amount)} @ {position.base_price} " +
                      f"(PnL: {position.profit_loss})")
        else:
            print("Inga aktiva positioner")

        # Hämta en specifik position
        btc_position = await get_position_by_symbol("tBTCUSD")
        if btc_position:
            print(f"\nBTC Position: {btc_position.amount} @ {btc_position.base_price}")
        else:
            print("\nIngen BTC position hittad")

        # Hämta long-positioner
        long_positions = await get_long_positions()
        print(f"\nAntal long-positioner: {len(long_positions)}")

        # Hämta short-positioner
        short_positions = await get_short_positions()
        print(f"Antal short-positioner: {len(short_positions)}")

    except Exception as e:
        logger.error(f"Fel vid hämtning av positioner: {e}")
        print(f"Fel: {e}")
```

### Exempel på hur man stänger en position

```python
async def close_position_example():
    """Exempel på hur man stänger en position."""
    try:
        # Hämta alla positioner
        positions = await get_positions()

        if positions:
            # Välj den första positionen att stänga
            position_to_close = positions[0]
            symbol = position_to_close.symbol

            print(f"\n=== Stänger Position {symbol} ===")
            result = await close_position(symbol)
            print(f"Resultat: {result}")
        else:
            print("\n=== Stänger Position ===")
            print("Inga positioner att stänga")

    except Exception as e:
        logger.error(f"Fel vid stängning av position: {e}")
        print(f"Fel: {e}")
```

## Datamodeller

### Position

```python
class Position(BaseModel):
    """Modell för en position."""
    symbol: str
    status: str  # "ACTIVE", "CLOSED"
    amount: float
    base_price: float
    funding: float = 0.0
    funding_type: int = 0  # 0 för daily, 1 för term
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
```

### PositionHistory

```python
class PositionHistory(BaseModel):
    """Modell för en historisk position."""
    id: Optional[int] = None
    symbol: str
    status: str  # "ACTIVE", "CLOSED"
    amount: float
    base_price: float
    funding: float = 0.0
    funding_type: int = 0  # 0 för daily, 1 för term
    profit_loss: Optional[float] = None
    profit_loss_percentage: Optional[float] = None
    liquidation_price: Optional[float] = None
    created_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None

    @property
    def is_long(self) -> bool:
        """Returnerar True om positionen är long."""
        return self.amount > 0

    @property
    def is_short(self) -> bool:
        """Returnerar True om positionen är short."""
        return self.amount < 0
```
