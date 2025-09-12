# Inställningsladdning - Load Order

## 🔄 **Startup-flöde för inställningar:**

### **1. Miljövariabler (.env fil)**
**Plats:** `tradingbot-backend/.env`
**Prioritet:** HÖGST (överrider allt annat)

```bash
# Exempel .env fil
BITFINEX_API_KEY=din_api_key
BITFINEX_API_SECRET=din_api_secret
DRY_RUN_ENABLED=true
PROB_MODEL_ENABLED=true
SCHEDULER_ENABLED=true
DEV_MODE=true
```

### **2. Settings Class (Pydantic BaseSettings)**
**Plats:** `config/settings.py`
**Prioritet:** HÖG (laddar från .env + defaults)

```python
class Settings(_BaseSettings):
    # Default värden
    DRY_RUN_ENABLED: bool = False
    PROB_MODEL_ENABLED: bool = False
    SCHEDULER_ENABLED: bool = True

    class Config:
        env_file = ".env"  # Laddar från .env fil
        case_sensitive = False
        extra = "allow"
```

### **3. Startup Configuration**
**Plats:** `config/startup_config.py`
**Prioritet:** MEDIUM (aktiverar komponenter vid startup)

```python
def enable_components_on_startup():
    # Aktivera baserat på miljövariabler
    if os.environ.get("ENABLE_DRY_RUN", "").lower() in ("true", "1", "yes"):
        rc.set_bool("DRY_RUN_ENABLED", True)
        settings.DRY_RUN_ENABLED = True
```

### **4. Runtime Config Service**
**Plats:** `services/runtime_config.py`
**Prioritet:** MEDIUM (hot-reload utan omstart)

```python
# In-memory overrides
_runtime_overrides: dict[str, Any] = {}

def set_bool(key: str, value: bool) -> None:
    _runtime_overrides[key] = bool(value)
    os.environ[key] = "True" if bool(value) else "False"

def get_bool(key: str, default: bool | None = None) -> bool:
    if key in _runtime_overrides:
        return bool(_runtime_overrides[key])
    val = getattr(Settings(), key, default)
    return bool(val) if val is not None else False
```

### **5. Feature Flags Service**
**Plats:** `services/feature_flags_service.py`
**Prioritet:** LÅG (UI-kontrollerade inställningar)

```python
class FeatureFlagsService:
    def __init__(self):
        self.flags = {
            "dry_run_enabled": FeatureFlag(
                name="dry_run_enabled",
                default_value=False,
                current_value=self._get_dry_run_status(),
                description="Aktivera dry run mode",
                category="trading",
                requires_restart=False
            )
        }
```

## 📋 **Laddningsordning vid startup:**

### **Steg 1: Miljövariabler**
```python
# main.py - Rad 33
from config.settings import Settings
```
- Laddar `.env` fil automatiskt
- Sätter `os.environ` värden

### **Steg 2: Settings Initialization**
```python
# settings.py - Rad 24
class Settings(_BaseSettings):
    DRY_RUN_ENABLED: bool = False  # Default
    # Laddar från .env om finns
```

### **Steg 3: Startup Config**
```python
# main.py - Rad 139
from config.startup_config import enable_components_on_startup
enable_components_on_startup()
```
- Kontrollerar miljövariabler som `ENABLE_DRY_RUN`
- Aktiverar komponenter via runtime_config

### **Steg 4: Runtime Config**
```python
# startup_config.py - Rad 28
import services.runtime_config as rc
rc.set_bool("DRY_RUN_ENABLED", True)
```
- Sätter in-memory overrides
- Uppdaterar `os.environ`

### **Steg 5: Feature Flags**
```python
# services/feature_flags_service.py
# Initialiseras när första API-anrop görs
```

## 🎯 **Prioritetsordning:**

1. **Miljövariabler** (`.env` fil) - HÖGST
2. **Settings defaults** - HÖG
3. **Runtime Config overrides** - MEDIUM
4. **Feature Flags** - LÅG

## 🔧 **Praktiska exempel:**

### **Aktivera Dry Run:**
```bash
# Metod 1: Miljövariabel (rekommenderat)
echo "DRY_RUN_ENABLED=true" >> .env

# Metod 2: Startup flag
echo "ENABLE_DRY_RUN=true" >> .env

# Metod 3: Dev mode (aktiverar allt)
echo "DEV_MODE=true" >> .env
```

### **Aktivera Probability Model:**
```bash
# Metod 1: Miljövariabel
echo "PROB_MODEL_ENABLED=true" >> .env

# Metod 2: Startup flag
echo "ENABLE_PROB_MODEL=true" >> .env
```

### **Aktivera Scheduler:**
```bash
# Metod 1: Miljövariabel
echo "SCHEDULER_ENABLED=true" >> .env

# Metod 2: Startup flag
echo "ENABLE_SCHEDULER=true" >> .env
```

## 📁 **Konfigurationsfiler:**

### **Huvudkonfiguration:**
- `tradingbot-backend/.env` - Miljövariabler
- `tradingbot-backend/config/settings.py` - Settings class
- `tradingbot-backend/env.example` - Exempel på miljövariabler

### **Komponent-specifika:**
- `tradingbot-backend/config/trading_rules.json` - Trading windows
- `tradingbot-backend/config/strategy_settings.json` - Strategi-inställningar
- `tradingbot-backend/config/risk_guards.json` - Risk guards
- `tradingbot-backend/config/performance_history.json` - Performance data

### **Runtime:**
- `services/runtime_config.py` - Hot-reload inställningar
- `services/feature_flags_service.py` - UI-kontrollerade flags

## ⚡ **Snabbstart för komponenter:**

### **Aktivera alla komponenter:**
```bash
# Lägg till i .env
DEV_MODE=true
```

### **Aktivera specifika komponenter:**
```bash
# Lägg till i .env
ENABLE_DRY_RUN=true
ENABLE_PROB_MODEL=true
ENABLE_SCHEDULER=true
```

### **Kontrollera status:**
```bash
# Via API
curl http://localhost:8000/api/component-status \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 🚨 **Viktiga noter:**

1. **Miljövariabler har högsta prioritet** - överskriver allt annat
2. **Settings class laddar automatiskt från .env** vid startup
3. **Runtime Config** tillåter hot-reload utan omstart
4. **Feature Flags** är för UI-kontrollerade inställningar
5. **DEV_MODE=true** aktiverar alla komponenter automatiskt

**Sammanfattning:** Alla inställningar laddas först från `.env` filen via Pydantic Settings, sedan aktiveras komponenter via startup_config baserat på miljövariabler, och slutligen kan inställningar ändras runtime via runtime_config och feature flags.
