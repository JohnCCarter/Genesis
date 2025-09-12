# Risk Guards & Bitfinex-konto koppling

## 🚨 **AKTUELL STATUS: NEJ - Risk Guards speglar INTE ditt verkliga Bitfinex-konto**

### **Vad som händer nu:**

❌ **RiskGuardsService** returnerar **0.0** för current_equity
❌ **UnifiedRiskService** returnerar **10000.0** (hardcoded fallback)
❌ **Ingen koppling till verkliga Bitfinex-balanser**

### **Varför är det så?**

Systemet har **avstängt** equity-hämtning för att undvika hängningar:

```python
# I services/risk_guards.py
def _get_current_equity(self) -> float:
    # Enkel fallback - returnera 0.0 för att undvika hängningar
    logger.debug("⚠️ Equity computation disabled to prevent hanging")
    return 0.0  # ← HARDCODED!

# I services/unified_risk_service.py
def _get_current_equity(self) -> float:
    # Enkel fallback - returnera 10000 för att undvika hängningar
    logger.debug("⚠️ Equity computation disabled to prevent hanging")
    return 10000.0  # ← HARDCODED!
```

### **Vad betyder det för dig:**

- **Daily Loss %** = 100% (eftersom current_equity = 0, start_equity = 10000)
- **Drawdown %** = 100% (samma anledning)
- **Risk Guards** fungerar inte med verkliga balanser
- **Kill Switch** aktiveras inte baserat på verklig förlust
- **Max Daily Loss** kontrollerar inte verklig förlust

## 🔧 **Lösning - Aktivera verklig equity-hämtning:**

### **Steg 1: Fixa RiskGuardsService**

Ersätt `_get_current_equity()` metoden i `services/risk_guards.py`:

```python
def _get_current_equity(self) -> float:
    """Hämta live equity (USD) från Bitfinex med robust timeout."""
    try:
        import asyncio
        from services.performance import PerformanceService

        # Använd PerformanceService för att hämta verklig equity
        async def _get_equity_async():
            try:
                perf_service = PerformanceService()
                equity_data = await perf_service.compute_current_equity()
                return equity_data.get("total_usd", 0.0)
            except Exception as e:
                logger.warning(f"⚠️ Kunde inte hämta equity från PerformanceService: {e}")
                return 0.0

        # Kör async funktion med timeout
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Om vi redan är i en event loop, skapa en ny task
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, _get_equity_async())
                    return future.result(timeout=5.0)
            else:
                # Om ingen event loop körs, kör direkt
                return asyncio.run(_get_equity_async())
        except Exception as e:
            logger.warning(f"⚠️ Timeout eller fel vid equity-hämtning: {e}")
            return 0.0

    except Exception as e:
        logger.error(f"❌ Kunde inte hämta aktuell equity: {e}")
        return 0.0
```

### **Steg 2: Fixa UnifiedRiskService**

Ersätt `_get_current_equity()` metoden i `services/unified_risk_service.py`:

```python
def _get_current_equity(self) -> float:
    """Hämta aktuell equity från Bitfinex."""
    try:
        import asyncio
        from services.performance import PerformanceService

        # Använd PerformanceService för att hämta verklig equity
        async def _get_equity_async():
            try:
                perf_service = PerformanceService()
                equity_data = await perf_service.compute_current_equity()
                return equity_data.get("total_usd", 0.0)
            except Exception as e:
                logger.warning(f"⚠️ Kunde inte hämta equity från PerformanceService: {e}")
                return 0.0

        # Kör async funktion med timeout
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, _get_equity_async())
                    return future.result(timeout=5.0)
            else:
                return asyncio.run(_get_equity_async())
        except Exception as e:
            logger.warning(f"⚠️ Timeout eller fel vid equity-hämtning: {e}")
            return 0.0

    except Exception as e:
        logger.error(f"❌ Kunde inte hämta aktuell equity: {e}")
        return 0.0
```

### **Steg 3: Verifiera PerformanceService**

Kontrollera att `services/performance.py` har `compute_current_equity()` metoden som:
- Hämtar wallets från Bitfinex via `WalletService`
- Hämtar positions från Bitfinex via `PositionsService`
- Konverterar alla valutor till USD
- Returnerar total equity

## 🎯 **Efter fixen:**

### **Risk Guards kommer att:**
- ✅ Visa verklig current_equity från ditt Bitfinex-konto
- ✅ Beräkna korrekt daily_loss_percentage baserat på verklig förlust
- ✅ Aktivera Kill Switch vid verklig förlust över threshold
- ✅ Kontrollera Max Daily Loss mot verklig förlust
- ✅ Uppdatera drawdown baserat på verklig equity

### **Exempel på vad du kommer att se:**

**Före fix:**
```json
{
  "current_equity": 0.0,  // ← Hardcoded
  "daily_loss_percentage": 100.0,  // ← Felaktigt
  "drawdown_percentage": 100.0  // ← Felaktigt
}
```

**Efter fix:**
```json
{
  "current_equity": 15420.50,  // ← Verklig Bitfinex balance
  "daily_loss_percentage": 2.3,  // ← Korrekt beräkning
  "drawdown_percentage": 5.8  // ← Korrekt beräkning
}
```

## ⚠️ **Viktiga noter:**

1. **Timeout-hantering** - Equity-hämtning har 5 sekunders timeout för att undvika hängningar
2. **Fallback** - Om Bitfinex API inte svarar, returneras 0.0 istället för att hänga
3. **Performance** - Equity-hämtning kan ta några sekunder första gången
4. **Caching** - Överväg att lägga till caching för att förbättra prestanda

## 🚀 **Nästa steg:**

1. **Implementera fixen** ovan i båda filerna
2. **Testa equity-hämtning** via `/api/wallets/balance` endpoint
3. **Verifiera risk guards** visar korrekt data
4. **Kontrollera att Kill Switch** aktiveras vid verklig förlust
5. **Övervaka prestanda** för att säkerställa inga hängningar

**Sammanfattning:** Risk guards speglar för närvarande INTE ditt verkliga Bitfinex-konto, men kan fixas genom att aktivera equity-hämtning från PerformanceService som i sin tur hämtar data från Bitfinex API.
