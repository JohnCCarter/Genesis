import React from 'react';
import { createRoot } from 'react-dom/client';
import { ensureToken, get, post } from './lib/api';

function Badge({ ok, label }: { ok: boolean; label: string }) {
    return (
        <span
            style={{
                display: 'inline-block',
                padding: '2px 8px',
                borderRadius: 999,
                fontSize: 12,
                color: '#fff',
                background: ok ? '#2ea44f' : '#d29922',
                marginRight: 8,
            }}
        >
            {label}
        </span>
    );
}

function App() {
    const [status, setStatus] = React.useState<any>(null);
    const [caps, setCaps] = React.useState<any>(null);
    const [loading, setLoading] = React.useState(false);

    const refresh = React.useCallback(async () => {
        await ensureToken();
        const s = await get('/api/v2/ws/pool/status');
        setStatus(s);
        try {
            const c = await get('/api/v2/ui/capabilities');
            setCaps(c);
        } catch { }
    }, []);

    React.useEffect(() => {
        refresh();
        const id = setInterval(refresh, 5000);
        return () => clearInterval(id);
    }, [refresh]);

    async function toggleWsStrategy(enabled: boolean) {
        try {
            setLoading(true);
            await post('/api/v2/mode/ws-strategy', { enabled });
            await refresh();
        } finally {
            setLoading(false);
        }
    }

    async function toggleValidation(enabled: boolean) {
        try {
            setLoading(true);
            await post('/api/v2/mode/validation-warmup', { enabled });
            await refresh();
        } finally {
            setLoading(false);
        }
    }

    return (
        <div style={{ fontFamily: 'system-ui, sans-serif', padding: 16 }}>
            <h2>Genesis Dashboard</h2>
            <div style={{ marginBottom: 12 }}>
                {status && (
                    <>
                        <Badge ok={!!status.main?.connected} label={status.main?.connected ? 'WS Connected' : 'WS Disc'} />
                        <Badge ok={!!status.main?.authenticated} label={status.main?.authenticated ? 'WS Auth' : 'No Auth'} />
                    </>
                )}
                {caps && (
                    <>
                        <Badge ok={!!caps.dry_run} label={caps.dry_run ? 'DRY_RUN' : 'LIVE'} />
                    </>
                )}
            </div>
            <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
                <button disabled={loading} onClick={() => toggleWsStrategy(true)}>
                    WS Strategy On
                </button>
                <button disabled={loading} onClick={() => toggleWsStrategy(false)}>
                    WS Strategy Off
                </button>
                <button disabled={loading} onClick={() => toggleValidation(true)}>
                    Validation On
                </button>
                <button disabled={loading} onClick={() => toggleValidation(false)}>
                    Validation Off
                </button>
            </div>
            <pre style={{ background: '#f6f8fa', padding: 12, borderRadius: 6 }}>
                {JSON.stringify({ status, caps }, null, 2)}
            </pre>
        </div>
    );
}

createRoot(document.getElementById('root')!).render(<App />);
