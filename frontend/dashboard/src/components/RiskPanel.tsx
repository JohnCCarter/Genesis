import { get, post } from '@lib/api';
import React from 'react';

type DayKey = 'mon' | 'tue' | 'wed' | 'thu' | 'fri' | 'sat' | 'sun';
const DAY_KEYS: DayKey[] = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];

type WindowsMap = Record<DayKey, [string, string][]>;

function emptyWindows(): WindowsMap {
    return {
        mon: [], tue: [], wed: [], thu: [], fri: [], sat: [], sun: [],
    };
}

export function RiskPanel() {
    const [status, setStatus] = React.useState<any>(null);
    const [windowsPayload, setWindowsPayload] = React.useState<any>(null);
    const [editTz, setEditTz] = React.useState<string>('Europe/Stockholm');
    const [editPaused, setEditPaused] = React.useState<boolean>(false);
    const [editWindows, setEditWindows] = React.useState<WindowsMap>(emptyWindows());
    const [loading, setLoading] = React.useState(false);
    const [saving, setSaving] = React.useState(false);
    const [error, setError] = React.useState<string | null>(null);
    const [maxPerDay, setMaxPerDay] = React.useState<number | ''>('');
    const [maxPerSymbol, setMaxPerSymbol] = React.useState<number | ''>('');
    const [cooldownSec, setCooldownSec] = React.useState<number | ''>('');

    const toWindowsMap = React.useCallback((raw: any): WindowsMap => {
        const out = emptyWindows();
        if (!raw || !raw.windows) return out;
        for (const k of DAY_KEYS) {
            const arr = Array.isArray(raw.windows[k]) ? raw.windows[k] : [];
            out[k] = arr.map((pair: any) => [String(pair[0] || ''), String(pair[1] || '')]);
        }
        return out;
    }, []);

    const refresh = React.useCallback(async () => {
        try {
            setError(null);
            const [s] = await Promise.all([
                get('/api/v2/risk/unified/status').catch(() => null),
            ]);
            if (s) setStatus(s);
            if (s && s.trading_window) {
                const w = s.trading_window;
                setWindowsPayload(w);
                setEditTz(w.timezone || 'Europe/Stockholm');
                setEditPaused(!!w.paused);
                setEditWindows(toWindowsMap(w));
                const lim = (w && w.limits) || {};
                setMaxPerDay(Number.isFinite(lim.max_trades_per_day) ? Number(lim.max_trades_per_day) : '');
                setMaxPerSymbol(Number.isFinite(lim.max_trades_per_symbol_per_day) ? Number(lim.max_trades_per_symbol_per_day) : '');
                setCooldownSec(Number.isFinite(lim.trade_cooldown_seconds) ? Number(lim.trade_cooldown_seconds) : '');
            }
        } catch (e: any) {
            setError(e?.message || 'Risk refresh misslyckades');
        }
    }, [toWindowsMap]);

    React.useEffect(() => {
        refresh();
        const id = setInterval(refresh, 120000); // Öka från 30s till 120s
        return () => clearInterval(id);
    }, [refresh]);

    async function pauseResume(pause: boolean) {
        try {
            setLoading(true);
            await post(pause ? '/api/v2/risk/unified/pause' : '/api/v2/risk/unified/resume');
            await refresh();
        } finally {
            setLoading(false);
        }
    }

    async function resetCircuit() {
        try {
            setLoading(true);
            await post('/api/v2/risk/unified/reset-circuit-breaker');
            await refresh();
        } finally {
            setLoading(false);
        }
    }

    function addInterval(day: DayKey) {
        setEditWindows((prev) => ({
            ...prev,
            [day]: [...prev[day], ['09:00', '17:00']],
        }));
    }

    function removeInterval(day: DayKey, idx: number) {
        setEditWindows((prev) => ({
            ...prev,
            [day]: prev[day].filter((_, i) => i !== idx),
        }));
    }

    function updateInterval(day: DayKey, idx: number, which: 0 | 1, val: string) {
        const v = val.slice(0, 5);
        setEditWindows((prev) => {
            const arr = prev[day].slice();
            const pair = arr[idx] ? [...arr[idx]] as [string, string] : ['00:00', '00:00'];
            pair[which] = v;
            arr[idx] = pair as [string, string];
            return { ...prev, [day]: arr };
        });
    }

    function validTime(s: string) {
        return /^\d{2}:\d{2}$/.test(s);
    }

    function normalizeTimeString(s: string): string {
        const m = s.match(/^(\d{1,2}):(\d{1,2})$/);
        if (!m) return s;
        const h = Math.min(23, Math.max(0, parseInt(m[1], 10)));
        const mm = Math.min(59, Math.max(0, parseInt(m[2], 10)));
        return `${String(h).padStart(2, '0')}:${String(mm).padStart(2, '0')}`;
    }

    async function saveWindows() {
        try {
            setSaving(true);
            // Bygg payload i rätt format
            const windowsPayload: Record<DayKey, [string, string][]> = {
                mon: editWindows.mon,
                tue: editWindows.tue,
                wed: editWindows.wed,
                thu: editWindows.thu,
                fri: editWindows.fri,
                sat: editWindows.sat,
                sun: editWindows.sun,
            };
            // Enkel validering
            for (const k of DAY_KEYS) {
                for (const [a, b] of windowsPayload[k]) {
                    if (!validTime(a) || !validTime(b)) throw new Error(`Ogiltig tid i ${k.toUpperCase()}: ${a}-${b}`);
                }
            }
            await post('/api/v2/risk/unified/windows/update', {
                timezone: editTz,
                windows: windowsPayload,
                paused: editPaused,
                max_trades_per_day: maxPerDay === '' ? undefined : Number(maxPerDay),
                max_trades_per_symbol_per_day: maxPerSymbol === '' ? undefined : Number(maxPerSymbol),
                trade_cooldown_seconds: cooldownSec === '' ? undefined : Number(cooldownSec),
            });
            await refresh();
        } catch (e: any) {
            setError(e?.message || 'Kunde inte spara trading window');
        } finally {
            setSaving(false);
        }
    }

    const open = !!status?.open;
    const paused = !!status?.paused;

    return (
        <div style={{ border: '1px solid #e1e4e8', borderRadius: 6, padding: 12 }}>
            <h3 style={{ margin: '0 0 8px' }}>Risk & Guardrails</h3>
            {error && (
                <div style={{ background: '#ffebe9', color: '#86181d', padding: 8, borderRadius: 4, marginBottom: 12 }}>
                    {error}
                </div>
            )}

            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
                <span style={{ padding: '2px 8px', borderRadius: 12, background: paused ? '#ffdada' : '#d7f5dd', color: paused ? '#8a1c1c' : '#166534' }}>
                    {paused ? 'Paused' : (open ? 'Open' : 'Closed')}
                </span>
                <button disabled={loading} onClick={() => pauseResume(true)}>Pause</button>
                <button disabled={loading} onClick={() => pauseResume(false)}>Resume</button>
                <button disabled={loading} onClick={resetCircuit}>Circuit Reset</button>
            </div>

            <div style={{ borderTop: '1px solid #eaecef', paddingTop: 12, marginTop: 8 }}>
                <h4 style={{ margin: '0 0 8px' }}>Trading Window</h4>
                <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 8, flexWrap: 'wrap' }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span>Tidszon</span>
                        <input value={editTz} onChange={(e) => setEditTz(e.target.value)} style={{ padding: 6 }} />
                    </label>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <input type="checkbox" checked={editPaused} onChange={(e) => setEditPaused(e.target.checked)} />
                        <span>Paused</span>
                    </label>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span>Max/dag</span>
                        <input type="number" min={0} value={maxPerDay} onChange={(e) => setMaxPerDay(e.target.value === '' ? '' : Number(e.target.value))} style={{ width: 100 }} />
                    </label>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span>Max/symbol/dag</span>
                        <input type="number" min={0} value={maxPerSymbol} onChange={(e) => setMaxPerSymbol(e.target.value === '' ? '' : Number(e.target.value))} style={{ width: 120 }} />
                    </label>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span>Cooldown (s)</span>
                        <input type="number" min={0} value={cooldownSec} onChange={(e) => setCooldownSec(e.target.value === '' ? '' : Number(e.target.value))} style={{ width: 120 }} />
                    </label>
                    <button disabled={saving} onClick={saveWindows}>Spara</button>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: 8 }}>
                    {DAY_KEYS.map((day) => (
                        <React.Fragment key={day}>
                            <div style={{ fontWeight: 600, textTransform: 'uppercase', paddingTop: 6 }}>{day}</div>
                            <div>
                                {editWindows[day].length === 0 && (
                                    <div style={{ color: '#6a737d', fontStyle: 'italic' }}>Inga intervall</div>
                                )}
                                {editWindows[day].map((pair, idx) => (
                                    <div key={idx} style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6 }}>
                                        <input
                                            type="text"
                                            inputMode="numeric"
                                            lang="sv-SE"
                                            placeholder="HH:MM"
                                            pattern="^([01]\\d|2[0-3]):[0-5]\\d$"
                                            title="Ange tid i 24-timmarsformat HH:MM"
                                            value={pair[0]}
                                            onChange={(e) => updateInterval(day, idx, 0, e.target.value)}
                                            onBlur={(e) => updateInterval(day, idx, 0, normalizeTimeString(e.target.value))}
                                        />
                                        <span>–</span>
                                        <input
                                            type="text"
                                            inputMode="numeric"
                                            lang="sv-SE"
                                            placeholder="HH:MM"
                                            pattern="^([01]\\d|2[0-3]):[0-5]\\d$"
                                            title="Ange tid i 24-timmarsformat HH:MM"
                                            value={pair[1]}
                                            onChange={(e) => updateInterval(day, idx, 1, e.target.value)}
                                            onBlur={(e) => updateInterval(day, idx, 1, normalizeTimeString(e.target.value))}
                                        />
                                        <button onClick={() => removeInterval(day, idx)}>
                                            Ta bort
                                        </button>
                                    </div>
                                ))}
                                <button onClick={() => addInterval(day)}>+ Lägg till intervall</button>
                            </div>
                        </React.Fragment>
                    ))}
                </div>
            </div>

            <details style={{ marginTop: 12 }}>
                <summary>Debug</summary>
                <pre style={{ background: '#f6f8fa', padding: 12, borderRadius: 6 }}>
                    {JSON.stringify({ status, windows: windowsPayload, edit: { timezone: editTz, paused: editPaused, windows: editWindows } }, null, 2)}
                </pre>
            </details>
        </div>
    );
}
