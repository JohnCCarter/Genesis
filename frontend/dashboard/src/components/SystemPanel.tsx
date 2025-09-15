import { ensureToken, get, getApiBase, post } from '@lib/api';
import React from 'react';
import { io } from 'socket.io-client';

export function SystemPanel() {
    const [health, setHealth] = React.useState<any>(null);
    const [error, setError] = React.useState<string | null>(null);
    const [wsLog, setWsLog] = React.useState<string>('');
    const [wsStatus, setWsStatus] = React.useState<string>('disconnected');
    const [subs, setSubs] = React.useState<string[]>([]);
    const [restUrl, setRestUrl] = React.useState<string>('/health');
    const [sym, setSym] = React.useState<string>('tBTCUSD');
    const [chan, setChan] = React.useState<string>('ticker');
    const [tf, setTf] = React.useState<string>('1m');
    const socketRef = React.useRef<any>(null);
    const WS_BASE = getApiBase();

    const refresh = React.useCallback(async () => {
        try {
            setError(null);
            const h = await get('/health');
            setHealth(h);
        } catch (e: any) {
            setError(e?.message || 'Kunde inte hämta health');
        }
    }, []);

    const refreshSubs = React.useCallback(async () => {
        try {
            const s = await get('/api/v2/ws/pool/status');
            const arr = (s && s.subscriptions) || [];
            setSubs(Array.isArray(arr) ? arr : []);
        } catch (e) {
            setSubs([]);
        }
    }, []);

    React.useEffect(() => {
        refresh();
        refreshSubs();
        const id = setInterval(refresh, 120000); // Öka från 60s till 120s för bättre prestanda
        const id2 = setInterval(refreshSubs, 120000); // Öka från 60s till 120s för bättre prestanda
        return () => {
            clearInterval(id);
            clearInterval(id2);
        };
    }, [refresh, refreshSubs]);

    const [metricsSummary, setMetricsSummary] = React.useState<any | null>(null);
    async function loadMetrics() {
        try {
            setError(null);
            const js = await get('/api/v2/metrics/summary');
            setMetricsSummary(js);
        } catch (e: any) {
            setError(e?.message || 'Kunde inte hämta metrics summary');
        }
    }

    return (
        <div style={{ border: '1px solid #e1e4e8', borderRadius: 6, padding: 12 }}>
            <h3 style={{ margin: '0 0 8px' }}>System</h3>
            <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
                <button onClick={refresh}>Uppdatera Health</button>
                <button onClick={loadMetrics}>Hämta Metrics</button>
            </div>
            {error && (
                <div style={{ background: '#ffebe9', color: '#86181d', padding: 8, borderRadius: 4, marginBottom: 12 }}>
                    {error}
                </div>
            )}
            <pre style={{ background: '#f6f8fa', padding: 12, borderRadius: 6 }}>
                {JSON.stringify(health, null, 2)}
            </pre>
            {metricsSummary && (
                <details style={{ marginTop: 12 }}>
                    <summary>Metrics Summary (JSON)</summary>
                    <pre style={{ background: '#0b1021', color: '#d6deeb', padding: 12, borderRadius: 6, overflow: 'auto', maxHeight: 300 }}>
                        {JSON.stringify(metricsSummary, null, 2)}
                    </pre>
                </details>
            )}

            <div style={{ borderTop: '1px solid #eaecef', marginTop: 12, paddingTop: 12 }}>
                <h4 style={{ margin: '0 0 8px' }}>Debug</h4>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginBottom: 8 }}>
                    <span style={{ padding: '2px 8px', borderRadius: 12, background: wsStatus === 'connected' ? '#d7f5dd' : '#ffdada' }}>{wsStatus}</span>
                    <button onClick={async () => {
                        if (socketRef.current) return;
                        try {
                            await ensureToken();
                        } catch { }
                        const tk = localStorage.getItem('jwt') || localStorage.getItem('genesis_access_token');
                        const base = String(WS_BASE);
                        const url = tk ? `${base}${base.includes('?') ? '&' : '?'}token=${encodeURIComponent(tk)}` : base;
                        const s = io(url, { path: '/ws/socket.io' });
                        socketRef.current = s;
                        s.on('connect', () => { setWsStatus('connected'); setWsLog((v) => v + `\n[${new Date().toISOString()}] connected`); });
                        s.on('disconnect', () => { setWsStatus('disconnected'); setWsLog((v) => v + `\n[${new Date().toISOString()}] disconnected`); socketRef.current = null; });
                        s.on('message', (m: any) => setWsLog((v) => v + `\n[${new Date().toISOString()}] message ${JSON.stringify(m)}`));
                    }}>Connect</button>
                    <button onClick={() => { if (socketRef.current) socketRef.current.close(); }}>Disconnect</button>
                </div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginBottom: 8 }}>
                    <select value={chan} onChange={(e) => setChan(e.target.value)}>
                        <option value="ticker">ticker</option>
                        <option value="trades">trades</option>
                        <option value="candles">candles</option>
                    </select>
                    <input placeholder="1m (candles)" value={tf} onChange={(e) => setTf(e.target.value)} style={{ width: 120 }} />
                    <input placeholder="tBTCUSD" value={sym} onChange={(e) => setSym(e.target.value)} style={{ width: 160 }} />
                    <button onClick={async () => {
                        try {
                            const body: any = { channel: chan, symbol: sym };
                            if (chan === 'candles' && tf.trim()) body.timeframe = tf.trim();
                            await post('/api/v2/ws/subscribe', body);
                            await refreshSubs();
                        } catch (e: any) {
                            setWsLog((v) => v + `\nERR ${e?.message || String(e)}`);
                        }
                    }}>Subscribe</button>
                    <button onClick={async () => {
                        try {
                            const body: any = { channel: chan, symbol: sym };
                            if (chan === 'candles' && tf.trim()) body.timeframe = tf.trim();
                            await post('/api/v2/ws/unsubscribe', body);
                            await refreshSubs();
                        } catch (e: any) {
                            setWsLog((v) => v + `\nERR ${e?.message || String(e)}`);
                        }
                    }}>Unsubscribe</button>
                    <button onClick={async () => { await refreshSubs(); }}>Refresh Subs</button>
                </div>
                <div style={{ marginBottom: 8 }}>
                    <strong>Active Subs</strong>
                    <pre style={{ background: '#f6f8fa', padding: 8, borderRadius: 6 }}>{subs.join('\n') || '-'}</pre>
                </div>
                <div style={{ marginBottom: 8 }}>
                    <strong>WS Log</strong>
                    <pre style={{ background: '#0b1021', color: '#d6deeb', padding: 8, borderRadius: 6, maxHeight: 200, overflow: 'auto' }}>{wsLog}</pre>
                </div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <input value={restUrl} onChange={(e) => setRestUrl(e.target.value)} style={{ flex: 1 }} />
                    <button onClick={async () => {
                        try {
                            const r = await fetch(restUrl);
                            const txt = await r.text();
                            setWsLog((v) => v + `\nREST ${restUrl}\n${txt}`);
                        } catch (e: any) {
                            setWsLog((v) => v + `\nERR ${e?.message || String(e)}`);
                        }
                    }}>REST Call</button>
                </div>
            </div>
        </div>
    );
}
