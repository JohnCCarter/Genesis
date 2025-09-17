# Backend Troubleshooting Guide

## 🚨 Circuit Breaker OPEN - Vad betyder detta?

När du ser meddelandet "🚨 Circuit breaker: OPEN - too many failures" betyder det att:

1. **Backend-servern svarar inte** (timeout efter 10 sekunder)
2. **Frontend har skyddat sig** genom att stoppa API-anrop
3. **Circuit breakern öppnades** efter 5 misslyckade försök

## 🔍 Diagnostik

### 1. Kontrollera om backend körs
```bash
# I terminal (från tradingbot-backend mapp)
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

### 2. Testa backend direkt
```bash
# I terminal
curl http://localhost:8000/health
# Eller
python -c "import requests; print(requests.get('http://localhost:8000/health').json())"
```

### 3. Kontrollera port 8000
```bash
# Windows
netstat -an | findstr :8000

# Om inget visas = backend körs inte
```

## 🛠️ Lösningar

### Lösning 1: Starta backend
```bash
cd tradingbot-backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

### Lösning 2: Reset circuit breaker (temporärt)
```javascript
// I browser console
import api from './lib/api';
api.resetCircuitBreaker();
```

### Lösning 3: Använd BackendStatus komponent
```tsx
import { BackendStatus } from './components/BackendStatus';

// Lägg till i din app
<BackendStatus />
```

## 📱 Frontend förbättringar

### 1. Lägg till BackendStatus komponent
```tsx
// I din huvudkomponent
import { BackendStatus } from './components/BackendStatus';

function App() {
  return (
    <div>
      {/* Din app */}
      <BackendStatus />
    </div>
  );
}
```

### 2. Använd useBackendStatus hook
```tsx
import { useBackendStatus } from './lib/useBackendStatus';

function MyComponent() {
  const { status, checkBackend, getStatusMessage } = useBackendStatus();
  
  return (
    <div>
      <p>{getStatusMessage()}</p>
      {!status.isOnline && (
        <button onClick={checkBackend}>
          Check Backend
        </button>
      )}
    </div>
  );
}
```

### 3. Hantera API-fel gracefully
```tsx
import { useApiError } from './lib/useApiError';

function DataComponent() {
  const { error, handleError, clearError } = useApiError();
  
  const fetchData = async () => {
    try {
      const data = await api.get('/api/v2/data');
      clearError();
    } catch (err) {
      handleError(err);
    }
  };
  
  return (
    <div>
      {error && (
        <div className="error-banner">
          <p>{error.message}</p>
          {error.retryable && (
            <button onClick={fetchData}>Retry</button>
          )}
        </div>
      )}
    </div>
  );
}
```

## 🔄 Automatisk återhämtning

Circuit breakern kommer automatiskt att:
- **Försöka igen efter 30 sekunder** (recovery timeout)
- **Återställas vid första lyckade anrop**
- **Logga alla försök** i console

## 📊 Status indikatorer

### I browser console:
```javascript
// Kontrollera circuit breaker status
import api from './lib/api';
console.log(api.getCircuitBreakerStatus());

// Testa backend health
api.checkBackendHealth().then(online => 
  console.log('Backend online:', online)
);
```

### I UI:
- **✅ Backend Online** - Allt fungerar
- **⚠️ Backend Issues** - Några fel, men fungerar
- **🚨 Backend Offline** - Circuit breaker öppen

## 🚀 Bästa praxis

### 1. Alltid starta backend först
```bash
# Terminal 1: Backend
cd tradingbot-backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2: Frontend
cd frontend/dashboard
npm run dev
```

### 2. Använd BackendStatus komponent
Lägg alltid till BackendStatus i din app för att se backend-status.

### 3. Hantera fel gracefully
Använd useApiError hook för att visa användarvänliga felmeddelanden.

### 4. Testa offline-scenario
Stäng av backend och se att frontend hanterar det gracefully.

## 🔧 Debugging

### Console logs att leta efter:
```
🌐 API request (attempt 1/4): http://127.0.0.1:8000/api/v2/status
⚠️ API attempt 1 failed: Request timeout after 10000ms
🔄 Retrying in 1000ms...
🚨 Circuit breaker: OPEN - too many failures
```

### Network tab i DevTools:
- **Pending** = Request hänger (före våra fixes)
- **Cancelled** = Timeout (efter våra fixes)
- **Failed** = Nätverksfel

## 📞 När allt annat misslyckas

1. **Starta om backend**:
   ```bash
   # Stoppa backend (Ctrl+C)
   cd tradingbot-backend
   python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
   ```

2. **Reset circuit breaker**:
   ```javascript
   // I browser console
   api.resetCircuitBreaker();
   ```

3. **Kontrollera port-konflikter**:
   ```bash
   # Om port 8000 är upptagen
   netstat -an | findstr :8000
   ```

4. **Starta med debug-flags**:
   ```bash
   cd tradingbot-backend
   python scripts/start_debug.py
   ```
