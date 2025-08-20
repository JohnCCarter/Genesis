import React from 'react';
import { get, post } from '../lib/api';

export function MarketPanel() {
    const [watchlist, setWatchlist] = React.useState<any[]>([]);
    const [symbols, setSymbols] = React.useState<string>('');
    const [prob, setProb] = React.useState<boolean>(false);
    const [error, setError] = React.useState<string | null>(null);
    const [settings, setSettings] = React.useState<any | null>(null);
    const [auto, setAuto] = React.useState<{ AUTO_REGIME_ENABLED?: boolean; AUTO_WEIGHTS_ENABLED?: boolean }>({});
    const [currentRegime, setCurrentRegime] = React.useState<any | null>(null);
    const [allRegimes, setAllRegimes] = React.useState<any[]>([]);
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
            if (st) {
                console.log('Settings från API:', st);
                setSettings(st);
            }
            if (au) setAuto(au);

            // Hämta aktuell regim om auto-regim är aktiverat
            if (au?.AUTO_REGIME_ENABLED && items.length > 0) {
                const firstSymbol = items[0]?.symbol || 'tBTCUSD';
                try {
                    const regimeRes = await get(`/api/v2/strategy/regime/${firstSymbol}`);
                    console.log('Regim response:', regimeRes);
                    setCurrentRegime(regimeRes);
                } catch (e) {
                    console.error('Regim error:', e);
                    setCurrentRegime(null);
                }
            }
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
                <button onClick={() => {
                    console.log('=== DEBUG: Watchlist ===');
                    console.log('Watchlist items:', watchlist);
                    console.log('Watchlist count:', watchlist?.length);
                    console.log('All symbols:', watchlist?.map((item: any) => item?.symbol));
                }}>Debug: Watchlist</button>
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
                                    // Uppdatera settings från regim om aktiverat
                                    if (v) {
                                        setTimeout(async () => {
                                            try {
                                                await post(`/api/v2/strategy/update-from-regime`);
                                            } catch { /* ignore */ }
                                            refresh();
                                        }, 500);
                                    } else {
                                        setTimeout(() => refresh(), 500);
                                    }
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
                                    // Uppdatera settings från regim om aktiverat
                                    if (v) {
                                        setTimeout(async () => {
                                            try {
                                                await post(`/api/v2/strategy/update-from-regime`);
                                            } catch { /* ignore */ }
                                            refresh();
                                        }, 500);
                                    } else {
                                        setTimeout(() => refresh(), 500);
                                    }
                                } catch { /* ignore */ }
                            }}
                        />{' '}Auto‑vikter
                    </label>
                    <button
                        type="button"
                        onClick={async () => {
                            try {
                                const result = await post(`/api/v2/strategy/update-from-regime`);
                                console.log('Auto-regim result:', result);
                                // Explicit refresh settings
                                const newSettings = await get(`/api/v2/strategy/settings`);
                                console.log('New settings after update:', newSettings);
                                setSettings(newSettings);
                                refresh();
                            } catch (e) {
                                console.error('Auto-regim error:', e);
                            }
                        }}
                        disabled={!(auto?.AUTO_REGIME_ENABLED && auto?.AUTO_WEIGHTS_ENABLED)}
                    >
                        Uppdatera från regim
                    </button>
                    <button
                        type="button"
                        onClick={async () => {
                            console.log('=== DEBUG: Refresh Settings ===');
                            console.log('Current settings state:', settings);
                            console.log('Current weightSum:', weightSum);
                            await refresh();
                            console.log('After refresh - settings:', settings);
                            console.log('After refresh - weightSum:', weightSum);
                        }}
                    >
                        Debug: Refresh Settings
                    </button>
                    <button
                        type="button"
                        onClick={async () => {
                            try {
                                const regimeRes = await get(`/api/v2/strategy/regime/tBTCUSD`);
                                console.log('Manual regim fetch:', regimeRes);
                                setCurrentRegime(regimeRes);
                            } catch (e) {
                                console.error('Manual regim error:', e);
                            }
                        }}
                    >
                        Debug: Fetch Regim
                    </button>
                </div>
                {/* Debug-info för auto-regim */}
                {(auto?.AUTO_REGIME_ENABLED || auto?.AUTO_WEIGHTS_ENABLED) && (
                    <div style={{ background: '#f6f8fa', padding: 8, borderRadius: 4, marginTop: 8, fontSize: '0.9em' }}>
                        <strong>Auto-status:</strong><br />
                        Regim: {auto?.AUTO_REGIME_ENABLED ? 'Aktiv' : 'Inaktiv'}<br />
                        Vikter: {auto?.AUTO_WEIGHTS_ENABLED ? 'Aktiva' : 'Inaktiva'}<br />
                        {currentRegime && <span>Aktuell regim: <strong>{currentRegime.regime || currentRegime}</strong><br /></span>}
                        <span>ADX: {currentRegime?.adx_value?.toFixed(1) || 'N/A'}<br /></span>
                        <span>EMA Z: {currentRegime?.ema_z_value?.toFixed(2) || 'N/A'}<br /></span>
                        Aktuella vikter: EMA={settings?.ema_weight?.toFixed(2) || '0.00'}, RSI={settings?.rsi_weight?.toFixed(2) || '0.00'}, ATR={settings?.atr_weight?.toFixed(2) || '0.00'}<br />
                        Vikt-summa: {weightSum.toFixed(2)} (ska vara ~1.0)<br />
                        <small>Settings timestamp: {new Date().toLocaleTimeString()}</small><br />
                        <small>Settings object: {JSON.stringify(settings)}</small>
                    </div>
                )}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginTop: 8 }}>
                    <div>
                        <label>EMA period</label>
                        <input
                            type="number"
                            value={settings?.ema_period ?? ''}
                            onChange={(e) => setSettings((s: any) => ({ ...(s || {}), ema_period: Number(e.target.value) }))}
                        />
                    </div>
                    <div>
                        <label>RSI period</label>
                        <input
                            type="number"
                            value={settings?.rsi_period ?? ''}
                            onChange={(e) => setSettings((s: any) => ({ ...(s || {}), rsi_period: Number(e.target.value) }))}
                        />
                    </div>
                    <div>
                        <label>ATR period</label>
                        <input
                            type="number"
                            value={settings?.atr_period ?? ''}
                            onChange={(e) => setSettings((s: any) => ({ ...(s || {}), atr_period: Number(e.target.value) }))}
                        />
                    </div>
                    <div>
                        <label>EMA weight</label>
                        <input
                            type="number" step="0.01"
                            value={settings?.ema_weight ?? ''}
                            onChange={(e) => setSettings((s: any) => ({ ...(s || {}), ema_weight: Number(e.target.value) }))}
                        />
                    </div>
                    <div>
                        <label>RSI weight</label>
                        <input
                            type="number" step="0.01"
                            value={settings?.rsi_weight ?? ''}
                            onChange={(e) => setSettings((s: any) => ({ ...(s || {}), rsi_weight: Number(e.target.value) }))}
                        />
                    </div>
                    <div>
                        <label>ATR weight</label>
                        <input
                            type="number" step="0.01"
                            value={settings?.atr_weight ?? ''}
                            onChange={(e) => setSettings((s: any) => ({ ...(s || {}), atr_weight: Number(e.target.value) }))}
                        />
                    </div>
                </div>
                <div style={{ display: 'flex', gap: 8, marginTop: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                    <span style={{ opacity: 0.8 }}>Sum(weights): {weightSum.toFixed(2)}</span>
                    <button type="button" onClick={async () => {
                        // Balanced preset: EMA=0.4, RSI=0.4, ATR=0.2 (sum=1.0)
                        const newSettings = { ...(settings || {}), ema_weight: 0.4, rsi_weight: 0.4, atr_weight: 0.2 };
                        setSettings(newSettings);
                        try {
                            await post(`/api/v2/strategy/settings`, newSettings);
                            console.log('Balanced preset sparat:', newSettings);
                        } catch (e) {
                            console.error('Kunde inte spara balanced preset:', e);
                        }
                    }}>Preset: Balanced</button>
                    <button type="button" onClick={async () => {
                        // Trend preset: EMA=0.5, RSI=0.1, ATR=0.4 (sum=1.0)
                        const newSettings = { ...(settings || {}), ema_weight: 0.5, rsi_weight: 0.1, atr_weight: 0.4 };
                        setSettings(newSettings);
                        try {
                            await post(`/api/v2/strategy/settings`, newSettings);
                            console.log('Trend preset sparat:', newSettings);
                        } catch (e) {
                            console.error('Kunde inte spara trend preset:', e);
                        }
                    }}>Preset: Trend</button>
                    <button type="button" onClick={async () => {
                        // Range preset: EMA=0.3, RSI=0.6, ATR=0.1 (sum=1.0)
                        const newSettings = { ...(settings || {}), ema_weight: 0.3, rsi_weight: 0.6, atr_weight: 0.1 };
                        setSettings(newSettings);
                        try {
                            await post(`/api/v2/strategy/settings`, newSettings);
                            console.log('Range preset sparat:', newSettings);
                        } catch (e) {
                            console.error('Kunde inte spara range preset:', e);
                        }
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
                    <button type="button" onClick={async () => {
                        console.log('=== DEBUG: Current Settings ===');
                        console.log('Settings state:', settings);
                        console.log('Weight sum:', weightSum);
                        console.log('Periods - EMA:', settings?.ema_period, 'RSI:', settings?.rsi_period, 'ATR:', settings?.atr_period);
                        try {
                            const backendSettings = await get(`/api/v2/strategy/settings`);
                            console.log('Backend settings:', backendSettings);
                            console.log('Backend periods - EMA:', backendSettings?.ema_period, 'RSI:', backendSettings?.rsi_period, 'ATR:', backendSettings?.atr_period);
                        } catch (e) {
                            console.error('Kunde inte hämta backend settings:', e);
                        }
                    }}>Debug: Check Settings</button>
                    <button type="button" onClick={async () => {
                        // Testa att ändra RSI period från 14 till 21
                        const newSettings = { ...(settings || {}), rsi_period: 21 };
                        setSettings(newSettings);
                        try {
                            await post(`/api/v2/strategy/settings`, newSettings);
                            console.log('RSI period ändrad till 21:', newSettings);
                            await refresh();
                        } catch (e) {
                            console.error('Kunde inte ändra RSI period:', e);
                        }
                    }}>Test: RSI 21</button>
                    <button type="button" onClick={async () => {
                        try {
                            console.log('=== HÄMTAR ALLA REGIMER ===');
                            const allRegimes = await get(`/api/v2/strategy/regime/all`);
                            console.log('Alla regimen:', allRegimes);

                            if (allRegimes?.regimes) {
                                setAllRegimes(allRegimes.regimes);
                                console.log('📊 REGIM-ÖVERSIKT:');
                                allRegimes.regimes.forEach((regime: any) => {
                                    console.log(`${regime.symbol}: ${regime.regime} (ADX: ${regime.adx_value?.toFixed(1) || 'N/A'}, EMA Z: ${regime.ema_z_value?.toFixed(2) || 'N/A'})`);
                                });

                                // Gruppera efter regim
                                const trendCount = allRegimes.regimes.filter((r: any) => r.regime === 'trend').length;
                                const balancedCount = allRegimes.regimes.filter((r: any) => r.regime === 'balanced').length;
                                const rangeCount = allRegimes.regimes.filter((r: any) => r.regime === 'range').length;

                                console.log(`📈 SAMMANFATTNING: Trend: ${trendCount}, Balanced: ${balancedCount}, Range: ${rangeCount}`);
                            }
                        } catch (e) {
                            console.error('Kunde inte hämta alla regimen:', e);
                        }
                    }}>Visa alla regimen</button>
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

            {/* Visa alla regimen */}
            {allRegimes.length > 0 && (
                <details style={{ marginTop: 12 }}>
                    <summary>📊 Alla Regimer ({allRegimes.length} symboler)</summary>
                    <div style={{ background: '#f6f8fa', padding: 8, borderRadius: 4, marginTop: 8 }}>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 8 }}>
                            {allRegimes.map((regime: any, i: number) => (
                                <div key={i} style={{
                                    background: 'white',
                                    padding: 12,
                                    borderRadius: 4,
                                    border: '1px solid #e1e4e8',
                                    fontSize: '0.9em'
                                }}>
                                    <strong>{regime.symbol}</strong><br />
                                    Regim: <span style={{
                                        color: regime.regime === 'trend' ? '#d73a49' :
                                            regime.regime === 'balanced' ? '#28a745' : '#6f42c1',
                                        fontWeight: 'bold'
                                    }}>{regime.regime}</span><br />

                                    {/* Confidence Score */}
                                    Säkerhet: <span style={{
                                        color: regime.confidence_score > 70 ? '#28a745' :
                                            regime.confidence_score > 50 ? '#f6a434' : '#d73a49',
                                        fontWeight: 'bold'
                                    }}>{regime.confidence_score}%</span><br />

                                    {/* Trading Probability */}
                                    Trading-chans: <span style={{
                                        color: regime.trading_probability > 60 ? '#28a745' :
                                            regime.trading_probability > 40 ? '#f6a434' : '#d73a49',
                                        fontWeight: 'bold'
                                    }}>{regime.trading_probability}%</span><br />

                                    {/* Recommendation */}
                                    Rekommendation: <span style={{
                                        color: regime.recommendation === 'STRONG_BUY' ? '#28a745' :
                                            regime.recommendation === 'BUY' ? '#2ea043' :
                                                regime.recommendation === 'WEAK_BUY' ? '#f6a434' :
                                                    regime.recommendation === 'HOLD' ? '#6f42c1' :
                                                        regime.recommendation === 'AVOID' ? '#d73a49' : '#6a737d',
                                        fontWeight: 'bold'
                                    }}>{regime.recommendation}</span><br />

                                    <small style={{ color: '#6a737d' }}>
                                        ADX: {regime.adx_value?.toFixed(1) || 'N/A'} |
                                        EMA Z: {regime.ema_z_value?.toFixed(2) || 'N/A'} |
                                        Pris: {regime.last_close?.toFixed(2) || 'N/A'}
                                    </small>
                                </div>
                            ))}
                        </div>

                        {/* Enhanced Summary */}
                        <div style={{ marginTop: 8, padding: 12, background: 'white', borderRadius: 4, border: '1px solid #e1e4e8' }}>
                            <strong>📈 Sammanfattning:</strong><br />
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 8, marginTop: 8 }}>
                                <div>
                                    <strong>Regimer:</strong><br />
                                    Trend: {allRegimes.filter((r: any) => r.regime === 'trend').length}<br />
                                    Balanced: {allRegimes.filter((r: any) => r.regime === 'balanced').length}<br />
                                    Range: {allRegimes.filter((r: any) => r.regime === 'range').length}
                                </div>
                                <div>
                                    <strong>Genomsnitt:</strong><br />
                                    Säkerhet: {(allRegimes.reduce((sum: number, r: any) => sum + (r.confidence_score || 0), 0) / allRegimes.length).toFixed(1)}%<br />
                                    Trading-chans: {(allRegimes.reduce((sum: number, r: any) => sum + (r.trading_probability || 0), 0) / allRegimes.length).toFixed(1)}%
                                </div>
                                <div>
                                    <strong>Rekommendationer:</strong><br />
                                    Köp: {allRegimes.filter((r: any) => r.recommendation?.includes('BUY')).length}<br />
                                    Håll: {allRegimes.filter((r: any) => r.recommendation === 'HOLD').length}<br />
                                    Undvik: {allRegimes.filter((r: any) => r.recommendation === 'AVOID').length}
                                </div>
                            </div>
                        </div>
                    </div>
                </details>
            )}
        </div >
    );
}


