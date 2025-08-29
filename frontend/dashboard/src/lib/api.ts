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
  if (token()) return token();
  const res = await post<{ token?: string }>("/api/v2/auth/ws-token", {
    user_id: "frontend_user",
    scope: "read",
    expiry_hours: 1,
  });
  if (res && res.token) localStorage.setItem("jwt", res.token);
  return res?.token || "";
}

export async function getText(path: string): Promise<string> {
  const r = await fetch(`${BASE}${path}`, { headers: headers() });
  if (!r.ok) throw new Error(await r.text());
  return r.text();
}

const api = { get, post, getText, ensureToken, getApiBase };
export default api;
