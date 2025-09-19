# 🔧 TODO: Enhetlig Konfigurationshantering v2.0

## 📋 **ÖVERSIKT**

Detta dokument innehåller en detaljerad todolista för att implementera **förbättrad enhetlig konfigurationshantering** i Genesis Trading Bot baserat på feedback och säkerhetsförbättringar.

## 🎯 **MÅL**

- Lösa konfigurationskonflikter mellan olika källor
- Implementera **kontextuell prioritetsordning** per nyckel/domän
- **Central store** med pub/sub för kluster-konsistens
- **Säkra API:er** med RBAC, preview/apply-flöde och audit
- **Key Registry** för schema, metadata och validering
- **INGEN autosync** till .env (skrivskyddad startkonfiguration)

## 📝 **TODOLISTA**

### **🏗️ Fas 1: Grundläggande System**

#### **1. Skapa UnifiedConfigManager klass**

- [ ] **Status:** Pending
- [ ] **Beskrivning:** Skapa huvudklass med prioritetsordning och grundläggande API
- [ ] **Filer:** `services/unified_config_manager.py`
- [ ] **Funktioner:**
  - [ ] `get_config(key: str) -> Any`
  - [ ] `set_config(key: str, value: Any, source: str) -> None`
  - [ ] `sync_all_sources() -> None`
  - [ ] `validate_consistency() -> List[str]`
  - [ ] `get_all_sources(key: str) -> Dict[str, Any]`
- [ ] **Prioritet:** Hög
- [ ] **Tidsuppskattning:** 4-6 timmar

#### **2. Implementera ConfigValidator**

- [ ] **Status:** Pending
- [ ] **Beskrivning:** Detektera konflikter mellan olika konfigurationskällor
- [ ] **Filer:** `services/config_validator.py`
- [ ] **Funktioner:**
  - [ ] `validate_trading_rules() -> List[str]`
  - [ ] `validate_risk_settings() -> List[str]`
  - [ ] `validate_websocket_settings() -> List[str]`
  - [ ] `validate_all() -> List[str]`
  - [ ] `get_recommendations() -> List[str]`
- [ ] **Prioritet:** Hög
- [ ] **Tidsuppskattning:** 3-4 timmar

#### **3. Skapa ConfigSynchronizer**

- [ ] **Status:** Pending
- [ ] **Beskrivning:** Automatisk synkronisering mellan konfigurationskällor
- [ ] **Filer:** `services/config_synchronizer.py`
- [ ] **Funktioner:**
  - [ ] `sync_env_to_runtime() -> None`
  - [ ] `sync_runtime_to_env() -> None`
  - [ ] `sync_config_files() -> None`
  - [ ] `auto_sync_on_change(key: str, value: Any) -> None`
- [ ] **Prioritet:** Hög
- [ ] **Tidsuppskattning:** 4-5 timmar

#### **4. Lägg till valideringsregler**

- [ ] **Status:** Pending
- [ ] **Beskrivning:** Specifika valideringsregler för trading rules, risk settings och websocket
- [ ] **Filer:** `config/validation.py`, `config/sync_rules.py`
- [ ] **Regler:**
  - [ ] Trading rules validering (MAX_TRADES_PER_DAY, TRADE_COOLDOWN_SECONDS)
  - [ ] Risk settings validering (RISK_PERCENTAGE, POSITION_SIZE)
  - [ ] WebSocket settings validering (WS_CONNECT_ON_START, WS_SUBSCRIBE_SYMBOLS)
- [ ] **Prioritet:** Medium
- [ ] **Tidsuppskattning:** 2-3 timmar

### **🔧 Fas 2: Integration**

#### **5. Uppdatera startup validering**

- [ ] **Status:** Pending
- [ ] **Beskrivning:** Validera konfiguration vid backend-start i main.py
- [ ] **Filer:** `main.py`, `config/startup_config.py`
- [ ] **Funktioner:**
  - [ ] Lägg till ConfigValidator i lifespan funktion
  - [ ] Rapportera konflikter vid startup
  - [ ] Automatisk synkronisering vid startup
- [ ] **Prioritet:** Medium
- [ ] **Tidsuppskattning:** 2-3 timmar

#### **6. Skapa API endpoints**

- [ ] **Status:** Pending
- [ ] **Beskrivning:** API endpoints för konfigurationshantering från dashboard
- [ ] **Filer:** `rest/routes.py`
- [ ] **Endpoints:**
  - [ ] `GET /api/v2/config/status` - Hämta alla konfigurationer
  - [ ] `POST /api/v2/config/set` - Sätt konfiguration
  - [ ] `GET /api/v2/config/validate` - Validera konfiguration
  - [ ] `GET /api/v2/config/sources/{key}` - Hämta alla källor för en nyckel
- [ ] **Prioritet:** Medium
- [ ] **Tidsuppskattning:** 3-4 timmar

#### **7. Migrera befintlig kod**

- [ ] **Status:** Pending
- [ ] **Beskrivning:** Ersätt Settings() anrop med UnifiedConfigManager
- [ ] **Filer:** Alla filer som använder Settings(), runtime_config, feature_flags
- [ ] **Ändringar:**
  - [ ] Ersätt `Settings()` med `config_manager.get_config()`
  - [ ] Ersätt `runtime_config.get_bool()` med `config_manager.get_config()`
  - [ ] Ersätt `feature_flags.get_flag()` med `config_manager.get_config()`
- [ ] **Prioritet:** Medium
- [ ] **Tidsuppskattning:** 6-8 timmar

#### **8. Synkronisera trading_rules**

- [ ] **Status:** Pending
- [ ] **Beskrivning:** Fixa konflikter mellan trading_rules.json och .env
- [ ] **Filer:** `config/trading_rules.json`, `.env`
- [ ] **Konflikter att lösa:**
  - [ ] `MAX_TRADES_PER_SYMBOL_PER_DAY` (0 i .env vs 1 i JSON)
  - [ ] `TRADE_COOLDOWN_SECONDS` (60 i .env vs 5 i JSON)
  - [ ] Synkronisera alla trading-relaterade inställningar
- [ ] **Prioritet:** Hög
- [ ] **Tidsuppskattning:** 1-2 timmar

### ** Fas 3: Kvalitetssäkring**

#### **9. Skapa tester**

- [ ] **Status:** Pending
- [ ] **Beskrivning:** Tester för alla nya konfigurationskomponenter
- [ ] **Filer:** `tests/test_unified_config.py`, `tests/test_config_sync.py`
- [ ] **Tester:**
  - [ ] UnifiedConfigManager funktionalitet
  - [ ] ConfigValidator validering
  - [ ] ConfigSynchronizer synkronisering
  - [ ] API endpoints
  - [ ] Edge cases och felhantering
- [ ] **Prioritet:** Låg
- [ ] **Tidsuppskattning:** 4-6 timmar

#### **10. Uppdatera dokumentation**

- [ ] **Status:** Pending
- [ ] **Beskrivning:** Dokumentera ny konfigurationshantering
- [ ] **Filer:** `README.md`, `config/README.md`
- [ ] **Innehåll:**
  - [ ] Användarhandledning för UnifiedConfigManager
  - [ ] Prioritetsordning och synkronisering
  - [ ] API dokumentation
  - [ ] Troubleshooting guide
- [ ] **Prioritet:** Låg
- [ ] **Tidsuppskattning:** 2-3 timmar

## **PRIORITETSORDNING**

### **Högsta Prioritet (Implementera först):**

1. **UnifiedConfigManager** - Kärnfunktionalitet
2. **ConfigValidator** - Detektera konflikter
3. **Sync trading_rules** - Lösa aktuella problem

### **Medium Prioritet:**

4. **ConfigSynchronizer** - Automatisk synkronisering
5. **API endpoints** - Dashboard integration
6. **Startup validation** - Förhindra konflikter
7. **Migrera befintlig kod** - Använda ny system

### **Låg Prioritet:**

8. **Valideringsregler** - Avancerade regler
9. **Tester** - Kvalitetssäkring
10. **Dokumentation** - Användarhandledning

## ⏱️ **TIDSUPPSKATTNING**

### **Total tid:** 31-42 timmar

### **Fas 1:** 13-18 timmar

### **Fas 2:** 12-17 timmar

### **Fas 3:** 6-9 timmar

## **MILSTOLPAR**

### **Milstolpe 1: Grundläggande System (Vecka 1)**

- [ ] UnifiedConfigManager implementerad
- [ ] ConfigValidator implementerad
- [ ] ConfigSynchronizer implementerad
- [ ] Trading rules synkroniserade

### **Milstolpe 2: Integration (Vecka 2)**

- [ ] API endpoints implementerade
- [ ] Startup validering implementerad
- [ ] Befintlig kod migrerad
- [ ] Dashboard integration fungerar

### **Milstolpe 3: Kvalitetssäkring (Vecka 3)**

- [ ] Alla tester implementerade
- [ ] Dokumentation uppdaterad
- [ ] System testat och validerat
- [ ] Redo för produktion

## 🚨 **RISKER OCH UTMANINGAR**

### **Tekniska Risker:**

- [ ] **Breaking changes** - Befintlig kod kan brytas
- [ ] **Performance impact** - Ny system kan vara långsammare
- [ ] **Complexity** - Mer komplex kod att underhålla

### **Mitigation:**

- [ ] **Gradual migration** - Migrera steg för steg
- [ ] **Backward compatibility** - Behåll gamla API som fallback
- [ ] **Comprehensive testing** - Testa alla edge cases

## 📊 **SUCCESS METRICS**

### **Tekniska Mått:**

- [ ] **Konfigurationskonflikter:** 0 konflikter vid startup
- [ ] **Synkronisering:** 100% synkronisering mellan källor
- [ ] **Validering:** Alla konfigurationer validerade
- [ ] **Performance:** < 100ms för config operations

### **Användarupplevelse:**

- [ ] **Dashboard:** Alla inställningar synkroniserade
- [ ] **Startup:** Inga konflikter eller varningar
- [ ] **Runtime:** Konsekvent beteende
- [ ] **Maintenance:** Enkel att underhålla och utöka

## 🔄 **UPPDATERINGAR**

### **Version 1.0** (2025-01-27)

- [ ] Initial todolista skapad
- [ ] 10 huvuduppgifter definierade
- [ ] Prioritetsordning etablerad
- [ ] Tidsuppskattningar tillagda

### **Framtida Uppdateringar:**

- [ ] Statusuppdateringar för varje uppgift
- [ ] Tidsuppskattningar justerade baserat på erfarenhet
- [ ] Nya uppgifter tillagda vid behov
- [ ] Milstolpar uppdaterade

## 📞 **KONTAKT OCH SUPPORT**

### **Ansvarig:** Codex AI Assistant

### **Projekt:** Genesis Trading Bot

### **Datum:** 2025-01-27

### **Status:** Föreslaget för implementation

---

**Nästa steg:** Börja implementera UnifiedConfigManager (Uppgift #1) för att etablera grundläggande konfigurationshantering! 🚀
