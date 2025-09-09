# Circuit Breaker Integration Guide

## 🚨 Problem: "Circuit breaker is OPEN - backend appears to be down"

Detta fel uppstår när backend-servern inte svarar och circuit breakern skyddar frontend från att hänga.

## 🛠️ Lösningar

### 1. Lägg till CircuitBreakerBanner (Rekommenderat)

```tsx
// I din huvudkomponent (App.tsx eller liknande)
import { CircuitBreakerBanner } from './components/CircuitBreakerBanner';

function App() {
  return (
    <div>
      <CircuitBreakerBanner />
      {/* Resten av din app */}
    </div>
  );
}
```

**Resultat**: En röd banner visas överst på sidan när backend är nere.

### 2. Lägg till CircuitBreakerErrorBoundary

```tsx
// I din huvudkomponent
import { CircuitBreakerErrorBoundary } from './components/CircuitBreakerErrorBoundary';

function App() {
  return (
    <CircuitBreakerErrorBoundary>
      <CircuitBreakerBanner />
      {/* Resten av din app */}
    </CircuitBreakerErrorBoundary>
  );
}
```

**Resultat**: Hela appen visas som en fel-sida när backend är nere.

### 3. Använd useCircuitBreaker hook

```tsx
// I komponenter som behöver hantera backend-status
import { useCircuitBreaker } from './lib/useCircuitBreaker';

function MyComponent() {
  const { state, checkBackend, getStatusMessage, canRetry } = useCircuitBreaker();
  
  return (
    <div>
      <p>{getStatusMessage()}</p>
      {canRetry() && (
        <button onClick={checkBackend}>
          Check Backend
        </button>
      )}
    </div>
  );
}
```

## 🚀 Snabb fix för ditt nuvarande problem

### Steg 1: Lägg till CircuitBreakerBanner
```tsx
// I din huvudkomponent
import { CircuitBreakerBanner } from './components/CircuitBreakerBanner';

export default function App() {
  return (
    <div>
      <CircuitBreakerBanner />
      {/* Din befintliga app */}
    </div>
  );
}
```

### Steg 2: Starta backend-servern
```bash
# I terminal
cd tradingbot-backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

### Steg 3: Reset circuit breaker
```javascript
// I browser console
import api from './lib/api';
api.resetCircuitBreaker();
```

## 📱 Användarupplevelse

### Före (utan circuit breaker):
- ❌ App hänger oändligt
- ❌ "Väntar" i Network tab
- ❌ Ingen feedback till användaren
- ❌ Användaren vet inte vad som händer

### Efter (med circuit breaker):
- ✅ App skyddar sig från hängning
- ✅ Tydlig felmeddelande
- ✅ "Check Backend" knapp
- ✅ Automatisk återhämtning efter 30s
- ✅ Användaren vet vad som händer

## 🔧 Konfiguration

### Anpassa circuit breaker inställningar
```typescript
// I api.ts
const circuitBreakerState = {
  failureThreshold: 5,      // Öppna efter 5 fel
  recoveryTimeout: 30000,   // 30s recovery timeout
};
```

### Anpassa timeout inställningar
```typescript
// I api.ts
const API_TIMEOUT = 10000; // 10 sekunder timeout
const MAX_RETRIES = 3;     // 3 försök
const RETRY_DELAY = 1000;  // 1 sekund mellan försök
```

## 🎯 Bästa praxis

### 1. Alltid starta backend först
```bash
# Terminal 1: Backend
cd tradingbot-backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2: Frontend
cd frontend/dashboard
npm run dev
```

### 2. Använd både banner och error boundary
```tsx
function App() {
  return (
    <CircuitBreakerErrorBoundary>
      <CircuitBreakerBanner />
      {/* Din app */}
    </CircuitBreakerErrorBoundary>
  );
}
```

### 3. Hantera fel gracefully i komponenter
```tsx
function DataComponent() {
  const { state, checkBackend } = useCircuitBreaker();
  
  const fetchData = async () => {
    if (state.isOpen) {
      console.log('Circuit breaker is open, cannot fetch data');
      return;
    }
    
    try {
      const data = await api.get('/api/v2/data');
      // Hantera data
    } catch (error) {
      // Fel hanteras automatiskt av circuit breaker
    }
  };
  
  return (
    <div>
      {state.isOpen ? (
        <div className="offline-message">
          <p>Backend is offline</p>
          <button onClick={checkBackend}>Check Backend</button>
        </div>
      ) : (
        <button onClick={fetchData}>Fetch Data</button>
      )}
    </div>
  );
}
```

## 🔍 Debugging

### Console logs att leta efter:
```
🚨 Circuit breaker: OPEN - too many failures
🌐 API request (attempt 1/4): http://127.0.0.1:8000/api/v2/status
⚠️ API attempt 1 failed: Request timeout after 10000ms
🔄 Retrying in 1000ms...
```

### Network tab:
- **Cancelled** = Timeout (bra, inte hängning)
- **Failed** = Nätverksfel
- **Completed** = Lyckat anrop

### Circuit breaker status:
```javascript
// I browser console
import api from './lib/api';
console.log(api.getCircuitBreakerStatus());
```

## 🚀 Resultat

Med dessa förbättringar får du:

1. **Inga hängningar** - Circuit breaker skyddar appen
2. **Tydlig feedback** - Användaren vet vad som händer
3. **Automatisk återhämtning** - Försöker igen efter 30s
4. **Manuell kontroll** - "Check Backend" knapp
5. **Bättre användarupplevelse** - Professionell felhantering

**Dina hängningsproblem är nu helt lösta!** 🎉
