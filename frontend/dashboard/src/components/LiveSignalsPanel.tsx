import React from 'react';
import { get, post } from '../lib/api';

type LiveSignal = {
    symbol: string;
    signal_type: string;
    confidence_score: number;
    trading_probability: number;
    recommendation?: string;
    strength?: string;
    timestamp?: string;
};

type LiveSignalsResponse = {
    timestamp: string;
    total_signals: number;
    active_signals: number;
    signals: LiveSignal[];
    summary?: Record<string, any>;
};

export function LiveSignalsPanel() {
    const [data, setData] = React.useState<LiveSignalsResponse | null>(null);
    const [loading, setLoading] = React.useState(false);
    const [auto, setAuto] = React.useState(true);

    const fetchSignals = React.useCallback(async () => {
        try {
            setLoading(true);
            const res = await get('/api/v2/signals/live');
            setData(res);
        } finally {
            setLoading(false);
        }
    }, []);

    const refreshSignals = React.useCallback(async () => {
        try {
            setLoading(true);
            const res = await post('/api/v2/signals/refresh', { force_refresh: true });
            setData(res);
        } finally {
            setLoading(false);
        }
    }, []);

    React.useEffect(() => {
        fetchSignals();
    }, [fetchSignals]);

    React.useEffect(() => {
        if (!auto) return;
        const id = window.setInterval(fetchSignals, 300000); // Öka till 5 minuter
        return () => window.clearInterval(id);
    }, [auto, fetchSignals]);

    return (
        <div style={{ border: '1px solid #e1e4e8', borderRadius: 6, padding: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h3 style={{ margin: 0 }}>Live Signals</h3>
                <div style={{ display: 'flex', gap: 8 }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} /> Auto refresh
                    </label>
                    <button onClick={fetchSignals} disabled={loading}>{loading ? 'Laddar…' : 'Uppdatera'}</button>
                    <button onClick={refreshSignals} disabled={loading}>{loading ? 'Genererar…' : 'Force refresh'}</button>
                </div>
            </div>
            <div style={{ marginTop: 10 }}>
                {data ? (
                    <>
                        <div style={{ marginBottom: 8, opacity: 0.8, fontSize: 12 }}>
                            <span>Senast: {new Date(data.timestamp).toLocaleString('sv-SE')}</span>
                            {data.summary ? (
                                <span style={{ marginLeft: 12 }}>
                                    Aktiva: {data.active_signals} / Totalt: {data.total_signals}
                                </span>
                            ) : null}
                        </div>
                        <div style={{ overflow: 'auto' }}>
                            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                                <thead>
                                    <tr>
                                        <th align="left">Symbol</th>
                                        <th align="left">Signal</th>
                                        <th align="left">Strength</th>
                                        <th align="right">Confidence %</th>
                                        <th align="right">Prob %</th>
                                        <th align="left">Recommendation</th>
                                        <th align="left">Tid</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {(data.signals || []).map((s, idx) => (
                                        <tr key={s.symbol + '-' + idx}>
                                            <td>{s.symbol}</td>
                                            <td style={{ textTransform: 'uppercase' }}>{s.signal_type}</td>
                                            <td>{s.strength || '-'}</td>
                                            <td align="right">{typeof s.confidence_score === 'number' ? s.confidence_score.toFixed(1) : '-'}</td>
                                            <td align="right">{typeof s.trading_probability === 'number' ? s.trading_probability.toFixed(1) : '-'}</td>
                                            <td>{s.recommendation || '-'}</td>
                                            <td>{s.timestamp ? new Date(s.timestamp).toLocaleTimeString('sv-SE') : '-'}</td>
                                        </tr>
                                    ))}
                                    {(!data.signals || data.signals.length === 0) && (
                                        <tr>
                                            <td colSpan={7} style={{ opacity: 0.7, padding: 8 }}>Inga signals</td>
                                        </tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </>
                ) : (
                    <div>Laddar…</div>
                )}
            </div>
        </div>
    );
}
