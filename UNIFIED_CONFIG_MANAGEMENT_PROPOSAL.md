# 🔧 FÖRESLAGEN ENHETLIG KONFIGURATIONSHANTERING

## 📋 **ÖVERSIKT**

Detta dokument beskriver en enhetlig konfigurationshantering för Genesis Trading Bot med tydlig prioritetsordning och automatisk synkronisering för att lösa de nuvarande problemen med konfigurationskonflikter.

## 🚨 **AKTUELLA PROBLEM**

### **Konfigurationskonflikter:**

```bash
# .env fil
MAX_TRADES_PER_SYMBOL_PER_DAY=0    # Inga gränser

# trading_rules.json
"max_trades_per_symbol_per_day": 1  # Max 1 per symbol

# Resultat: Systemet använder 1 (från JSON) - INTE 0 från .env!
```

### **Runtime Override Chaos:**

```python
# Dashboard ändrar:
POST /api/v2/runtime-config
{
  "key": "DRY_RUN_ENABLED",
  "value": true
}

# Men .env säger:
DRY_RUN_ENABLED=false

# Resultat: Dashboard vinner, men vid omstart → .env vinner igen!
```

### **Inconsistent State:**

```python
# Samma inställning kan ha olika värden:
settings.DRY_RUN_ENABLED          # Från .env
runtime_config.get_bool("DRY_RUN_ENABLED")  # Från runtime override
feature_flags.get_flag("dry_run_enabled")   # Från feature flags
```

## 🎯 **DESIGN PRINCIPER**

### **1. Enhetlig Prioritetsordning:**

```python
# Prioritet 1: Runtime Config (högsta - dashboard-ändringar)
# Prioritet 2: .env fil (startup-värden)
# Prioritet 3: Settings defaults (fallback)
# Prioritet 4: Config files (komponent-specifika)
```

### **2. Automatisk Synkronisering:**

- Alla källor synkroniseras automatiskt
- Konflikter detekteras och rapporteras
- Validering vid startup och runtime

### **3. Centraliserad Hantering:**

- En ConfigManager klass hanterar allt
- Enhetlig API för alla konfigurationskällor
- Tydlig dokumentation av prioritetsordning

## 🏗️ **IMPLEMENTATION PLAN**

### **Steg 1: Skapa ConfigManager**

```python
# services/unified_config_manager.py
class UnifiedConfigManager:
    """Enhetlig konfigurationshantering med tydlig prioritetsordning."""

    def __init__(self):
        self.priority_order = [
            "runtime_config",    # Högsta prioritet
            "env_file",          # Startup-värden
            "settings_defaults", # Fallback
            "config_files"       # Komponent-specifika
        ]

    def get_config(self, key: str) -> Any:
        """Hämta konfiguration med korrekt prioritetsordning."""
        # 1. Kolla runtime config först
        # 2. Fallback till .env
        # 3. Fallback till settings defaults
        # 4. Fallback till config files

    def set_config(self, key: str, value: Any, source: str = "runtime"):
        """Sätt konfiguration och synkronisera alla källor."""
        # Sätt i runtime config
        # Synkronisera med .env
        # Synkronisera med config files
        # Validera konsistens

    def sync_all_sources(self):
        """Synkronisera alla konfigurationskällor."""
        # Uppdatera .env baserat på runtime config
        # Uppdatera config files baserat på .env
        # Validera konsistens

    def validate_consistency(self) -> List[str]:
        """Validera att alla källor är konsistenta."""
        # Kontrollera konflikter
        # Rapportera inkonsistenser
        # Föreslå lösningar
```

### **Steg 2: Uppdatera Befintlig Kod**

```python
# Ersätt alla direkta anrop till:
# - Settings()
# - runtime_config.get_bool()
# - feature_flags.get_flag()
# - os.environ.get()

# Med:
# - config_manager.get_config(key)
# - config_manager.set_config(key, value)
```

### **Steg 3: Lägg till Validering**

```python
# config/validation.py
class ConfigValidator:
    """Validerar konfigurationskonsistens."""

    def validate_trading_rules(self) -> List[str]:
        """Validera trading rules mot .env."""
        # Kontrollera MAX_TRADES_PER_DAY
        # Kontrollera TRADE_COOLDOWN_SECONDS
        # Kontrollera MAX_TRADES_PER_SYMBOL_PER_DAY

    def validate_risk_settings(self) -> List[str]:
        """Validera risk-inställningar."""
        # Kontrollera RISK_PERCENTAGE
        # Kontrollera POSITION_SIZE
        # Kontrollera risk guards

    def validate_websocket_settings(self) -> List[str]:
        """Validera WebSocket-inställningar."""
        # Kontrollera WS_CONNECT_ON_START
        # Kontrollera WS_SUBSCRIBE_SYMBOLS
        # Kontrollera WS_CANDLE_TIMEFRAMES
```

### **Steg 4: Lägg till Synkronisering**

```python
# services/config_synchronizer.py
class ConfigSynchronizer:
    """Synkroniserar konfigurationskällor."""

    def sync_env_to_runtime(self):
        """Synkronisera .env till runtime config."""
        # Läs .env fil
        # Uppdatera runtime config
        # Validera ändringar

    def sync_runtime_to_env(self):
        """Synkronisera runtime config till .env."""
        # Läs runtime config
        # Uppdatera .env fil
        # Validera ändringar

    def sync_config_files(self):
        """Synkronisera config files med .env."""
        # Uppdatera trading_rules.json
        # Uppdatera risk_guards.json
        # Uppdatera andra config files

    def auto_sync_on_change(self, key: str, value: Any):
        """Automatisk synkronisering vid ändringar."""
        # Uppdatera alla relevanta källor
        # Validera konsistens
        # Rapportera ändringar
```

## 📁 **FILSTRUKTUR**

```
tradingbot-backend/
├── services/
│   ├── unified_config_manager.py      # Huvudklass
│   ├── config_synchronizer.py         # Synkronisering
│   └── config_validator.py            # Validering
├── config/
│   ├── settings.py                    # Uppdaterad
│   ├── validation.py                  # Valideringsregler
│   └── sync_rules.py                  # Synkroniseringsregler
└── tests/
    ├── test_unified_config.py         # Tester
    └── test_config_sync.py            # Synkroniseringstester
```

## 💻 **EXEMPEL PÅ ANVÄNDNING**

### **Före (nuvarande):**

```python
# Flera olika sätt att hämta samma inställning:
from config.settings import Settings
import services.runtime_config as rc
from services.feature_flags_service import feature_flags_service

settings = Settings()
dry_run_1 = settings.DRY_RUN_ENABLED
dry_run_2 = rc.get_bool("DRY_RUN_ENABLED")
dry_run_3 = feature_flags_service.get_flag("dry_run_enabled")
# Kan ha olika värden!
```

### **Efter (enhetlig):**

```python
# Ett enhetligt sätt:
from services.unified_config_manager import config_manager

dry_run = config_manager.get_config("DRY_RUN_ENABLED")
# Alltid samma värde oavsett källa!

# Sätt konfiguration:
config_manager.set_config("DRY_RUN_ENABLED", True, source="dashboard")
# Automatisk synkronisering med alla källor
```

## 🔍 **VALIDERING OCH RAPPORTERING**

### **Startup Validering:**

```python
# main.py
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 TradingBot Backend startar...")

    # Validera konfiguration
    from services.config_validator import ConfigValidator
    validator = ConfigValidator()
    issues = validator.validate_all()

    if issues:
        logger.warning("⚠️ Konfigurationskonflikter upptäckta:")
        for issue in issues:
            logger.warning(f"  - {issue}")

    # Synkronisera konfiguration
    from services.unified_config_manager import config_manager
    config_manager.sync_all_sources()

    # ... resten av startup
```

### **Runtime Validering:**

```python
# API endpoint för konfigurationsvalidering
@app.get("/api/v2/config/validate")
async def validate_config():
    """Validera konfigurationskonsistens."""
    validator = ConfigValidator()
    issues = validator.validate_all()

    return {
        "status": "ok" if not issues else "warning",
        "issues": issues,
        "recommendations": validator.get_recommendations()
    }
```

## 🔄 **AUTOMATISK SYNKRONISERING**

### **Dashboard Ändringar:**

```python
# När dashboard ändrar en inställning:
@app.post("/api/v2/config/set")
async def set_config(key: str, value: Any):
    """Sätt konfiguration och synkronisera."""
    config_manager.set_config(key, value, source="dashboard")

    # Automatisk synkronisering:
    config_manager.sync_all_sources()

    # Validering:
    issues = config_manager.validate_consistency()

    return {
        "status": "success",
        "key": key,
        "value": value,
        "synced_sources": config_manager.get_synced_sources(key),
        "warnings": issues
    }
```

## 🎯 **PRIORITETSORDNING**

### **1. Runtime Config (Högsta Priorit event)**

- Dashboard-ändringar
- Hot-reload utan omstart
- Överskriver alla andra källor

### **2. .env Fil (Startup-värden)**

- Miljövariabler vid startup
- Persistent konfiguration
- Fallback för runtime config

### **3. Settings Defaults (Fallback)**

- Standardvärden i koden
- Används om .env saknas
- Säkerställer att systemet fungerar

### **4. Config Files (Komponent-specifika)**

- trading_rules.json
- risk_guards.json
- Andra komponent-specifika filer

## ✅ **FÖRDELAR**

### **Enhetlighet:**

- ✅ En enhetlig API för alla konfigurationskällor
- ✅ Tydlig prioritetsordning
- ✅ Konsekvent beteende

### **Synkronisering:**

- ✅ Automatisk synkronisering mellan källor
- ✅ Konflikter detekteras och rapporteras
- ✅ Validering vid startup och runtime

### **Underhållbarhet:**

- ✅ Centraliserad konfigurationshantering
- ✅ Tydlig dokumentation
- ✅ Enkelt att lägga till nya källor

### **Säkerhet:**

- ✅ Validering av konfigurationsvärden
- ✅ Säkerhetskontroller
- ✅ Backup och återställning

## 🚀 **IMPLEMENTERINGSORDNING**

### **Fas 1: Grundläggande System**

1. **Skapa UnifiedConfigManager** (kärnfunktionalitet)
2. **Lägg till validering** (detektera konflikter)
3. **Implementera synkronisering** (automatisk sync)

### **Fas 2: Migration**

4. **Uppdatera befintlig kod** (migrera till ny system)
5. **Lägg till tester** (säkerställ kvalitet)
6. **Dokumentera** (användarhandledning)

### **Fas 3: Förbättringar**

7. **Optimera prestanda** (caching, lazy loading)
8. **Lägg till fler valideringar** (avancerade regler)
9. **UI för konfigurationshantering** (dashboard-integration)

## 📊 **EXEMPEL PÅ KONFIGURATIONSKONFLIKTER**

### **Trading Rules:**

```bash
# .env
MAX_TRADES_PER_DAY=200
TRADE_COOLDOWN_SECONDS=60

# trading_rules.json
{
  "max_trades_per_day": 200,        # ✅ Matchar
  "trade_cooldown_seconds": 5       # ❌ Konflikt! (5 vs 60)
}
```

**Lösning:** UnifiedConfigManager prioriterar runtime config, sedan .env, sedan config files.

### **Risk Management:**

```bash
# .env
RISK_PERCENTAGE=2.0

# Runtime config (dashboard ändring)
RISK_PERCENTAGE=5.0

# Feature flags
RISK_PERCENTAGE=10.0
```

**Lösning:** UnifiedConfigManager använder runtime config (5.0) som högsta prioritet.

## 🔧 **TEKNISKA DETALJER**

### **API Design:**

```python
class UnifiedConfigManager:
    # Hämta konfiguration
    def get_config(self, key: str, default: Any = None) -> Any

    # Sätt konfiguration
    def set_config(self, key: str, value: Any, source: str = "runtime") -> None

    # Synkronisera källor
    def sync_all_sources(self) -> None

    # Validera konsistens
    def validate_consistency(self) -> List[str]

    # Hämta alla källor för en nyckel
    def get_all_sources(self, key: str) -> Dict[str, Any]

    # Hämta prioritetsordning
    def get_priority_order(self) -> List[str]
```

### **Valideringsregler:**

```python
class ConfigValidator:
    # Validera trading rules
    def validate_trading_rules(self) -> List[str]

    # Validera risk-inställningar
    def validate_risk_settings(self) -> List[str]

    # Validera WebSocket-inställningar
    def validate_websocket_settings(self) -> List[str]

    # Validera alla konfigurationer
    def validate_all(self) -> List[str]

    # Hämta rekommendationer
    def get_recommendations(self) -> List[str]
```

## 📈 **FÖRVÄNTADE RESULTAT**

### **Före Implementation:**

- ❌ Konfigurationskonflikter mellan källor
- ❌ Inconsistent state under körning
- ❌ Runtime overrides som försvinner vid omstart
- ❌ Trading rules som överskriver .env-inställningar
- ❌ Feature flags som inte synkroniseras

### **Efter Implementation:**

- ✅ Enhetlig konfigurationshantering
- ✅ Tydlig prioritetsordning
- ✅ Automatisk synkronisering
- ✅ Validering och konflikthantering
- ✅ Konsekvent beteende

## 🎯 **SLUTSATS**

Denna enhetliga konfigurationshantering löser de nuvarande problemen med konfigurationskonflikter genom:

1. **Tydlig prioritetsordning** (runtime > .env > defaults > files)
2. **Automatisk synkronisering** (alla källor hålls synkroniserade)
3. **Validering** (konflikter detekteras och rapporteras)
4. **Enhetlig API** (enkelt att använda och underhålla)

**Rekommendation:** Implementera detta system för att säkerställa en robust och konsekvent konfigurationshantering i Genesis Trading Bot.

---

**Dokument version:** 1.0  
**Datum:** 2025-09-19
**Författare:** Cursor AI Assistant  
**Status:** Föreslaget för implementation
