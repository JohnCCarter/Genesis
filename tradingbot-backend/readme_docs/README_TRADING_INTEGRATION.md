# Trading Integration - TradingBot Backend

Detta dokument beskriver hur trading-integrationen fungerar i tradingboten. Trading-integrationen kopplar samman olika delar av systemet för att skapa en komplett tradingfunktionalitet.

## Innehåll

1. [Översikt](#översikt)
2. [Huvudfunktioner](#huvudfunktioner)
3. [Riskhantering](#riskhantering)
4. [Automatiserad Trading](#automatiserad-trading)
5. [API-referens](#api-referens)
6. [Exempel](#exempel)

## Översikt

Trading-integrationen är en central komponent i tradingboten som kopplar samman:

- **Marknadsdata** (priser, candles, ticker)
- **Strategiutvärdering** (signaler baserade på tekniska indikatorer)
- **Orderhantering** (lägga, uppdatera, avbryta ordrar)
- **Positionshantering** (hantera aktiva positioner)
- **Plånboksinformation** (tillgängliga medel)
- **Margin-information** (hävstång, margin-status)
- **Riskhantering** (positionsstorlek, max hävstång, etc.)

Genom att integrera dessa delar skapas ett komplett system för att utvärdera tradingmöjligheter, utföra trades och övervaka positioner.

## Autentisering och realtid

- REST- och Socket.IO-åtkomst kan skyddas av `AUTH_REQUIRED`. Sätt `AUTH_REQUIRED=False` för enkel utveckling.
- Hämta JWT via `POST /api/v2/auth/ws-token` och använd `Authorization: Bearer <token>` i REST samt Socket.IO-anslutning.
- Interna Bitfinex privata WS-events (`os`, `on`, `ou`, `oc`, `te`, `tu`) vidarebefordras som Socket.IO-events till klienter för enklare konsumtion.

## Huvudfunktioner

### Initialisering

```python
from services.trading_integration import trading_integration

# Initialisera trading-integrationen
await trading_integration.initialize()
```

Initialiserar trading-integrationen genom att hämta initial data om plånböcker, positioner och margin-status.

### Utvärdera Tradingmöjligheter

```python
# Utvärdera en tradingmöjlighet för en symbol
result = await trading_integration.evaluate_trading_opportunity("tBTCUSD")
```

Utvärderar en tradingmöjlighet för en symbol genom att:

1. Hämta aktuell marknadsdata
2. Utvärdera strategin baserat på tekniska indikatorer
3. Utföra en riskbedömning
4. Returnera ett resultat med signal och riskbedömning

### Utföra Tradingsignaler

```python
# Utför en tradingsignal baserat på utvärderingsresultat
trade_result = await trading_integration.execute_trading_signal("tBTCUSD", result)
```

Utför en tradingsignal genom att:

1. Kontrollera om signalen är giltig (BUY/SELL)
2. Kontrollera riskhantering
3. Beräkna lämplig positionsstorlek
4. Lägga en order
5. Uppdatera position- och plånboksinformation

### Kontosammanfattning

```python
# Hämta en sammanfattning av kontostatus
summary = await trading_integration.get_account_summary()
```

Skapar en sammanfattning av kontostatus med information om:

- Totalt saldo
- Margin-saldo
- Orealiserad vinst/förlust
- Hävstång
- Margin-nivå
- Antal öppna positioner
- Totalt positionsvärde

## Riskhantering

Trading-integrationen inkluderar omfattande riskhantering för att skydda mot förluster:

### Risklimiter

```python
self.risk_limits = {
    "max_position_size": 0.01,  # BTC
    "max_leverage": 3.0,
    "max_open_positions": 3,
    "max_drawdown_percent": 5.0,
    "stop_loss_percent": 2.0,
    "take_profit_percent": 5.0
}
```

Dessa limiter används för att:

- Begränsa positionsstorlek
- Begränsa hävstång
- Begränsa antal öppna positioner
- Sätta stop loss och take profit

### Riskbedömning

Vid utvärdering av tradingmöjligheter görs en riskbedömning som kontrollerar:

- Om det finns för många öppna positioner
- Om hävstången är för hög
- Om margin-nivån är för låg
- Om det redan finns en position i samma riktning

Baserat på dessa faktorer sätts en risknivå (LOW, MEDIUM, HIGH) och en flagga som indikerar om trading är tillåten.

### Positionsstorlek

Positionsstorleken beräknas automatiskt baserat på:

- Risklimiter
- Tillgängligt saldo
- Aktuellt pris

Systemet använder max 20% av tillgängligt saldo för en position, begränsat av max_position_size.

## Automatiserad Trading

Trading-integrationen stödjer automatiserad trading baserat på realtidssignaler:

```python
# Starta automatiserad trading för en symbol
await trading_integration.start_automated_trading("tBTCUSD", signal_callback)

# Stoppa automatiserad trading för en symbol
await trading_integration.stop_automated_trading("tBTCUSD")

# Stoppa all automatiserad trading
await trading_integration.stop_all_trading()
```

Vid automatiserad trading:

1. Realtidsövervakning startas för symbolen
2. Strategin utvärderas kontinuerligt baserat på nya marknadsdata
3. Riskbedömning görs för varje signal
4. Ordrar läggs automatiskt om signalen är giltig och riskbedömningen tillåter det
5. Callback-funktionen anropas med resultatet

### Callback-funktion

```python
async def signal_callback(result: Dict[str, Any]):
    symbol = result.get("symbol", "unknown")
    signal = result.get("signal", "UNKNOWN")
    price = result.get("current_price", 0)

    print(f"Ny signal för {symbol}: {signal} @ ${price:,.2f}")

    if "trade_result" in result:
        trade_result = result["trade_result"]
        if trade_result["success"]:
            print(f"Order lagd: {trade_result['message']}")
```

Callback-funktionen anropas vid nya signaler och kan användas för att:

- Visa signaler i användargränssnittet
- Logga signaler
- Utföra ytterligare åtgärder baserat på signaler

## API-referens

### TradingIntegrationService

#### Metoder

| Metod                                         | Beskrivning                                  |
| --------------------------------------------- | -------------------------------------------- |
| `initialize()`                                | Initialiserar trading-integrationen          |
| `update_wallet_info()`                        | Uppdaterar plånboksinformation               |
| `update_position_info()`                      | Uppdaterar positionsinformation              |
| `update_margin_info()`                        | Uppdaterar margin-information                |
| `update_market_data(symbol)`                  | Uppdaterar marknadsdata för en symbol        |
| `evaluate_trading_opportunity(symbol)`        | Utvärderar en tradingmöjlighet för en symbol |
| `execute_trading_signal(symbol, signal_data)` | Utför en tradingsignal för en symbol         |
| `start_automated_trading(symbol, callback)`   | Startar automatiserad trading för en symbol  |
| `stop_automated_trading(symbol)`              | Stoppar automatiserad trading för en symbol  |
| `stop_all_trading()`                          | Stoppar all automatiserad trading            |
| `get_account_summary()`                       | Skapar en sammanfattning av kontostatus      |

#### Privata Metoder

| Metod                                           | Beskrivning                                        |
| ----------------------------------------------- | -------------------------------------------------- |
| `_assess_risk(symbol, strategy_result)`         | Utvärderar risk för en tradingmöjlighet            |
| `_calculate_position_size(symbol, signal_data)` | Beräknar lämplig positionsstorlek                  |
| `_handle_realtime_signal(result)`               | Hanterar realtidssignaler från strategiutvärdering |

## Exempel

Se `docs/legacy/examples/trading_integration_example.py` för fullständiga exempel.

### Exempel på hur man initialiserar trading-integrationen

```python
async def initialize_trading_example():
    """Exempel på hur man initialiserar trading-integrationen."""
    try:
        print("\n=== Initialiserar Trading Integration ===")
        await trading_integration.initialize()

        # Hämta kontosammanfattning
        summary = await trading_integration.get_account_summary()

        print("\n=== Kontosammanfattning ===")
        print(f"Totalt saldo (USD): ${summary['total_balance_usd']:,.2f}")
        print(f"Margin-saldo: {summary['margin_balance']:,.2f}")
        print(f"Orealiserad vinst/förlust: {summary['unrealized_pl']:,.2f}")
        print(f"Hävstång: {summary['leverage']}x")
        print(f"Margin-nivå: {summary['margin_level']}")
        print(f"Margin-status: {summary['margin_status']}")
        print(f"Öppna positioner: {summary['open_positions']}")
        print(f"Totalt positionsvärde: ${summary['total_position_value']:,.2f}")

    except Exception as e:
        logger.error(f"Fel vid initialisering av trading-integration: {e}")
        print(f"Fel: {e}")
```

### Exempel på hur man utvärderar en tradingmöjlighet

```python
async def evaluate_trading_opportunity_example():
    """Exempel på hur man utvärderar en tradingmöjlighet."""
    try:
        symbol = "tBTCUSD"

        print(f"\n=== Utvärderar Trading-möjlighet för {symbol} ===")
        result = await trading_integration.evaluate_trading_opportunity(symbol)

        print(f"Symbol: {result['symbol']}")
        print(f"Signal: {result['signal']}")
        print(f"Pris: ${result.get('current_price', 0):,.2f}")
        print(f"Anledning: {result['reason']}")
        print(f"RSI: {result.get('rsi', 'N/A')}")
        print(f"EMA: {result.get('ema', 'N/A')}")
        print(f"Risk-nivå: {result.get('risk_level', 'UNKNOWN')}")
        print(f"Kan handla: {result.get('can_trade', False)}")

        # Om vi kan handla, fråga användaren om vi ska utföra signalen
        if result.get("can_trade", False) and result["signal"] in ["BUY", "SELL"]:
            response = input(f"\nVill du utföra {result['signal']} för {symbol}? (y/n): ")

            if response.lower() == "y":
                trade_result = await trading_integration.execute_trading_signal(symbol, result)

                print("\n=== Trading Resultat ===")
                if trade_result["success"]:
                    print(f"Order lagd: {trade_result['message']}")
                else:
                    print(f"Order misslyckades: {trade_result['message']}")

    except Exception as e:
        logger.error(f"Fel vid utvärdering av trading-möjlighet: {e}")
        print(f"Fel: {e}")
```

### Exempel på hur man använder automatiserad trading

```python
async def automated_trading_example():
    """Exempel på hur man använder automatiserad trading."""
    try:
        symbol = "tBTCUSD"

        print(f"\n=== Startar Automatiserad Trading för {symbol} ===")
        await trading_integration.start_automated_trading(symbol, signal_callback)

        print(f"Automatiserad trading startad för {symbol}")
        print("Väntar på signaler... (tryck Ctrl+C för att avbryta)")

        # Vänta på signaler (i ett riktigt scenario skulle detta köras kontinuerligt)
        try:
            await asyncio.sleep(60)  # Vänta 60 sekunder
        except asyncio.CancelledError:
            pass

        # Stoppa automatiserad trading
        print(f"\n=== Stoppar Automatiserad Trading för {symbol} ===")
        await trading_integration.stop_automated_trading(symbol)

        print(f"Automatiserad trading stoppad för {symbol}")

    except Exception as e:
        logger.error(f"Fel vid automatiserad trading: {e}")
        print(f"Fel: {e}")
```
