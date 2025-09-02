const BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

export function getApiBase(): string {
  return BASE;
}

function token(): string {
  try {
    return localStorage.getItem("jwt") || "";
  } catch {
    return "";
  }
}

function isTokenExpired(token: string): boolean {
  try {
    const parts = token.split('.');
    if (parts.length >= 2) {
      const payload = JSON.parse(atob(parts[1]));
      const now = Math.floor(Date.now() / 1000);
      return !(payload.exp && payload.exp > now);
    }
  } catch (error) {
    console.error('❌ Error checking token expiration:', error);
  }
  return true; // Consider invalid tokens as expired
}

function headers(): Record<string, string> {
  const h: Record<string, string> = { "Content-Type": "application/json" };
  const t = token();
  if (t) h["Authorization"] = `Bearer ${t}`;
  return h;
}

export async function get<T = any>(path: string): Promise<T> {
  const r = await fetch(`${BASE}${path}`, { headers: headers() });
  if (!r.ok) throw new Error(await r.text());
  return r.json() as Promise<T>;
}

export async function post<T = any>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(body ?? {}),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json() as Promise<T>;
}

export async function ensureToken(): Promise<string> {
  console.log('🔑 ensureToken called');

  const existingToken = token();
  if (existingToken) {
    console.log('🔑 Existing token found, checking if expired...');

    // Check if token is expired
    try {
      const parts = existingToken.split('.');
      if (parts.length >= 2) {
        const payload = JSON.parse(atob(parts[1]));
        const now = Math.floor(Date.now() / 1000);

        if (payload.exp && payload.exp > now) {
          console.log('🔑 Existing token is still valid, returning it');
          return existingToken;
        } else {
          console.log('🔑 Existing token is expired, removing it');
          localStorage.removeItem('jwt');
        }
      }
    } catch (error) {
      console.log('🔑 Could not decode existing token, removing it');
      localStorage.removeItem('jwt');
    }
  }

  console.log('🔑 No valid token found, requesting new one from:', `${BASE}/api/v2/auth/ws-token`);

  try {
    const res = await post<{ token?: string; success?: boolean; error?: string }>("/api/v2/auth/ws-token", {
      user_id: "frontend_user",
      scope: "read",
      expiry_hours: 1,
    });

    console.log('🔑 Token response:', res);

    if (res && res.token) {
      localStorage.setItem("jwt", res.token);
      console.log('🔑 New token saved to localStorage');
      return res.token;
    } else if (res && res.success === false) {
      throw new Error(res.error || 'Token generation failed');
    } else {
      throw new Error('No token in response');
    }
  } catch (error) {
    console.error('❌ ensureToken failed:', error);
    throw error;
  }
}

export async function getText(path: string): Promise<string> {
  const r = await fetch(`${BASE}${path}`, { headers: headers() });
  if (!r.ok) throw new Error(await r.text());
  return r.text();
}

const api = { get, post, getText, ensureToken, getApiBase };
export default api;
