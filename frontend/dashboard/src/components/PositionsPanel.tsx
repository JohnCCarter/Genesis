import React from 'react';
import { get, post } from '@lib/api';
import { TEST_SYMBOLS } from '@lib/testSymbols';

type Position = any;

export function PositionsPanel() {
    const [positions, setPositions] = React.useState<Position[]>([]);
    const [loading, setLoading] = React.useState(false);
    const [error, setError] = React.useState<string | null>(null);
    const [filterSymbol, setFilterSymbol] = React.useState<string>('');

    const refresh = React.useCallback(async () => {
        try {
            setLoading(true);
            setError(null);
            const res = await get('/api/v2/positions');
            setPositions(Array.isArray(res) ? res : []);
        } catch (e: any) {
            setError(e?.message || 'Kunde inte hämta positioner');
        } finally {
            setLoading(false);
        }
    }, []);

    React.useEffect(() => {
        refresh();
        const id = setInterval(refresh, 90000);
        return () => clearInterval(id);
    }, [refresh]);

    async function closePosition(symbol: string) {
        try {
            await post(`/api/v2/positions/close/${encodeURIComponent(symbol)}`, {});
            await refresh();
        } catch { }
    }

    const shown = React.useMemo(() => {
        if (!filterSymbol) return positions;
        return positions.filter((p: any) => String(p?.symbol || '').toUpperCase() === filterSymbol.toUpperCase());
    }, [positions, filterSymbol]);

    return (
        <div style={{ border: '1px solid #e1e4e8', borderRadius: 6, padding: 12 }}>
            <h3 style={{ margin: '0 0 8px' }}>Positioner</h3>
            <div style={{ display: 'flex', gap: 8, marginBottom: 12, alignItems: 'center' }}>
                <button onClick={refresh} disabled={loading}>Uppdatera</button>
                <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span>Filter</span>
                    <select value={filterSymbol} onChange={(e) => setFilterSymbol(e.target.value)}>
                        <option value="">Alla</option>
                        {TEST_SYMBOLS.map((s: { symbol: string; name: string }) => {
                            return <option key={s.symbol} value={s.symbol}>{s.symbol}</option>;
                        })}
                    </select>
                </label>
            </div>
            {error && (
                <div style={{ background: '#ffebe9', color: '#86181d', padding: 8, borderRadius: 4, marginBottom: 12 }}>
                    {error}
                </div>
            )}
            {loading ? (
                <div>Laddar…</div>
            ) : (
                <div style={{ overflow: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <thead>
                            <tr>
                                <th align="left">Symbol</th>
                                <th align="left">Amount</th>
                                <th align="left">Base Price</th>
                                <th align="left">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {shown?.length ? (
                                shown.map((p: any, i: number) => (
                                    <tr key={i}>
                                        <td>{p?.symbol || '-'}</td>
                                        <td>{p?.amount ?? '-'}</td>
                                        <td>{p?.base_price ?? '-'}</td>
                                        <td>
                                            <button onClick={() => closePosition(p?.symbol)}>
                                                Close
                                            </button>
                                        </td>
                                    </tr>
                                ))
                            ) : (
                                <tr>
                                    <td colSpan={4} style={{ opacity: 0.7, padding: 8 }}>Inga aktiva positioner</td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}
