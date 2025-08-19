import React from 'react';
import { get, post } from '../lib/api';

export function MarketPanel() {
    const [watchlist, setWatchlist] = React.useState<any[]>([]);
    const [symbols, setSymbols] = React.useState<string>('');
    const [prob, setProb] = React.useState<boolean>(false);
    const [error, setError] = React.useState<string | null>(null);
    const [settings, setSettings] = React.useState<any | null>(null);
    const [auto, setAuto] = React.useState<{ AUTO_REGIME_ENABLED?: boolean; AUTO_WEIGHTS_ENABLED?: boolean }>({});
    const weightSum = React.useMemo(() => {
        const ew = Number(settings?.ema_weight ?? 0) || 0;
        const rw = Number(settings?.rsi_weight ?? 0) || 0;
        const aw = Number(settings?.atr_weight ?? 0) || 0;
        return ew + rw + aw;
    }, [settings]);
    const [saveMsg, setSaveMsg] = React.useState<string | null>(null);
    const [saveBusy, setSaveBusy] = React.useState(false);

    const refresh = React.useCallback(async () => {
        try {
            setError(null);
            const qs = new URLSearchParams();
            if (symbols.trim()) qs.set('symbols', symbols.trim());
            if (prob) qs.set('prob', 'true');
            const [res, st, au] = await Promise.all([
                get(`/api/v2/market/watchlist${qs.toString() ? `?${qs}` : ''}`),
                get(`/api/v2/strategy/settings`).catch(() => null),
                get(`/api/v2/strategy/auto`).catch(() => null),
            ]);
            const items = Array.isArray(res) ? res : (Array.isArray(res?.items) ? res.items : []);
            setWatchlist(items);
            if (st) setSettings(st);
            if (au) setAuto(au);
        } catch (e: any) {
            setError(e?.message || 'Kunde inte hämta watchlist');
        }
    }, [symbols, prob]);

    React.useEffect(() => {
        refresh();
        const id = setInterval(refresh, 15000);
        return () => clearInterval(id);
    }, [refresh]);

    return (
        <div style={{ border: '1px solid #e1e4e8', borderRadius: 6, padding: 12 }}>
            <h3 style={{ margin: '0 0 8px' }}>Market / Watchlist</h3>
            <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
                <input
                    placeholder="symbols (komma-separerat, t.ex. tBTCUSD,tETHUSD)"
                    value={symbols}
                    onChange={(e) => setSymbols(e.target.value)}
                    style={{ flex: 1 }}
                />
                <label>
                    <input type="checkbox" checked={prob} onChange={(e) => setProb(e.target.checked)} /> Visa prob
                </label>
                <button onClick={refresh}>Uppdatera</button>
            </div>
            <details style={{ marginBottom: 12 }}>
                <summary>Strategy / Indicators</summary>
                <div style={{ display: 'flex', gap: 12, marginTop: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                    <label>
                        <input
                            type="checkbox"
                            checked={!!auto?.AUTO_REGIME_ENABLED}
                            onChange={async (e) => {
                                const v = e.target.checked;
                                try {
                                    await post(`/api/v2/strategy/auto`, { AUTO_REGIME_ENABLED: v });
                                    setAuto((a) => ({ ...(a || {}), AUTO_REGIME_ENABLED: v }));
                                } catch { /* ignore */ }
                            }}
                        />{' '}Auto‑regim
                    </label>
                    <label>
                        <input
                            type="checkbox"
                            checked={!!auto?.AUTO_WEIGHTS_ENABLED}
                            onChange={async (e) => {
                                const v = e.target.checked;
                                try {
                                    await post(`/api/v2/strategy/auto`, { AUTO_WEIGHTS_ENABLED: v });
                                    setAuto((a) => ({ ...(a || {}), AUTO_WEIGHTS_ENABLED: v }));
                                } catch { /* ignore */ }
                            }}
                        />{' '}Auto‑vikter
                    </label>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginTop: 8 }}>
                    <div>
                        <label>EMA period</label>
                        <input
                            type="number"
                            defaultValue={settings?.ema_period ?? ''}
                            onChange={(e) => setSettings((s: any) => ({ ...(s || {}), ema_period: Number(e.target.value) }))}
                        />
                    </div>
                    <div>
                        <label>RSI period</label>
                        <input
                            type="number"
                            defaultValue={settings?.rsi_period ?? ''}
                            onChange={(e) => setSettings((s: any) => ({ ...(s || {}), rsi_period: Number(e.target.value) }))}
                        />
                    </div>
                    <div>
                        <label>ATR period</label>
                        <input
                            type="number"
                            defaultValue={settings?.atr_period ?? ''}
                            onChange={(e) => setSettings((s: any) => ({ ...(s || {}), atr_period: Number(e.target.value) }))}
                        />
                    </div>
                    <div>
                        <label>EMA weight</label>
                        <input
                            type="number" step="0.01"
                            defaultValue={settings?.ema_weight ?? ''}
                            onChange={(e) => setSettings((s: any) => ({ ...(s || {}), ema_weight: Number(e.target.value) }))}
                        />
                    </div>
                    <div>
                        <label>RSI weight</label>
                        <input
                            type="number" step="0.01"
                            defaultValue={settings?.rsi_weight ?? ''}
                            onChange={(e) => setSettings((s: any) => ({ ...(s || {}), rsi_weight: Number(e.target.value) }))}
                        />
                    </div>
                    <div>
                        <label>ATR weight</label>
                        <input
                            type="number" step="0.01"
                            defaultValue={settings?.atr_weight ?? ''}
                            onChange={(e) => setSettings((s: any) => ({ ...(s || {}), atr_weight: Number(e.target.value) }))}
                        />
                    </div>
                </div>
                <div style={{ display: 'flex', gap: 8, marginTop: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                    <span style={{ opacity: 0.8 }}>Sum(weights): {weightSum.toFixed(2)}</span>
                    <button type="button" onClick={() => {
                        setSettings((s: any) => ({ ...(s || {}), ema_weight: 0.4, rsi_weight: 0.3, atr_weight: 0.3 }));
                    }}>Preset: Balanced</button>
                    <button type="button" onClick={() => {
                        setSettings((s: any) => ({ ...(s || {}), ema_weight: 0.6, rsi_weight: 0.2, atr_weight: 0.2 }));
                    }}>Preset: Trend</button>
                    <button type="button" onClick={() => {
                        setSettings((s: any) => ({ ...(s || {}), ema_weight: 0.2, rsi_weight: 0.6, atr_weight: 0.2 }));
                    }}>Preset: Range</button>
                    <button type="button" onClick={() => {
                        setSettings((s: any) => ({ ...(s || {}), ema_weight: 1 / 3, rsi_weight: 1 / 3, atr_weight: 1 / 3 }));
                    }}>Equalize</button>
                    <button type="button" onClick={() => {
                        const ew = Number(settings?.ema_weight ?? 0) || 0;
                        const rw = Number(settings?.rsi_weight ?? 0) || 0;
                        const aw = Number(settings?.atr_weight ?? 0) || 0;
                        const sum = ew + rw + aw;
                        if (sum > 0) {
                            setSettings((s: any) => ({ ...(s || {}), ema_weight: ew / sum, rsi_weight: rw / sum, atr_weight: aw / sum }));
                        }
                    }}>Normalize</button>
                </div>
                <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                    <button disabled={saveBusy} onClick={async () => {
                        try {
                            setSaveBusy(true); setSaveMsg(null);
                            const payload: any = {};
                            for (const k of ['ema_period', 'rsi_period', 'atr_period', 'ema_weight', 'rsi_weight', 'atr_weight']) {
                                if (settings && settings[k] !== undefined && settings[k] !== null && settings[k] !== '') payload[k] = settings[k];
                            }
                            const base = (import.meta as any).env?.VITE_API_BASE || 'http://127.0.0.1:8000';
                            const res = await fetch(`${base}/api/v2/strategy/settings`, {
                                method: 'POST', headers: { 'Content-Type': 'application/json', ...(localStorage.getItem('jwt') ? { 'Authorization': `Bearer ${localStorage.getItem('jwt')}` } : {}) },
                                body: JSON.stringify(payload),
                            });
                            if (!res.ok) throw new Error(await res.text());
                            setSaveMsg('Sparat');
                            await refresh();
                        } catch (e: any) {
                            setSaveMsg(e?.message || 'Misslyckades');
                        } finally {
                            setSaveBusy(false);
                        }
                    }}>Spara</button>
                    {saveMsg && <span style={{ opacity: 0.8 }}>{saveMsg}</span>}
                </div>
            </details>
            {error && (
                <div style={{ background: '#ffebe9', color: '#86181d', padding: 8, borderRadius: 4, marginBottom: 12 }}>
                    {error}
                </div>
            )}
            <div style={{ overflow: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                        <tr>
                            <th align="left">Symbol</th>
                            <th align="left">Last</th>
                            <th align="left">Volume</th>
                            <th align="left">Signal</th>
                        </tr>
                    </thead>
                    <tbody>
                        {watchlist?.length ? (
                            watchlist.map((it: any, i: number) => (
                                <tr key={i}>
                                    <td>{it?.symbol}</td>
                                    <td>{it?.last ?? it?.last_price ?? '-'}</td>
                                    <td>{it?.volume ?? '-'}</td>
                                    <td>{it?.strategy?.signal || it?.prob?.decision || '-'}</td>
                                </tr>
                            ))
                        ) : (
                            <tr>
                                <td colSpan={4} style={{ opacity: 0.7, padding: 8 }}>Tomt</td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div >
    );
}


