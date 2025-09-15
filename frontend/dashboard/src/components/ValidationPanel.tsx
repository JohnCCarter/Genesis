import React from 'react';
import { post } from '@lib/api';
import { Sparkline } from './Sparkline';
import { JsonTree } from './JsonTree';

export function ValidationPanel() {
    const [symbol, setSymbol] = React.useState('tBTCUSD');
    const [timeframe, setTimeframe] = React.useState('1m');
    const [limit, setLimit] = React.useState(600);
    const [maxSamples, setMaxSamples] = React.useState(500);
    const [loading, setLoading] = React.useState(false);
    const [result, setResult] = React.useState<any>(null);
    const [error, setError] = React.useState<string | null>(null);

    async function run() {
        try {
            setLoading(true);
            setError(null);
            const res = await post('/api/v2/validation/probability', {
                symbol,
                timeframe,
                limit,
                max_samples: maxSamples,
                force_refresh: true,
            });
            setResult(res);
        } catch (e: any) {
            setError(e?.message || 'validate_failed');
        } finally {
            setLoading(false);
        }
    }

    // Härled simpla serier om resultatet innehåller rolling/series
    const brierSeries = React.useMemo(() => {
        const rolling = result?.rolling_metrics || result?.metrics?.rolling || {};
        // försök ta första nyckelns serie
        const series: any[] = Array.isArray(rolling) ? rolling : (Object.values(rolling)[0] as any[] || []);
        return (series || []).map((x: any) => Number(x?.brier || 0)).filter((n: number) => Number.isFinite(n));
    }, [result]);

    return (
        <div style={{ border: '1px solid #e1e4e8', borderRadius: 6, padding: 12 }}>
            {error && <div style={{ background: '#ffebe9', color: '#86181d', padding: 8, borderRadius: 4, marginBottom: 12 }}>{error}</div>}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, minmax(140px, 1fr))', gap: 8, alignItems: 'end' }}>
                <div>
                    <label>Symbol</label>
                    <input value={symbol} onChange={(e) => setSymbol(e.target.value)} style={{ width: '100%' }} />
                </div>
                <div>
                    <label>Timeframe</label>
                    <input value={timeframe} onChange={(e) => setTimeframe(e.target.value)} style={{ width: '100%' }} />
                </div>
                <div>
                    <label>Limit</label>
                    <input type="number" value={limit} onChange={(e) => setLimit(parseInt(e.target.value || '0', 10))} style={{ width: '100%' }} />
                </div>
                <div>
                    <label>Max samples</label>
                    <input type="number" value={maxSamples} onChange={(e) => setMaxSamples(parseInt(e.target.value || '0', 10))} style={{ width: '100%' }} />
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                    <button onClick={run} disabled={loading}>{loading ? 'Validating…' : 'Run validation'}</button>
                    <button onClick={() => setResult(null)} disabled={loading}>Clear</button>
                </div>
            </div>
            {result && (
                <div style={{ marginTop: 12 }}>
                    <div style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap', marginBottom: 8 }}>
                        <div>
                            <div style={{ fontSize: 12, color: '#555' }}>Brier (sparkline)</div>
                            <Sparkline data={brierSeries} width={220} height={42} color="#12B886" />
                        </div>
                        <div style={{ fontSize: 12, color: '#555' }}>
                            <div>p50: <b>{Number(result?.brier_p50 ?? result?.metrics?.p50 ?? 0).toFixed(4)}</b></div>
                            <div>p95: <b>{Number(result?.brier_p95 ?? result?.metrics?.p95 ?? 0).toFixed(4)}</b></div>
                            <div>p99: <b>{Number(result?.brier_p99 ?? result?.metrics?.p99 ?? 0).toFixed(4)}</b></div>
                        </div>
                    </div>
                    <div style={{ fontSize: 12, color: '#555', marginBottom: 8 }}>Result</div>
                    <JsonTree data={result} />
                </div>
            )}
        </div>
    );
}
