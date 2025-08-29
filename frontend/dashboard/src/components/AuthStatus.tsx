import React from 'react';
import { ensureToken } from '../lib/api';

type Status = {
  state: 'none' | 'valid' | 'expired' | 'soon';
  minutesLeft?: number;
  exp?: number;
  iat?: number;
};

function readToken(): string | null {
  try {
    const t = localStorage.getItem('jwt');
    return t && t.length > 0 ? t : null;
  } catch {
    return null;
  }
}

function decodeJwt(token: string): { exp?: number; iat?: number; sub?: string } | null {
  try {
    const parts = token.split('.');
    if (parts.length < 2) return null;
    const b64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const padded = b64 + '==='.slice((b64.length + 3) % 4);
    const json = atob(padded);
    return JSON.parse(json);
  } catch {
    return null;
  }
}

function computeStatus(): Status {
  const tok = readToken();
  if (!tok) return { state: 'none' };
  const payload = decodeJwt(tok);
  if (!payload?.exp) return { state: 'none' };
  const now = Math.floor(Date.now() / 1000);
  const secondsLeft = payload.exp - now;
  if (secondsLeft <= 0) return { state: 'expired', exp: payload.exp, iat: payload.iat };
  const minutesLeft = Math.floor(secondsLeft / 60);
  if (secondsLeft <= 180) return { state: 'soon', minutesLeft, exp: payload.exp, iat: payload.iat };
  return { state: 'valid', minutesLeft, exp: payload.exp, iat: payload.iat };
}

export function AuthStatus() {
  const [status, setStatus] = React.useState<Status>(() => computeStatus());
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => {
    const id = window.setInterval(() => setStatus(computeStatus()), 30_000);
    return () => window.clearInterval(id);
  }, []);

  const renew = React.useCallback(async () => {
    try {
      setBusy(true);
      await ensureToken();
      setStatus(computeStatus());
    } catch {
      // ignore
    } finally {
      setBusy(false);
    }
  }, []);

  let bg = '#868E96';
  let label = 'AUTH: NONE';
  if (status.state === 'valid') {
    bg = '#228BE6';
    label = `AUTH: VALID${status.minutesLeft !== undefined ? ` · ${status.minutesLeft}m` : ''}`;
  } else if (status.state === 'soon') {
    bg = '#FAB005';
    label = `AUTH: EXPIRES SOON${status.minutesLeft !== undefined ? ` · ${status.minutesLeft}m` : ''}`;
  } else if (status.state === 'expired') {
    bg = '#F03E3E';
    label = 'AUTH: EXPIRED';
  }

  const showRenew = status.state !== 'valid' || (status.minutesLeft !== undefined && status.minutesLeft <= 3);

  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
      <span
        title={label}
        style={{
          display: 'inline-block',
          padding: '4px 10px',
          borderRadius: 999,
          background: bg,
          color: '#fff',
          fontSize: 12,
          fontWeight: 600,
        }}
      >
        {label}
      </span>
      {showRenew && (
        <button
          onClick={renew}
          disabled={busy}
          style={{
            fontSize: 12,
            padding: '4px 8px',
            borderRadius: 6,
            border: '1px solid #ccc',
            background: busy ? '#f3f3f3' : '#fff',
            cursor: busy ? 'not-allowed' : 'pointer',
          }}
        >
          {busy ? 'Renewing…' : 'Renew token'}
        </button>
      )}
    </div>
  );
}
