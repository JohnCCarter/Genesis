# Komponentaktivering - TradingBot Backend

Denna guide förklarar hur man aktiverar olika komponenter i TradingBot Backend.

## 🔧 **Tillgängliga komponenter**

### 1. **Dry Run Mode** 📝
- **Vad:** Simulerar trades utan att utföra riktiga ordrar
- **Användning:** Säker testning av trading-strategier
- **Aktivering:** `ENABLE_DRY_RUN=true` i `.env`

### 2. **Probability Model** 🧠
- **Vad:** ML-baserad signal-generering och analys
- **Användning:** Avancerad marknadsanalys och automatisk signal-generering
- **Aktivering:** `ENABLE_PROB_MODEL=true` i `.env`

### 3. **Scheduler** 🗓️
- **Vad:** Schemalagda jobb (equity snapshots, validation, cleanup)
- **Användning:** Automatisk underhåll och datahantering
- **Aktivering:** `ENABLE_SCHEDULER=true` i `.env`

### 4. **Auto Trading** 🤖
- **Vad:** Automatisk handel baserat på ML-modell
- **Användning:** Fullständig automation av trading-beslut
- **Aktivering:** `PROB_AUTOTRADE_ENABLED=true` i `.env`

## 🚀 **Snabbstart**

### **Aktivera alla komponenter (Dev Mode):**
```bash
# Lägg till i .env-filen
DEV_MODE=true
```

### **Aktivera individuella komponenter:**
```bash
# Lägg till i .env-filen
ENABLE_DRY_RUN=true
ENABLE_PROB_MODEL=true
ENABLE_SCHEDULER=true
PROB_AUTOTRADE_ENABLED=true
```

## 📋 **Steg-för-steg instruktioner**

### **Steg 1: Kopiera env.example**
```bash
cd tradingbot-backend
cp env.example .env
```

### **Steg 2: Redigera .env-filen**
Öppna `.env` och ändra värdena:
```bash
# Aktivera alla komponenter
DEV_MODE=true

# ELLER aktivera individuellt
ENABLE_DRY_RUN=true
ENABLE_PROB_MODEL=true
ENABLE_SCHEDULER=true
```

### **Steg 3: Starta om servern**
```bash
# Stoppa servern (Ctrl+C)
# Starta igen
uvicorn main:app --reload
```

### **Steg 4: Kontrollera status**
Kontrollera loggarna för att se vilka komponenter som aktiverades:
```
🔧 Komponent-status vid startup:
  📝 Dry Run: ✅ Aktiverat
  🧠 Probability Model: ✅ Aktiverat
  🤖 Auto Trading: ✅ Aktiverat
  🗓️ Scheduler: ✅ Aktiverat
```

## 🔍 **Kontrollera komponentstatus**

### **Via API:**
```bash
# Kontrollera feature flags
curl http://localhost:8000/api/feature-flags

# Kontrollera scheduler status
curl http://localhost:8000/api/mode/scheduler

# Kontrollera dry run status
curl http://localhost:8000/api/mode/dry-run
```

### **Via Dashboard:**
- Gå till `/dashboard` i webbläsaren
- Kontrollera status-panelen för komponenter

## ⚠️ **Viktiga noter**

### **Säkerhet:**
- **Dry Run** är säkert att aktivera (ingen riktig handel)
- **Probability Model** är säkert (endast analys)
- **Scheduler** är säkert (endast underhållsjobb)
- **Auto Trading** kan utföra riktiga trades - använd försiktigt!

### **Prestanda:**
- **Scheduler** kan öka CPU-användning
- **Probability Model** kan öka minnesanvändning
- **Auto Trading** kan öka API-anrop

### **Felsökning:**
Om komponenter inte aktiveras:
1. Kontrollera `.env`-filen
2. Starta om servern
3. Kontrollera loggarna för felmeddelanden
4. Kontrollera att miljövariablerna är korrekt formaterade (`true`/`false`)

## 🎯 **Rekommenderade konfigurationer**

### **Utveckling:**
```bash
DEV_MODE=true
DEBUG=true
```

### **Testning:**
```bash
ENABLE_DRY_RUN=true
ENABLE_PROB_MODEL=true
ENABLE_SCHEDULER=true
```

### **Produktion:**
```bash
ENABLE_SCHEDULER=true
# Aktivera endast komponenter du behöver
```

## 📞 **Support**

Om du har problem med komponentaktivering:
1. Kontrollera loggarna för felmeddelanden
2. Verifiera `.env`-konfigurationen
3. Kontrollera att alla beroenden är installerade
4. Starta om servern efter ändringar
