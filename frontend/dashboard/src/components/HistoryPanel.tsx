import React from 'react';
import { get } from '../lib/api';

export function HistoryPanel() {
    const [trades, setTrades] = React.useState<any[]>([]);
    const [ledgers, setLedgers] = React.useState<any[]>([]);
    const [equity, setEquity] = React.useState<any>(null);
    const [equityHist, setEquityHist] = React.useState<any[]>([]);
    const [loading, setLoading] = React.useState(false);
    const [error, setError] = React.useState<string | null>(null);

    const refresh = React.useCallback(async () => {
        try {
            setLoading(true);
            setError(null);
            const [t, l, e, eh] = await Promise.all([
                get('/api/v2/trades/history?limit=25').catch(() => []),
                get('/api/v2/ledgers?limit=25').catch(() => []),
                get('/api/v2/account/performance').catch(() => null),
                get('/api/v2/account/equity/history?limit=100').catch(() => ({ equity: [] })),
            ]);
            setTrades(Array.isArray(t) ? t : []);
            setLedgers(Array.isArray(l) ? l : []);
            setEquity(e);
            setEquityHist(Array.isArray(eh?.equity) ? eh.equity : []);
        } catch (e: any) {
            setError(e?.message || 'Kunde inte hämta historik');
        } finally {
            setLoading(false);
        }
    }, []);

    React.useEffect(() => {
        refresh();
    }, [refresh]);

    return (
        <div style={{ border: '1px solid #e1e4e8', borderRadius: 6, padding: 12 }}>
            <h3 style={{ margin: '0 0 8px' }}>Historik</h3>
            {error && (
                <div style={{ background: '#ffebe9', color: '#86181d', padding: 8, borderRadius: 4, marginBottom: 12 }}>
                    {error}
                </div>
            )}
            {loading ? (
                <div>Laddar…</div>
            ) : (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                    <div>
                        <h4>Trades (senaste)</h4>
                        <pre style={{ background: '#f6f8fa', padding: 8, borderRadius: 6 }}>
                            {JSON.stringify(trades, null, 2)}
                        </pre>
                    </div>
                    <div>
                        <h4>Ledgers (senaste)</h4>
                        <pre style={{ background: '#f6f8fa', padding: 8, borderRadius: 6 }}>
                            {JSON.stringify(ledgers, null, 2)}
                        </pre>
                    </div>
                    <div>
                        <h4>Performance (equity + realized)</h4>
                        <pre style={{ background: '#f6f8fa', padding: 8, borderRadius: 6 }}>
                            {JSON.stringify(equity, null, 2)}
                        </pre>
                    </div>
                    <div>
                        <h4>Equity History (senaste)</h4>
                        <pre style={{ background: '#f6f8fa', padding: 8, borderRadius: 6, maxHeight: 240, overflow: 'auto' }}>
                            {JSON.stringify(equityHist, null, 2)}
                        </pre>
                    </div>
                </div>
            )}
        </div>
    );
}


