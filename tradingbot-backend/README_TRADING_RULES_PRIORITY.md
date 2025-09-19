# Trading Rules Konfigurationsprioritet

## Översikt

Detta dokument beskriver hur trading rules-konfigurationen hanteras och prioriteras i det enhetliga konfigurationssystemet.

## Konflikter som identifierats

### Ursprungliga konflikter:

1. **`.env.example`** (rad 88-90):

   - `MAX_TRADES_PER_DAY=200`
   - `MAX_TRADES_PER_SYMBOL_PER_DAY=0`
   - `TRADE_COOLDOWN_SECONDS=60`

2. **`trading_rules.json`**:

   - `max_trades_per_day: 200`
   - `trade_cooldown_seconds: 5` ❌ **Konflikt**
   - `max_trades_per_symbol_per_day: 0`

3. **`settings.py`** (rad 93-96):
   - `MAX_TRADES_PER_DAY: int = 15` ❌ **Konflikt**
   - `MAX_TRADES_PER_SYMBOL_PER_DAY: int = 0`
   - `TRADE_COOLDOWN_SECONDS: int = 60`

## Lösning: Tydlig Prioritetsordning

### Ny Prioritetsordning för Trading Rules:

1. **`.env` variabler** (HÖGSTA PRIORITET) - Skrivskyddad

   - `MAX_TRADES_PER_DAY`
   - `MAX_TRADES_PER_SYMBOL_PER_DAY`
   - `TRADE_COOLDOWN_SECONDS`

2. **`trading_rules.json`** (Fallback)

   - `max_trades_per_day`
   - `max_trades_per_symbol_per_day`
   - `trade_cooldown_seconds`

3. **`settings.py` defaults** (Sist)
   - Används endast om inget annat är definierat

### Implementering

#### UnifiedConfigManager Ändringar:

```python
def _get_file_setting(self, key: str) -> Any:
    """Hämta från JSON-filer."""
    if key.startswith("trading_rules."):
        # För trading rules, kontrollera först .env (högsta prioritet)
        env_value = self._get_env_trading_rules_setting(key)
        if env_value is not None:
            return env_value

        # Om inte i .env, hämta från trading_rules.json
        return self._get_trading_rules_setting(key)
    return None
```

#### Ny Mappning:

- `trading_rules.MAX_TRADES_PER_DAY` → `.env: MAX_TRADES_PER_DAY` → `trading_rules.json: max_trades_per_day`
- `trading_rules.MAX_TRADES_PER_SYMBOL_PER_DAY` → `.env: MAX_TRADES_PER_SYMBOL_PER_DAY` → `trading_rules.json: max_trades_per_symbol_per_day`
- `trading_rules.TRADE_COOLDOWN_SECONDS` → `.env: TRADE_COOLDOWN_SECONDS` → `trading_rules.json: trade_cooldown_seconds`

## Synkroniserade Värden

### Efter Fix:

1. **`.env.example`**:

   - `MAX_TRADES_PER_DAY=200`
   - `MAX_TRADES_PER_SYMBOL_PER_DAY=0`
   - `TRADE_COOLDOWN_SECONDS=60`

2. **`trading_rules.json`**:

   - `max_trades_per_day: 200`
   - `trade_cooldown_seconds: 60` ✅ **Synkroniserat**
   - `max_trades_per_symbol_per_day: 0`

3. **`settings.py`**:
   - `MAX_TRADES_PER_DAY: int = 200` ✅ **Synkroniserat**
   - `MAX_TRADES_PER_SYMBOL_PER_DAY: int = 0`
   - `TRADE_COOLDOWN_SECONDS: int = 60`

## Viktiga Principer

### 1. .env är Skrivskyddad

- `.env` variabler har högsta prioritet
- Ingen autosync tillbaka till `.env`
- Ändringar görs via UnifiedConfigManager API

### 2. Tydlig Fallback-kedja

- `.env` → `trading_rules.json` → `settings.py` defaults
- Varje nivå fungerar som fallback för nästa

### 3. Konsistent Namngivning

- Namespaced keys i UnifiedConfigManager: `trading_rules.MAX_TRADES_PER_DAY`
- Direkta env variabler: `MAX_TRADES_PER_DAY`
- JSON keys: `max_trades_per_day`

## Användning

### Via UnifiedConfigManager:

```python
from services.unified_config_manager import get_unified_config_manager
from services.unified_config_manager import ConfigContext

manager = get_unified_config_manager()
context = ConfigContext(priority_profile=PriorityProfile.DOMAIN_POLICY)

# Hämta värde med korrekt prioritet
max_trades = manager.get("trading_rules.MAX_TRADES_PER_DAY", context)
cooldown = manager.get("trading_rules.TRADE_COOLDOWN_SECONDS", context)
```

### Via API:

```bash
# Hämta trading rules
GET /api/v2/config/get?key=trading_rules.MAX_TRADES_PER_DAY

# Sätt trading rules (sparas i runtime/config store)
POST /api/v2/config/set
{
  "key": "trading_rules.MAX_TRADES_PER_DAY",
  "value": 150,
  "source": "runtime"
}
```

## Förmåner

1. **Tydlig Prioritet**: Inga förvirrande konflikter
2. **Skrivskydd**: `.env` kan inte ändras av programmet
3. **Flexibilitet**: Runtime-ändringar via API
4. **Konsistens**: Synkroniserade värden över alla källor
5. **Fallback**: Robust hantering av saknade värden

## Framtida Förbättringar

1. **Validation**: Automatisk validering av konflikter vid startup
2. **Documentation**: Auto-genererad dokumentation av prioritetsordning
3. **Monitoring**: Alerts vid konfigurationskonflikter
4. **Migration**: Automatisk migrering av gamla konfigurationer
