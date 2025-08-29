import React from 'react';
import { get } from '../lib/api';
import { Sparkline } from './Sparkline';
import { JsonTree } from './JsonTree';

type TabKey = 'trades' | 'ledgers' | 'equity';

function formatDateTime(v: any): string {
    try {
        const d = typeof v === 'string' ? new Date(v) : new Date(v * 1000);
        if (Number.isNaN(d.getTime())) return String(v);
        return d.toLocaleString();
    } catch {
        return String(v);
    }
}

function toNum(x: any, digits = 6): string {
    const n = Number(x);
    if (!Number.isFinite(n)) return '-';
    return n.toFixed(digits);
}

function exportCSV(filename: string, rows: any[], columns: { key: string; title: string }[]) {
    try {
        const header = columns.map(c => '"' + c.title.replace(/"/g, '""') + '"').join(',');
        const lines = rows.map(r =>
            columns
                .map(c => {
                    const val = r[c.key];
                    const s = val === undefined || val === null ? '' : String(val);
                    return '"' + s.replace(/"/g, '""') + '"';
                })
                .join(',')
        );
        const csv = [header, ...lines].join('\n');
        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
    } catch {
        // ignore
    }
}

export function HistoryPanel() {
    const [activeTab, setActiveTab] = React.useState<TabKey>('trades');
    const [symbol, setSymbol] = React.useState<string>('');
    const [limit, setLimit] = React.useState<number>(100);

    const [trades, setTrades] = React.useState<any[]>([]);
    const [ledgers, setLedgers] = React.useState<any[]>([]);
    const [equity, setEquity] = React.useState<any>(null);
    const [equityHist, setEquityHist] = React.useState<any[]>([]);
    const [loading, setLoading] = React.useState(false);
    const [error, setError] = React.useState<string | null>(null);
    const [details, setDetails] = React.useState<any | null>(null);

    const refresh = React.useCallback(async () => {
        try {
            setLoading(true);
            setError(null);
            const qSymbol = symbol && symbol.trim().length > 0 ? `&symbol=${encodeURIComponent(symbol.trim())}` : '';
            const [t, l, e, eh] = await Promise.all([
                get(`/api/v2/trades/history?limit=${limit}${qSymbol}`).catch(() => []),
                get(`/api/v2/ledgers?limit=${limit}`).catch(() => []),
                get('/api/v2/account/performance').catch(() => null),
                get(`/api/v2/account/equity/history?limit=${Math.min(1000, Math.max(100, limit))}`).catch(() => ({ equity: [] })),
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
    }, [symbol, limit]);

    React.useEffect(() => {
        refresh();
    }, [refresh]);

    // Summaries
    const tradesSummary = React.useMemo(() => {
        const count = trades.length;
        let vol = 0;
        let fee = 0;
        trades.forEach((r: any) => {
            vol += Math.abs(Number(r?.amount || 0));
            fee += Number(r?.fee || 0);
        });
        return { count, volume: vol, totalFee: fee };
    }, [trades]);

    const ledgersSummary = React.useMemo(() => {
        const count = ledgers.length;
        const byCur: Record<string, number> = {};
        ledgers.forEach((r: any) => {
            const cur = String(r?.currency || '').toUpperCase();
            const amt = Number(r?.amount || 0);
            byCur[cur] = (byCur[cur] || 0) + amt;
        });
        return { count, byCur };
    }, [ledgers]);

    const tradesColumns = [
        { key: 'executed_at', title: 'Time' },
        { key: 'symbol', title: 'Symbol' },
        { key: 'amount', title: 'Amount' },
        { key: 'price', title: 'Price' },
        { key: 'fee', title: 'Fee' },
        { key: 'fee_currency', title: 'FeeCur' },
        { key: 'order_id', title: 'OrderId' },
    ];
    const ledgersColumns = [
        { key: 'created_at', title: 'Time' },
        { key: 'wallet_type', title: 'Wallet' },
        { key: 'currency', title: 'Cur' },
        { key: 'amount', title: 'Amount' },
        { key: 'balance', title: 'Balance' },
        { key: 'description', title: 'Description' },
    ];

    const renderTradesTable = () => (
        <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <div style={{ fontSize: 12, color: '#555' }}>
                    Count: <b>{tradesSummary.count}</b> · Volume: <b>{toNum(tradesSummary.volume, 6)}</b> · Total fee:{' '}
                    <b>{toNum(tradesSummary.totalFee, 6)}</b>
                </div>
                <div>
                    <button
                        onClick={() => exportCSV('trades.csv', trades, tradesColumns)}
                        style={{ fontSize: 12, padding: '4px 8px', border: '1px solid #ccc', borderRadius: 6, background: '#fff' }}
                    >
                        Export CSV
                    </button>
                </div>
            </div>
            <div style={{ overflow: 'auto', maxHeight: 360, border: '1px solid #e1e4e8', borderRadius: 6 }}>
                <table style={{ width: '100%', borderCollapse: 'separate', borderSpacing: 0 }}>
                    <thead style={{ position: 'sticky', top: 0, background: '#f6f8fa', zIndex: 1 }}>
                        <tr>
                            {tradesColumns.map(c => (
                                <th key={c.key} style={{ textAlign: 'left', padding: '8px 8px', borderBottom: '1px solid #e1e4e8', fontSize: 12 }}>
                                    {c.title}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {trades.map((r: any, idx: number) => {
                            const amount = Number(r?.amount || 0);
                            const isBuy = amount > 0;
                            return (
                                <tr key={idx} onClick={() => setDetails(r)} style={{ cursor: 'pointer' }}>
                                    <td style={{ padding: '6px 8px', borderBottom: '1px solid #f1f3f5', fontSize: 12 }}>{formatDateTime(r?.executed_at)}</td>
                                    <td style={{ padding: '6px 8px', borderBottom: '1px solid #f1f3f5', fontSize: 12 }}>{r?.symbol || '-'}</td>
                                    <td style={{ padding: '6px 8px', borderBottom: '1px solid #f1f3f5', textAlign: 'right', fontFamily: 'monospace', color: isBuy ? '#2f9e44' : '#e03131' }}>{toNum(amount, 6)}</td>
                                    <td style={{ padding: '6px 8px', borderBottom: '1px solid #f1f3f5', textAlign: 'right', fontFamily: 'monospace' }}>{toNum(r?.price, 6)}</td>
                                    <td style={{ padding: '6px 8px', borderBottom: '1px solid #f1f3f5', textAlign: 'right', fontFamily: 'monospace' }}>{toNum(r?.fee, 6)}</td>
                                    <td style={{ padding: '6px 8px', borderBottom: '1px solid #f1f3f5', fontSize: 12 }}>{r?.fee_currency || '-'}</td>
                                    <td style={{ padding: '6px 8px', borderBottom: '1px solid #f1f3f5', fontSize: 12 }}>{r?.order_id ?? '-'}</td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
        </div>
    );

    const renderLedgersTable = () => (
        <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <div style={{ fontSize: 12, color: '#555' }}>
                    Count: <b>{ledgersSummary.count}</b> · Totals:{' '}
                    {Object.entries(ledgersSummary.byCur).map(([cur, val], i) => (
                        <span key={cur}>
                            {i > 0 ? ' · ' : ''}
                            {cur}: <b>{toNum(val, 6)}</b>
                        </span>
                    ))}
                </div>
                <div>
                    <button
                        onClick={() => exportCSV('ledgers.csv', ledgers, ledgersColumns)}
                        style={{ fontSize: 12, padding: '4px 8px', border: '1px solid #ccc', borderRadius: 6, background: '#fff' }}
                    >
                        Export CSV
                    </button>
                </div>
            </div>
            <div style={{ overflow: 'auto', maxHeight: 360, border: '1px solid #e1e4e8', borderRadius: 6 }}>
                <table style={{ width: '100%', borderCollapse: 'separate', borderSpacing: 0 }}>
                    <thead style={{ position: 'sticky', top: 0, background: '#f6f8fa', zIndex: 1 }}>
                        <tr>
                            {ledgersColumns.map(c => (
                                <th key={c.key} style={{ textAlign: 'left', padding: '8px 8px', borderBottom: '1px solid #e1e4e8', fontSize: 12 }}>
                                    {c.title}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {ledgers.map((r: any, idx: number) => (
                            <tr key={idx} onClick={() => setDetails(r)} style={{ cursor: 'pointer' }}>
                                <td style={{ padding: '6px 8px', borderBottom: '1px solid #f1f3f5', fontSize: 12 }}>{formatDateTime(r?.created_at)}</td>
                                <td style={{ padding: '6px 8px', borderBottom: '1px solid #f1f3f5', fontSize: 12 }}>{r?.wallet_type || '-'}</td>
                                <td style={{ padding: '6px 8px', borderBottom: '1px solid #f1f3f5', fontSize: 12 }}>{r?.currency || '-'}</td>
                                <td style={{ padding: '6px 8px', borderBottom: '1px solid #f1f3f5', textAlign: 'right', fontFamily: 'monospace', color: (Number(r?.amount || 0) >= 0 ? '#2f9e44' : '#e03131') }}>{toNum(r?.amount, 6)}</td>
                                <td style={{ padding: '6px 8px', borderBottom: '1px solid #f1f3f5', textAlign: 'right', fontFamily: 'monospace' }}>{toNum(r?.balance, 6)}</td>
                                <td style={{ padding: '6px 8px', borderBottom: '1px solid #f1f3f5', fontSize: 12 }}>{r?.description || '-'}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );

    return (
        <div style={{ border: '1px solid #e1e4e8', borderRadius: 6, padding: 12 }}>
            <h3 style={{ margin: '0 0 8px' }}>Historik</h3>
            {/* Filterbar */}
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8, flexWrap: 'wrap' }}>
                <label style={{ fontSize: 12, color: '#555' }}>Symbol</label>
                <input
                    value={symbol}
                    onChange={(e) => setSymbol(e.target.value)}
                    placeholder="tBTCUSD"
                    style={{ padding: '4px 8px', border: '1px solid #ced4da', borderRadius: 6, fontSize: 12 }}
                />
                <label style={{ fontSize: 12, color: '#555' }}>Limit</label>
                <select
                    value={String(limit)}
                    onChange={(e) => setLimit(Number(e.target.value || 100))}
                    style={{ padding: '4px 8px', border: '1px solid #ced4da', borderRadius: 6, fontSize: 12 }}
                >
                    <option value="25">25</option>
                    <option value="100">100</option>
                    <option value="500">500</option>
                </select>
                <button onClick={() => refresh()} style={{ padding: '4px 10px', border: '1px solid #ccc', borderRadius: 6, background: '#fff', fontSize: 12 }}>Refresh</button>
            </div>

            {/* Flikar */}
            <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
                {([
                    { key: 'trades', label: 'Trades' },
                    { key: 'ledgers', label: 'Ledgers' },
                    { key: 'equity', label: 'Equity' },
                ] as { key: TabKey; label: string }[]).map(t => (
                    <button
                        key={t.key}
                        onClick={() => setActiveTab(t.key)}
                        style={{
                            padding: '6px 10px',
                            borderRadius: 6,
                            border: '1px solid #ccc',
                            background: activeTab === t.key ? '#e7f5ff' : '#fff',
                            fontSize: 12,
                            cursor: 'pointer',
                        }}
                    >
                        {t.label}
                    </button>
                ))}
            </div>

            {error && (
                <div style={{ background: '#ffebe9', color: '#86181d', padding: 8, borderRadius: 4, marginBottom: 12 }}>{error}</div>
            )}
            {loading && <div style={{ marginBottom: 8 }}>Laddar…</div>}

            {/* Innehåll */}
            {activeTab === 'trades' && renderTradesTable()}
            {activeTab === 'ledgers' && renderLedgersTable()}
            {activeTab === 'equity' && (
                <div>
                    <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'center', marginBottom: 12 }}>
                        <div>
                            <div style={{ fontSize: 12, color: '#555' }}>Equity (sparkline)</div>
                            <Sparkline data={(equityHist || []).map((x: any) => Number(x?.equity || x?.value || 0)).filter((n: number) => Number.isFinite(n))} width={220} height={42} />
                        </div>
                        <div style={{ fontSize: 12, color: '#555' }}>
                            <div>Latest equity: <b>{toNum((equityHist?.[equityHist.length - 1]?.equity) ?? 0, 2)}</b></div>
                            <div>Points: <b>{equityHist?.length || 0}</b></div>
                        </div>
                    </div>
                    <div style={{ fontSize: 12, color: '#555', marginBottom: 8 }}>Performance snapshot</div>
                    <JsonTree data={equity} />
                    <div style={{ fontSize: 12, color: '#555', margin: '12px 0 8px' }}>Equity History</div>
                    <JsonTree data={equityHist} />
                </div>
            )}

            {/* Details Drawer */}
            {details && (
                <div
                    onClick={() => setDetails(null)}
                    style={{
                        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.25)', display: 'flex', justifyContent: 'flex-end',
                    }}
                >
                    <div
                        onClick={(e) => e.stopPropagation()}
                        style={{ width: 420, maxWidth: '90%', height: '100%', background: '#fff', boxShadow: '0 0 0 1px #dee2e6', padding: 12, overflow: 'auto' }}
                    >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                            <div style={{ fontWeight: 600 }}>Detaljer</div>
                            <button onClick={() => setDetails(null)} style={{ border: '1px solid #ccc', background: '#fff', borderRadius: 6, padding: '4px 8px', fontSize: 12 }}>Stäng</button>
                        </div>
                        <JsonTree data={details} />
                    </div>
                </div>
            )}
        </div>
    );
}
