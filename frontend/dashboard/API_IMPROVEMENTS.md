# Frontend API Förbättringar

## Problem som lösts

### 1. "Väntar" status i Dev Tools/Network
**Problem**: API-anrop hängde oändligt utan timeout
**Lösning**: 
- ✅ 10 sekunder timeout på alla fetch-anrop
- ✅ AbortController för att avbryta hängande requests
- ✅ Tydliga felmeddelanden för timeout

### 2. Ingen retry-logik
**Problem**: Ett misslyckat anrop stoppade allt
**Lösning**:
- ✅ 3 försök med exponential backoff (1s, 2s, 4s)
- ✅ Automatisk retry för nätverksfel
- ✅ Logging av alla försök

### 3. Ingen circuit breaker
**Problem**: Frontend fortsatte att försöka när backend var nere
**Lösning**:
- ✅ Circuit breaker öppnas efter 5 fel
- ✅ 30 sekunder recovery timeout
- ✅ Automatisk återhämtning när backend kommer tillbaka

## Nya funktioner

### 1. Förbättrad API-klient (`api.ts`)
```typescript
// Timeout och retry
const response = await api.get('/api/v2/status');

// Circuit breaker status
const status = api.getCircuitBreakerStatus();
console.log(status.isOpen); // true/false

// Manuell reset
api.resetCircuitBreaker();
```

### 2. API Status Komponent (`ApiStatus.tsx`)
```tsx
import { ApiStatus } from './components/ApiStatus';

// Visa i din app
<ApiStatus />
```

Visar:
- 🚨 Circuit Breaker OPEN
- ⚠️ X failures  
- ✅ API Healthy

### 3. Error Handling Hook (`useApiError.ts`)
```typescript
import { useApiError } from './lib/useApiError';

const { error, handleError, clearError } = useApiError();

try {
  const data = await api.get('/api/v2/data');
} catch (err) {
  const apiError = handleError(err);
  console.log(apiError.type); // 'timeout', 'network', 'server', etc.
}
```

### 4. Throttled API Calls (`useThrottledValue.ts`)
```typescript
import { useThrottledApiCall } from './lib/useThrottledValue';

const throttledApiCall = useThrottledApiCall(api.get, 1000); // Max 1 call per second
```

## Konfiguration

### Environment Variables
```bash
# API base URL
VITE_API_BASE=http://127.0.0.1:8000

# Timeout (ms)
VITE_API_TIMEOUT=10000

# Max retries
VITE_API_MAX_RETRIES=3
```

### Circuit Breaker Settings
```typescript
// I api.ts
const circuitBreakerState = {
  failureThreshold: 5,      // Öppna efter 5 fel
  recoveryTimeout: 30000,   // 30s recovery
};
```

## Debugging

### 1. Console Logs
Alla API-anrop loggas:
```
🌐 API request (attempt 1/4): http://127.0.0.1:8000/api/v2/status
⚠️ API attempt 1 failed: Request timeout after 10000ms
🔄 Retrying in 1000ms...
✅ API success: http://127.0.0.1:8000/api/v2/status
```

### 2. Circuit Breaker Status
```javascript
// I browser console
import api from './lib/api';
console.log(api.getCircuitBreakerStatus());
```

### 3. Network Tab
- Requests har nu tydliga status: "Completed", "Failed", "Cancelled"
- Timeout requests visas som "Cancelled" efter 10s
- Retry attempts visas som separata requests

## Användning

### 1. Lägg till ApiStatus komponent
```tsx
// I din huvudkomponent
import { ApiStatus } from './components/ApiStatus';

function App() {
  return (
    <div>
      {/* Din app */}
      <ApiStatus />
    </div>
  );
}
```

### 2. Använd error handling
```tsx
import { useApiError } from './lib/useApiError';

function MyComponent() {
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
        <div className="error">
          {error.message}
          {error.retryable && <button onClick={fetchData}>Retry</button>}
        </div>
      )}
    </div>
  );
}
```

### 3. Throttle API calls
```tsx
import { useThrottledApiCall } from './lib/useThrottledValue';

function DataComponent() {
  const throttledGet = useThrottledApiCall(api.get, 2000); // Max 1 call per 2s
  
  const handleRefresh = () => {
    throttledGet('/api/v2/refresh'); // Automatiskt throttlad
  };
}
```

## Resultat

### Före
- ❌ Anrop hängde oändligt ("väntar" i Network tab)
- ❌ Ingen retry vid fel
- ❌ Frontend kraschade när backend var nere
- ❌ Ingen feedback till användaren

### Efter  
- ✅ 10s timeout på alla anrop
- ✅ Automatisk retry med backoff
- ✅ Circuit breaker skyddar mot backend-problem
- ✅ Tydlig status och felhantering
- ✅ Bättre användarupplevelse
