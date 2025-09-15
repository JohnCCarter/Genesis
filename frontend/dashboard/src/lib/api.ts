const BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

const API_TIMEOUT = 10000; // ms
const MAX_RETRIES = 3;
const RETRY_DELAY = 1000; // ms

type Json = any;

type CBState = {
  isOpen: boolean;
  failureCount: number;
  lastFailureTime: number;
  failureThreshold: number;
  recoveryTimeout: number;
};
let circuitBreakerState: CBState = {
  isOpen: false,
  failureCount: 0,
  lastFailureTime: 0,
  failureThreshold: 5,
  recoveryTimeout: 30000,
};

// ---------- Circuit Breaker helpers ----------
function isCircuitBreakerOpen(): boolean {
  if (!circuitBreakerState.isOpen) return false;
  const now = Date.now();
  if (now - circuitBreakerState.lastFailureTime > circuitBreakerState.recoveryTimeout) {
    // half-open: allow next call
    circuitBreakerState.isOpen = false;
    circuitBreakerState.failureCount = 0;
    return false;
  }
  return true;
}
function recordFailureOnce(): void {
  circuitBreakerState.failureCount += 1;
  circuitBreakerState.lastFailureTime = Date.now();
  if (circuitBreakerState.failureCount >= circuitBreakerState.failureThreshold) {
    circuitBreakerState.isOpen = true;
    console.error("🚨 Circuit breaker: OPEN - too many failures");
  }
}
function recordSuccess(): void {
  circuitBreakerState.failureCount = 0;
  circuitBreakerState.isOpen = false;
}

// ---------- Token / Headers ----------
function token(): string {
  try {
    return localStorage.getItem("jwt") || "";
  } catch {
    return "";
  }
}
function base64UrlDecode(s: string): string {
  // Convert base64url → base64
  const pad = s.length % 4 === 2 ? "==" : s.length % 4 === 3 ? "=" : "";
  const b64 = s.replace(/-/g, "+").replace(/_/g, "/") + pad;
  return atob(b64);
}
function isTokenExpiredStrict(t: string): boolean {
  try {
    const parts = t.split(".");
    if (parts.length >= 2) {
      const payload = JSON.parse(base64UrlDecode(parts[1]));
      const now = Math.floor(Date.now() / 1000);
      return !(payload.exp && payload.exp > now);
    }
  } catch (e) {
    console.warn("JWT decode failed:", e);
  }
  return true;
}
function headers(): Record<string, string> {
  const h: Record<string, string> = { "Content-Type": "application/json" };
  const t = token();
  if (t) h["Authorization"] = `Bearer ${t}`;
  return h;
}

// ---------- Fetch utils ----------
async function fetchWithTimeout(url: string, options: RequestInit, timeoutMs: number): Promise<Response> {
  const controller = new AbortController();
  const to = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, { ...options, signal: controller.signal });
    return res;
  } finally {
    clearTimeout(to);
  }
}

function shouldRetry(status: number | null, err: unknown): boolean {
  // Retry on network/timeout OR 5xx OR 429. Do NOT retry 4xx (except 429).
  if (status === null) return true; // network/abort
  if (status === 429) return true;
  if (status >= 500) return true;
  return false;
}

function shouldCountAsCBFailure(status: number | null): boolean {
  // Only network/timeout/5xx/429 trip the breaker
  if (status === null) return true;
  return status === 429 || status >= 500;
}

async function parseJsonSafely(res: Response): Promise<Json | undefined> {
  const ct = res.headers.get("content-type") || "";
  const len = res.headers.get("content-length");
  if (res.status === 204) return undefined;
  if (!ct.includes("application/json")) return undefined;
  if (len === "0") return undefined;
  try {
    return await res.json();
  } catch {
    return undefined;
  }
}

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

// ---------- Core retry wrapper ----------
async function fetchWithRetry<T>(
  url: string,
  options: RequestInit,
  {
    maxRetries = MAX_RETRIES,
    timeout = API_TIMEOUT,
    ignoreCircuitBreaker = false,
    refreshOn401 = true,
    // När vi hämtar token ska inte CB triggas av dessa anrop
    doNotRecordCB = false,
  }: {
    maxRetries?: number;
    timeout?: number;
    ignoreCircuitBreaker?: boolean;
    refreshOn401?: boolean;
    doNotRecordCB?: boolean;
  } = {}
): Promise<T> {
  if (!ignoreCircuitBreaker && isCircuitBreakerOpen()) {
    // Add a small delay before throwing error to prevent rapid retries
    await sleep(1000);
    throw new Error("Circuit breaker is OPEN - backend appears to be down");
  }

  // We will record at most ONE CB failure per overall call
  let cbFailureRecorded = false;
  let triedRefreshForThisCall = false;

  let lastErr: Error | null = null;
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    let status: number | null = null;
    try {
      const res = await fetchWithTimeout(url, options, timeout);
      status = res.status;

      if (status === 401 && refreshOn401) {
        // Try refresh ONCE per overall call
        if (!triedRefreshForThisCall) {
          triedRefreshForThisCall = true;
          try {
            await ensureToken(/*bypass CB*/ true);
          } catch (e) {
            // refresh failed → fallthrough to error handling
          }
          // retry immediately (do not penalize CB yet)
          continue;
        }
      }

      if (!res.ok) {
        // Read text for error message, but parsing JSON errors safely
        const text = await res.text().catch(() => "");
        throw new Error(`HTTP ${status}: ${text || res.statusText}`);
      }

      const maybeJson = await parseJsonSafely(res);
      // If endpoint returns JSON, return it; else cast as any (caller can treat undefined/void)
      recordSuccess();
      return (maybeJson as T) ?? (undefined as unknown as T);
    } catch (e: any) {
      lastErr = e instanceof Error ? e : new Error(String(e));

      // decide retry
      const retryable = shouldRetry(status, e);
      const countsForCB = shouldCountAsCBFailure(status);

      if (countsForCB && !cbFailureRecorded && !doNotRecordCB) {
        recordFailureOnce();
        cbFailureRecorded = true;
      }

      if (attempt < maxRetries && retryable) {
        const delay = RETRY_DELAY * Math.pow(2, attempt) + Math.floor(Math.random() * 200); // jitter
        console.warn(`⚠️ API attempt ${attempt + 1} failed (${status ?? "network"}): ${lastErr.message}. Retrying in ${delay}ms`);
        await sleep(delay);
        continue;
      }

      break; // give up
    }
  }

  throw new Error(`API request failed after ${maxRetries + 1} attempts: ${lastErr?.message}`);
}

// ---------- Public API ----------
export function getApiBase(): string {
  return BASE;
}

export async function get<T = any>(path: string): Promise<T> {
  // Make sure token is valid before privileged calls (optional shortcut)
  const t = token();
  if (!t || isTokenExpiredStrict(t)) {
    try { await ensureToken(true); } catch { /* proceed; some GETs may be public */ }
  }
  return fetchWithRetry<T>(`${BASE}${path}`, { method: "GET", headers: headers() });
}

// Per-request override: timeout/retries/CB
export async function getWith<T = any>(
  path: string,
  opts: { timeout?: number; maxRetries?: number; ignoreCircuitBreaker?: boolean; doNotRecordCB?: boolean } = {}
): Promise<T> {
  const t = token();
  if (!t || isTokenExpiredStrict(t)) {
    try { await ensureToken(true); } catch {}
  }
  const { timeout, maxRetries, ignoreCircuitBreaker, doNotRecordCB } = opts;
  return fetchWithRetry<T>(`${BASE}${path}`, { method: "GET", headers: headers() }, { timeout, maxRetries, ignoreCircuitBreaker, doNotRecordCB });
}

export async function post<T = any>(path: string, body?: unknown): Promise<T> {
  const t = token();
  if (!t || isTokenExpiredStrict(t)) {
    await ensureToken(true); // bypass CB to avoid deadlock
  }
  return fetchWithRetry<T>(`${BASE}${path}`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(body ?? {}),
  });
}

export async function postWith<T = any>(
  path: string,
  body?: unknown,
  opts: { timeout?: number; maxRetries?: number; ignoreCircuitBreaker?: boolean; doNotRecordCB?: boolean } = {}
): Promise<T> {
  const t = token();
  if (!t || isTokenExpiredStrict(t)) {
    await ensureToken(true);
  }
  const { timeout, maxRetries, ignoreCircuitBreaker, doNotRecordCB } = opts;
  return fetchWithRetry<T>(`${BASE}${path}`, { method: "POST", headers: headers(), body: JSON.stringify(body ?? {}) }, { timeout, maxRetries, ignoreCircuitBreaker, doNotRecordCB });
}

export async function ensureToken(ignoreCB: boolean = false): Promise<string> {
  const existing = token();
  if (existing && !isTokenExpiredStrict(existing)) return existing;

  // call auth endpoint WITHOUT involving the breaker (to recover when OPEN)
  // MCP är avvecklat → använd officiell auth endpoint
  const url = `${BASE}/api/v2/auth/ws-token`;
  const body = JSON.stringify({ user_id: "frontend_user", scope: "read", expiry_hours: 1 });
  const res = await fetchWithRetry<{ token?: string; success?: boolean; error?: string }>(
    url,
    { method: "POST", headers: { "Content-Type": "application/json" }, body },
    { ignoreCircuitBreaker: ignoreCB, refreshOn401: false, doNotRecordCB: true }
  );

  if (res && res.token) {
    localStorage.setItem("jwt", res.token);
    return res.token;
  }
  if (res && res.success === false) throw new Error(res.error || "Token generation failed");
  throw new Error("No token in response");
}

export async function getText(path: string): Promise<string> {
  const res = await fetchWithTimeout(`${BASE}${path}`, { method: "GET", headers: headers() }, API_TIMEOUT);
  if (!res.ok) throw new Error(await res.text().catch(() => res.statusText));
  return await res.text();
}

export function getCircuitBreakerStatus() {
  return {
    isOpen: circuitBreakerState.isOpen,
    failureCount: circuitBreakerState.failureCount,
    lastFailureTime: circuitBreakerState.lastFailureTime,
    timeSinceLastFailure: Date.now() - circuitBreakerState.lastFailureTime,
  };
}

export function resetCircuitBreaker() {
  circuitBreakerState.isOpen = false;
  circuitBreakerState.failureCount = 0;
  circuitBreakerState.lastFailureTime = 0;
  console.log("🔄 Circuit breaker manually reset");
}

export async function checkBackendHealth(): Promise<boolean> {
  try {
    const controller = new AbortController();
    const to = setTimeout(() => controller.abort(), 5000);
    const res = await fetch(`${BASE}/health`, { method: "GET", signal: controller.signal });
    clearTimeout(to);
    return res.ok;
  } catch {
    return false;
  }
}

const api = {
  get,
  getWith,
  post,
  postWith,
  getText,
  ensureToken,
  getApiBase,
  getCircuitBreakerStatus,
  resetCircuitBreaker,
  checkBackendHealth,
};
export default api;
