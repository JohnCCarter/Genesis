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

## 🚨 **KRITISKA FÖRBÄTTRINGAR FRÅN FEEDBACK**

### **❌ Vad som var fel i v1.0:**

- **"Autosync" till .env** - bryter 12-factor app principles
- **Autoskrivning till JSON-filer** - skapar Git-konflikter och race conditions
- **In-memory overrides** - inkonsistens mellan workers/noder
- **Osäkra API:er** - ingen RBAC, validering eller audit
- **Ingen key registry** - oklart schema, metadata och prioritet

### **✅ Vad som förbättrats i v2.0:**

- **Central store** (DB/Redis) med pub/sub för kluster-konsistens
- **Kontextuell prioritet** per nyckel/domän (GLOBAL vs DOMAIN_POLICY)
- **Key Registry** med schema, metadata och validering
- **Säkra API:er** med RBAC, preview/apply-flöde och audit
- **Observability** med metrics, events och effective config

## 📝 **TODOLISTA v2.0**

### **🏗️ Fas 1: Grundläggande System (Förbättrat)**

#### **1. Skapa central Key Registry**

- [ ] **Status:** Pending
- [ ] **Beskrivning:** Central nyckel-katalog med schema, metadata och prioritetsprofiler per nyckel
- [ ] **Filer:** `config/key_registry.py`, `config/priority_profiles.py`
- [ ] **Funktioner:**
  - [ ] `ConfigKey` dataclass med type, default, min/max, priority_profile
  - [ ] `PriorityProfile` enum (GLOBAL, DOMAIN_POLICY)
  - [ ] `allowed_sources` per nyckel (runtime, feature_flags, settings, files)
  - [ ] `sensitive` flag för masking, `restart_required` flag
  - [ ] Namespace support (risk., ws., strategy., trading_rules.)
- [ ] **Prioritet:** Hög
- [ ] **Tidsuppskattning:** 3-4 timmar

#### **2. Implementera ConfigStore med Central DB/Redis**

- [ ] **Status:** Pending
- [ ] **Beskrivning:** Central store med pub/sub för kluster-konsistens och atomic updates
- [ ] **Filer:** `services/config_store.py`, `services/config_cache.py`
- [ ] **Funktioner:**
  - [ ] `ConfigStore` med DB/Redis backend
  - [ ] `ConfigCache` per process med invalidation
  - [ ] Pub/Sub för cache invalidation mellan noder
  - [ ] Atomic updates med "config generation number"
  - [ ] **INGEN synkronisering tillbaka till .env!**
- [ ] **Prioritet:** Hög
- [ ] **Tidsuppskattning:** 5-6 timmar

#### **3. Skapa UnifiedConfigManager v2**

- [ ] **Status:** Pending
- [ ] **Beskrivning:** Huvudklass med kontextuell prioritet och central store integration
- [ ] **Filer:** `services/unified_config_manager.py`
- [ ] **Funktioner:**
  - [ ] `get_config(key: str) -> Any` med kontextuell prioritet per nyckel
  - [ ] `set_config(key: str, value: Any, user: str) -> None` via central store
  - [ ] `get_effective_config(key: str) -> Dict` (value + source + generation)
  - [ ] `validate_consistency() -> List[str]` mot key registry
  - [ ] **INGEN sync_all_sources() - .env är skrivskyddad!**
- [ ] **Prioritet:** Hög
- [ ] **Tidsuppskattning:** 4-5 timmar

#### **4. Implementera ConfigValidator v2**

- [ ] **Status:** Pending
- [ ] **Beskrivning:** Validering med key registry integration och domänspecifik validering
- [ ] **Filer:** `services/config_validator.py`
- [ ] **Funktioner:**
  - [ ] Validering mot key registry (typ, min/max, allowed_sources)
  - [ ] Domänspecifik validering (trading_rules, risk, websocket)
  - [ ] Blast radius analysis för risknycklar
  - [ ] Dependency validation (t.ex. DRY_RUN_ENABLED=false + live market)
  - [ ] `get_recommendations() -> List[str]`
- [ ] **Prioritet:** Hög
- [ ] **Tidsuppskattning:** 4-5 timmar

### **🔧 Fas 2: Säkerhet och API (Nytt)**

#### **5. Skapa säkra API endpoints**

- [ ] **Status:** Pending
- [ ] **Beskrivning:** API endpoints med RBAC, preview/apply-flöde och audit logging
- [ ] **Filer:** `rest/config_routes.py`, `services/config_auth.py`
- [ ] **Endpoints:**
  - [ ] `GET /api/v2/config/effective[?scope=...&symbol=...]` - Hämta effective config
  - [ ] `POST /api/v2/config/preview` - Preview ändring med diff och effekt
  - [ ] `POST /api/v2/config/apply` - Apply ändring (kräver RBAC)
  - [ ] `POST /api/v2/config/rollback` - Rollback till snapshot
  - [ ] `GET /api/v2/config/snapshots` - Lista senaste N snapshots
- [ ] **Säkerhet:**
  - [ ] RBAC (ConfigAdmin, Viewer roles)
  - [ ] Allowlist av nycklar per roll
  - [ ] Two-man approval för risknycklar
  - [ ] Rate limiting och CSRF protection
- [ ] **Prioritet:** Hög
- [ ] **Tidsuppskattning:** 6-8 timmar

#### **6. Implementera observability**

- [ ] **Status:** Pending
- [ ] **Beskrivning:** Metrics, events och monitoring för konfigurationshantering
- [ ] **Filer:** `services/config_metrics.py`, `services/config_events.py`
- [ ] **Funktioner:**
  - [ ] Metrics: `config_overrides_total{key,source}`, `config_validation_failures_total`
  - [ ] Events: "config_changed" med payload (key, old, new, source, generation)
  - [ ] Audit log för alla ändringar (vem, vad, före/efter, ticket-id)
  - [ ] Performance metrics: `config_reload_duration_ms`
  - [ ] Health checks för central store
- [ ] **Prioritet:** Medium
- [ ] **Tidsuppskattning:** 3-4 timmar

#### **7. Lägg till kluster-konsistens**

- [ ] **Status:** Pending
- [ ] **Beskrivning:** Pub/sub, atomic updates och cache invalidation för multiprocess/kluster
- [ ] **Filer:** `services/cluster_config_manager.py`
- [ ] **Funktioner:**
  - [ ] Pub/Sub för config changes mellan noder
  - [ ] Atomic updates med RW-lock eller sequential generation numbers
  - [ ] Cache invalidation via pub/sub events
  - [ ] Bootstrap från .env vid startup, ladda cache från store
  - [ ] Failover: senaste kända snapshot i minnet vid store-bortfall
- [ ] **Prioritet:** Hög
- [ ] **Tidsuppskattning:** 5-6 timmar

### **🔄 Fas 3: Avancerade Funktioner (Nytt)**

#### **8. Implementera rollback-system**

- [ ] **Status:** Pending
- [ ] **Beskrivning:** Snapshots, staged rollout och rollback för risknycklar
- [ ] **Filer:** `services/config_snapshots.py`, `services/staged_rollout.py`
- [ ] **Funktioner:**
  - [ ] Automatiska snapshots vid ändringar
  - [ ] Staged rollout (canary): 1 bot/instrument → observera → fleet-wide
  - [ ] Rollback till tidigare snapshot
  - [ ] Export snapshot → .json för backup (ingen autosync!)
  - [ ] Guard rails för risknycklar (maxvärden, dependency checks)
- [ ] **Prioritet:** Medium
- [ ] **Tidsuppskattning:** 4-5 timmar

#### **9. Fixa trading_rules konflikter (Uppdaterat)**

- [ ] **Status:** Pending
- [ ] **Beskrivning:** Lösa konflikter mellan trading_rules.json och .env UTAN autosync
- [ ] **Filer:** `config/trading_rules.json`, `.env`
- [ ] **Lösning:**
  - [ ] **INGEN autosync** - .env är skrivskyddad startkonfiguration
  - [ ] Lägg trading_rules.\* nycklar i key registry med DOMAIN_POLICY prioritet
  - [ ] Central store hanterar runtime-ändringar
  - [ ] Manual export av snapshot → .json för backup vid behov
- [ ] **Prioritet:** Hög
- [ ] **Tidsuppskattning:** 1-2 timmar

#### **10. Skapa omfattande tester**

- [ ] **Status:** Pending
- [ ] **Beskrivning:** Tester för kluster-konsistens, API-säkerhet och edge cases
- [ ] **Filer:** `tests/test_config_v2/`
- [ ] **Tester:**
  - [ ] Unit tests: prioritet per nyckel/namespace, key registry validering
  - [ ] Integration tests: kluster pub/sub, central store atomic updates
  - [ ] Security tests: RBAC, API-validering, audit logging
  - [ ] Performance tests: config reload, cache invalidation
  - [ ] Edge cases: okända nycklar, fel typ, simultana ändringar, nätverksflapp
  - [ ] Canary/staged rollout tests
- [ ] **Prioritet:** Medium
- [ ] **Tidsuppskattning:** 6-8 timmar

## **PRIORITETSORDNING v2.0**

### **Högsta Prioritet (Implementera först):**

1. **Key Registry** - Central schema och metadata
2. **ConfigStore** - Central store med pub/sub
3. **UnifiedConfigManager v2** - Kontextuell prioritet
4. **Säkra API endpoints** - RBAC och preview/apply
5. **Fixa trading_rules konflikter** - Utan autosync

### **Medium Prioritet:**

6. **ConfigValidator v2** - Registry-integration
7. **Kluster-konsistens** - Pub/sub och atomic updates
8. **Observability** - Metrics och events
9. **Rollback-system** - Snapshots och staged rollout

### **Låg Prioritet:**

10. **Omfattande tester** - Edge cases och säkerhet

## ⏱️ **TIDSUPPSKATTNING v2.0**

### **Total tid:** 41-53 timmar

### **Fas 1:** 16-20 timmar (Grundläggande förbättrat system)

### **Fas 2:** 14-18 timmar (Säkerhet och API)

### **Fas 3:** 11-15 timmar (Avancerade funktioner)

## **MILSTOLPAR v2.0**

### **Milstolpe 1: Grundläggande System (Vecka 1)**

- [ ] Key Registry implementerad
- [ ] ConfigStore med pub/sub implementerad
- [ ] UnifiedConfigManager v2 implementerad
- [ ] Trading rules konflikter lösta (utan autosync)

### **Milstolpe 2: Säkerhet och API (Vecka 2)**

- [ ] Säkra API endpoints implementerade
- [ ] RBAC och preview/apply-flöde fungerar
- [ ] Kluster-konsistens implementerad
- [ ] Observability med metrics och events

### **Milstolpe 3: Avancerade Funktioner (Vecka 3)**

- [ ] Rollback-system implementerat
- [ ] Staged rollout för risknycklar
- [ ] Omfattande tester implementerade
- [ ] System testat och validerat

## 🚨 **RISKER OCH UTMANINGAR v2.0**

### **Tekniska Risker:**

- [ ] **Central store dependency** - Vad händer om DB/Redis är nere?
- [ ] **Kluster-konsistens** - Race conditions vid simultana ändringar
- [ ] **Performance impact** - Pub/sub och cache invalidation overhead

### **Mitigation:**

- [ ] **Failover strategy** - Bootstrap från .env, senaste snapshot i minnet
- [ ] **Atomic updates** - Sequential generation numbers, RW-locks
- [ ] **Performance optimization** - Lazy loading, batch operations

## 📊 **SUCCESS METRICS v2.0**

### **Tekniska Mått:**

- [ ] **Konfigurationskonflikter:** 0 konflikter vid startup
- [ ] **Kluster-konsistens:** 100% konsistens mellan noder
- [ ] **API-säkerhet:** 0 obehöriga ändringar
- [ ] **Performance:** < 50ms för config operations, < 100ms för cache invalidation

### **Användarupplevelse:**

- [ ] **Dashboard:** Säkra ändringar med preview/apply-flöde
- [ ] **Startup:** Bootstrap från .env, ladda från central store
- [ ] **Runtime:** Konsekvent beteende med kluster-konsistens
- [ ] **Maintenance:** Rollback och snapshots för säkerhet

## 🔄 **UPPDATERINGAR**

### **Version 2.0** (2025-01-27)

- [ ] Förbättrad design baserat på feedback
- [ ] Central store istället för autosync
- [ ] Kontextuell prioritet per nyckel
- [ ] Säkra API:er med RBAC och audit
- [ ] Key registry för schema och metadata

### **Framtida Uppdateringar:**

- [ ] Statusuppdateringar för varje uppgift
- [ ] Tidsuppskattningar justerade baserat på erfarenhet
- [ ] Nya säkerhetsförbättringar
- [ ] Performance optimeringar

## 📞 **KONTAKT OCH SUPPORT**

### **Ansvarig:** Codex AI Assistant

### **Projekt:** Genesis Trading Bot

### **Datum:** 2025-01-27

### **Status:** Förbättrad design baserat på feedback

---

**Nästa steg:** Börja implementera Key Registry (Uppgift #1) för att etablera central schema och metadata! 🚀

## 🎯 **SAMMANFATTNING AV FÖRBÄTTRINGAR**

### **Från v1.0 till v2.0:**

- ❌ **Autosync till .env** → ✅ **Central store (DB/Redis)**
- ❌ **Generell prioritet** → ✅ **Kontextuell prioritet per nyckel**
- ❌ **Ingen key registry** → ✅ **Central schema och metadata**
- ❌ **Osäkra API:er** → ✅ **RBAC, preview/apply, audit**
- ❌ **In-memory overrides** → ✅ **Pub/sub för kluster-konsistens**
- ❌ **Ingen observability** → ✅ **Metrics, events, snapshots**
