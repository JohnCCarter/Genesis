# Circuit Breaker Fix Guide

Denna guide hjälper dig att lösa circuit breaker-problem som "🚨 Circuit breaker: OPEN - too many failures".

## 🔍 **Vad är problemet?**

Circuit breakers öppnas när systemet upptäcker för många fel inom en kort tidsperiod. Detta är en säkerhetsmekanism för att skydda mot:

- Rate limiting från Bitfinex API
- Nätverksfel
- Server-fel
- Överbelastning

## 🛠️ **Lösningar**

### **1. Automatisk Recovery (Rekommenderat)**

Systemet har nu en automatisk recovery-service som:

- Kontrollerar öppna circuit breakers var 30:e sekund
- Återställer circuit breakers när cooldown-perioden har gått
- Startar automatiskt vid server-start

**Ingen åtgärd krävs** - recovery-service körs automatiskt.

### **2. Manuell Återställning**

Om du behöver återställa circuit breakers omedelbart:

#### **Via API:**

```bash
# Återställ alla circuit breakers
curl -X POST http://localhost:8000/api/circuit-breaker/reset \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'

# Tvinga recovery via recovery service
curl -X POST http://localhost:8000/api/circuit-breaker/force-recovery \
  -H "Authorization: Bearer YOUR_TOKEN"

# Kontrollera recovery status
curl http://localhost:8000/api/circuit-breaker/recovery-status \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### **Via Dashboard:**

- Gå till `/dashboard` i webbläsaren
- Hitta "Circuit Breaker" sektionen
- Klicka på "Reset All" eller "Force Recovery"

### **3. Felsökning**

#### **Kontrollera status:**

```bash
# Hämta circuit breaker status
curl http://localhost:8000/api/circuit-breaker/status \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### **Vanliga orsaker:**

1. **Rate Limiting** - För många API-anrop till Bitfinex
2. **Nätverksfel** - Instabil internetanslutning
3. **Server-fel** - Bitfinex har tekniska problem
4. **Konfigurationsfel** - Felaktiga API-nycklar

#### **Förhindra framtida problem:**

1. **Aktivera Dry Run** för säker testning:

   ```bash
   # Lägg till i .env
   ENABLE_DRY_RUN=true
   ```

2. **Kontrollera API-nycklar**:

   ```bash
   # Kontrollera att dessa är korrekt konfigurerade i .env
   BITFINEX_API_KEY=your_key
   BITFINEX_API_SECRET=your_secret
   ```

3. **Minska API-anrop**:
   - Använd längre intervall för scheduler
   - Aktivera caching
   - Undvik onödiga API-anrop

## 🔧 **Teknisk information**

### **Circuit Breaker Types:**

- **Transport Circuit Breaker** - För REST API-anrop
- **Trading Circuit Breaker** - För trading-operationer
- **Risk Circuit Breaker** - För riskhantering

### **Recovery Service:**

- Kontrollerar alla circuit breaker-typer
- Återställer automatiskt efter cooldown-period
- Loggar alla recovery-operationer
- Kan tvingas att köra manuellt

### **Konfiguration:**

```python
# Standard cooldown-perioder
TRANSPORT_CB_COOLDOWN = 60 sekunder
TRADING_CB_COOLDOWN = 300 sekunder (5 minuter)
RISK_CB_COOLDOWN = 300 sekunder (5 minuter)
```

## 📞 **Support**

Om problemet kvarstår:

1. **Kontrollera loggarna** för specifika felmeddelanden
2. **Verifiera API-nycklar** och nätverksanslutning
3. **Testa med Dry Run** först
4. **Kontakta support** med loggfiler om problemet kvarstår

## ✅ **Verifiering**

Efter åtgärder, kontrollera att circuit breakers är stängda:

```bash
# Kontrollera status
curl http://localhost:8000/api/circuit-breaker/status \
  -H "Authorization: Bearer YOUR_TOKEN"

# Förväntat svar:
{
  "open_circuit_breakers": 0,
  "total_circuit_breakers": 3,
  "circuit_breakers": {
    "transport": {"state": "closed"},
    "trading": {"state": "closed"},
    "risk": {"state": "closed"}
  }
}
```

**Status:** Alla circuit breakers ska visa `"state": "closed"` och `"open_circuit_breakers": 0`.
