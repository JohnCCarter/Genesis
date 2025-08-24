import React from 'react';
import { post } from '../lib/api';

export function ValidationPanel() {
    const [symbol, setSymbol] = React.useState('tTESTBTC:TESTUSD');
    const [timeframe, setTimeframe] = React.useState('1m');
    const [limit, setLimit] = React.useState(100);
    const [maxSamples, setMaxSamples] = React.useState(200);
    const [loading, setLoading] = React.useState(false);
    const [result, setResult] = React.useState<any>(null);
    const [error, setError] = React.useState<string | null>(null);

    async function run() {
        try {
            setLoading(true);
            setError(null);
            const res = await post('/api/v2/prob/validate/run', {
                symbol,
                timeframe,
                limit,
                max_samples: maxSamples,
            });
            setResult(res);
        } catch (e: any) {
            setError(e?.message || 'validate_failed');
        } finally {
            setLoading(false);
        }
    }

    return (
        <div style={{ border: '1px solid #e1e4e8', borderRadius: 6, padding: 12 }}>
            {error && <div style={{ background: '#ffebe9', color: '#86181d', padding: 8, borderRadius: 4, marginBottom: 12 }}>{error}</div>}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(140px, 1fr))', gap: 8, alignItems: 'end' }}>
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
            </div>
            <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                <button onClick={run} disabled={loading}>{loading ? 'Validating…' : 'Run validation'}</button>
            </div>
            {result && (
                <pre style={{ background: '#f6f8fa', padding: 8, borderRadius: 6, marginTop: 12 }}>{JSON.stringify(result, null, 2)}</pre>
            )}
        </div>
    );
}


