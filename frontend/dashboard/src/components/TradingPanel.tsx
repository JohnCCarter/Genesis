import React from 'react';
import { getWith, post, ensureToken } from '@lib/api';

type OrderRow = any;

function Section({ title, children }: { title: string; children: React.ReactNode }) {
    return (
        <div style={{ marginBottom: 24 }}>
            <h3 style={{ margin: '16px 0 8px' }}>{title}</h3>
            {children}
        </div>
    );
}

export const TradingPanel = React.memo(function TradingPanel() {
    const [orders, setOrders] = React.useState<OrderRow[]>([]);
    const [loading, setLoading] = React.useState(false);
    const [placing, setPlacing] = React.useState(false);
    const [error, setError] = React.useState<string | null>(null);
    const [symbolsList, setSymbolsList] = React.useState<string[]>([]);
    const [symbolsLoading, setSymbolsLoading] = React.useState(false);
    const [lastOrderMsg, setLastOrderMsg] = React.useState<string | null>(null);
    const [lastOrderOk, setLastOrderOk] = React.useState<boolean | null>(null);
    const [paperOnly, setPaperOnly] = React.useState<boolean>(true);
    const [isEditing, setIsEditing] = React.useState<boolean>(false);
    const blurTimeoutRef = React.useRef<number | null>(null);

    const PAPER_BASES = React.useMemo(
        () => [
            'BTC', 'ETH', 'LTC', 'SOL', 'ADA', 'XRP', 'DOT', 'FIL',
            'XTZ', 'APT', 'DOGE', 'BCH', 'LINK', 'AVAX', 'MATIC', 'TRX',
        ],
        []
    );
    const PAPER_SYMBOLS = React.useMemo(
        () => PAPER_BASES.map((b) => `tTEST${b}:TESTUSD`),
        [PAPER_BASES]
    );

    const optionsList = React.useMemo(() => {
        if (!Array.isArray(symbolsList) || !symbolsList.length) return paperOnly ? PAPER_SYMBOLS : [];
        if (paperOnly) {
            const onlyTest = symbolsList.filter((s) => s.includes('TEST'));
            return onlyTest.length ? onlyTest : PAPER_SYMBOLS;
        }
        return symbolsList;
    }, [symbolsList, paperOnly, PAPER_SYMBOLS]);

    // Order form state
    const [symbol, setSymbol] = React.useState('');
    const [side, setSide] = React.useState<'buy' | 'sell'>('buy');
    const [account, setAccount] = React.useState<'exchange' | 'margin'>('exchange');
    const [type, setType] = React.useState<string>('EXCHANGE MARKET');
    const [amount, setAmount] = React.useState<string>('0.001');
    const [price, setPrice] = React.useState<string>('');
    const [postOnly, setPostOnly] = React.useState(false);
    const [reduceOnly, setReduceOnly] = React.useState(false);

    const refreshOrders = React.useCallback(async () => {
        try {
            setLoading(true);
            setError(null);
            if (isEditing) {
                return; // hoppa över uppdatering när användaren skriver
            }
            const res = await getWith('/api/v2/orders', { timeout: 12000, maxRetries: 1 });
            setOrders(Array.isArray(res) ? res : []);
        } catch (e: any) {
            setError(e?.message || 'Kunde inte hämta ordrar');
        } finally {
            setLoading(false);
        }
    }, [isEditing]);

    React.useEffect(() => {
        refreshOrders();
        const id = setInterval(refreshOrders, 90000);
        return () => clearInterval(id);
    }, [refreshOrders]);

    const refreshSymbols = React.useCallback(async () => {
        setSymbolsLoading(true);
        try {
            try { await ensureToken(); } catch { }
            let list: string[] = [];
            if (paperOnly) {
                try {
                    const p = await getWith('/api/v2/market/symbols/paper?format=v2', { timeout: 8000, maxRetries: 0 });
                    if (Array.isArray(p) && p.length) list = p;
                } catch { }
            }
            if (!list.length && !paperOnly) {
                try {
                    const res1 = await getWith('/api/v2/market/symbols/config?format=v2', { timeout: 8000, maxRetries: 0 });
                    if (Array.isArray(res1) && res1.length) list = res1;
                } catch { }
            }
            if (!list.length) {
                try {
                    const res2 = await getWith('/api/v2/market/symbols?format=v2', { timeout: 10000, maxRetries: 0 });
                    if (Array.isArray(res2)) list = res2;
                } catch { }
            }
            setSymbolsList(list);
            if (!symbol && list.length) setSymbol(list[0] || '');
        } finally {
            setSymbolsLoading(false);
        }
    }, [paperOnly, symbol]);

    React.useEffect(() => { refreshSymbols(); }, [refreshSymbols, paperOnly]);

    async function placeOrder() {
        try {
            setPlacing(true);
            setError(null);
            // Justera ordertyp utifrån konto (exchange vs margin)
            let computedType = type;
            if (account === 'margin') {
                computedType = type.replace(/^EXCHANGE\s+/i, '').toUpperCase();
            } else {
                // exchange: säkerställ EXCHANGE-prefix
                const upper = type.toUpperCase();
                computedType = upper.startsWith('EXCHANGE') ? upper : `EXCHANGE ${upper}`;
            }

            const body: any = {
                symbol,
                amount: String(amount || '').trim(),
                type: computedType,
                side,
                post_only: !!postOnly,
                reduce_only: !!reduceOnly,
            };
            if (computedType.toUpperCase().includes('LIMIT')) body.price = String(price || '').trim();
            const res = await post('/api/v2/order', body);
            if (!res?.success) {
                setLastOrderOk(false);
                setLastOrderMsg(String(res?.error || 'order_failed'));
                throw new Error(res?.error || 'order_failed');
            }
            const usedWs = !!res?.data?.ws_fallback;
            setLastOrderOk(true);
            setLastOrderMsg(usedWs ? 'Order lagd via WS fallback' : 'Order lagd via REST');
            await refreshOrders();
        } catch (e: any) {
            setError(e?.message || 'Kunde inte lägga order');
            if (lastOrderOk !== false) {
                setLastOrderOk(false);
                setLastOrderMsg(e?.message || 'order_failed');
            }
        } finally {
            setPlacing(false);
        }
    }

    async function cancelOrder(orderId: number) {
        try {
            await post('/api/v2/order/cancel', { order_id: orderId });
            await refreshOrders();
        } catch { }
    }

    async function cancelAll() {
        try {
            await post('/api/v2/orders/cancel/all', {});
            await refreshOrders();
        } catch { }
    }

    function OrderForm() {
        return (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, minmax(120px, 1fr))', gap: 8, alignItems: 'end' }}>
                <div>
                    <label>Symbol</label>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 4, flexWrap: 'wrap' }}>
                        <small style={{ opacity: 0.8 }}>{symbolsList?.length ? `${symbolsList.length} symboler` : '—'}</small>
                        <button type="button" onClick={refreshSymbols} disabled={symbolsLoading}>
                            {symbolsLoading ? 'Uppdaterar…' : 'Uppdatera symboler'}
                        </button>
                        <button type="button" onClick={() => setPaperOnly(false)} disabled={symbolsLoading}>Visa alla</button>
                        <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <input type="checkbox" checked={paperOnly} onChange={(e) => setPaperOnly(e.target.checked)} />
                            <span>Paper‑symboler</span>
                        </label>
                    </div>
                    <input
                        placeholder={paperOnly ? 'tTESTASSET:TESTUSD' : 'tPAIR (t.ex. tBTCUSD)'}
                        value={symbol}
                        onFocus={() => {
                            if (blurTimeoutRef.current) window.clearTimeout(blurTimeoutRef.current);
                            setIsEditing(true);
                        }}
                        onBlur={() => {
                            if (blurTimeoutRef.current) window.clearTimeout(blurTimeoutRef.current);
                            blurTimeoutRef.current = window.setTimeout(() => setIsEditing(false), 400);
                        }}
                        onChange={(e) => setSymbol(e.target.value)}
                        style={{ width: '100%' }}
                    />
                    <select
                        value={symbol}
                        onChange={(e) => setSymbol(e.target.value)}
                        onFocus={() => {
                            if (blurTimeoutRef.current) window.clearTimeout(blurTimeoutRef.current);
                            setIsEditing(true);
                        }}
                        onBlur={() => {
                            if (blurTimeoutRef.current) window.clearTimeout(blurTimeoutRef.current);
                            blurTimeoutRef.current = window.setTimeout(() => setIsEditing(false), 400);
                        }}
                        style={{ width: '100%', marginTop: 6 }}
                    >
                        <option value="">— välj symbol —</option>
                        {optionsList.map((s) => (
                            <option key={s} value={s}>{s}</option>
                        ))}
                    </select>
                </div>
                <div>
                    <label>Account</label>
                    <select value={account} onChange={(e) => setAccount(e.target.value as any)} style={{ width: '100%' }}>
                        <option value="exchange">Exchange</option>
                        <option value="margin">Margin</option>
                    </select>
                </div>
                <div>
                    <label>Side</label>
                    <select value={side} onChange={(e) => setSide(e.target.value as any)} style={{ width: '100%' }}>
                        <option value="buy">Buy</option>
                        <option value="sell">Sell</option>
                    </select>
                </div>
                <div>
                    <label>Type</label>
                    {account === 'exchange' ? (
                        <select value={type} onChange={(e) => setType(e.target.value)} style={{ width: '100%' }}>
                            <option value="EXCHANGE MARKET">EXCHANGE MARKET</option>
                            <option value="EXCHANGE LIMIT">EXCHANGE LIMIT</option>
                        </select>
                    ) : (
                        <select value={type} onChange={(e) => setType(e.target.value)} style={{ width: '100%' }}>
                            <option value="MARKET">MARKET</option>
                            <option value="LIMIT">LIMIT</option>
                        </select>
                    )}
                </div>
                <div>
                    <label>Amount</label>
                    <input
                        value={amount}
                        onFocus={() => {
                            if (blurTimeoutRef.current) window.clearTimeout(blurTimeoutRef.current);
                            setIsEditing(true);
                        }}
                        onBlur={() => {
                            if (blurTimeoutRef.current) window.clearTimeout(blurTimeoutRef.current);
                            blurTimeoutRef.current = window.setTimeout(() => setIsEditing(false), 400);
                        }}
                        onChange={(e) => setAmount(e.target.value)}
                        style={{ width: '100%' }}
                    />
                </div>
                {(type.toUpperCase().includes('LIMIT')) && (
                    <div>
                        <label>Price</label>
                        <input
                            value={price}
                            onFocus={() => {
                                if (blurTimeoutRef.current) window.clearTimeout(blurTimeoutRef.current);
                                setIsEditing(true);
                            }}
                            onBlur={() => {
                                if (blurTimeoutRef.current) window.clearTimeout(blurTimeoutRef.current);
                                blurTimeoutRef.current = window.setTimeout(() => setIsEditing(false), 400);
                            }}
                            onChange={(e) => setPrice(e.target.value)}
                            style={{ width: '100%' }}
                        />
                    </div>
                )}
                <div>
                    <label style={{ display: 'block' }}>Flags</label>
                    <label style={{ marginRight: 8 }}>
                        <input type="checkbox" checked={postOnly} onChange={(e) => setPostOnly(e.target.checked)} /> Post‑only
                    </label>
                    <label>
                        <input type="checkbox" checked={reduceOnly} onChange={(e) => setReduceOnly(e.target.checked)} /> Reduce‑only
                    </label>
                </div>
                <div>
                    <button onClick={placeOrder} disabled={placing}>
                        {placing ? 'Placing…' : 'Place Order'}
                    </button>
                </div>
                {lastOrderMsg ? (
                    <div style={{ marginTop: 8, padding: 8, borderRadius: 6, background: lastOrderOk ? '#d7f5dd' : '#ffebe9', color: lastOrderOk ? '#166534' : '#86181d' }}>
                        {lastOrderMsg}
                    </div>
                ) : null}
            </div>
        );
    }

    function OrdersTable() {
        return (
            <div>
                <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                    <button onClick={refreshOrders} disabled={loading}>Uppdatera</button>
                    <button onClick={cancelAll} disabled={loading}>Cancel All</button>
                </div>
                <div style={{ overflow: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <thead>
                            <tr>
                                <th align="left">ID</th>
                                <th align="left">Symbol</th>
                                <th align="left">Type</th>
                                <th align="left">Price</th>
                                <th align="left">Amount</th>
                                <th align="left">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {orders?.length ? (
                                orders.map((o: any) => (
                                    <tr key={o?.data?.id || o?.data?.order_id || JSON.stringify(o)}>
                                        <td>{o?.data?.id || o?.data?.order_id || '-'}</td>
                                        <td>{o?.data?.symbol || '-'}</td>
                                        <td>{o?.data?.type || '-'}</td>
                                        <td>{o?.data?.price ?? '-'}</td>
                                        <td>{o?.data?.amount ?? '-'}</td>
                                        <td>
                                            <button onClick={() => cancelOrder(o?.data?.id || o?.data?.order_id)} disabled={loading}>
                                                Cancel
                                            </button>
                                        </td>
                                    </tr>
                                ))
                            ) : (
                                <tr>
                                    <td colSpan={6} style={{ opacity: 0.7, padding: 8 }}>Inga aktiva ordrar</td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        );
    }

    return (
        <div style={{ border: '1px solid #e1e4e8', borderRadius: 6, padding: 12 }}>
            {error && (
                <div style={{ background: '#ffebe9', color: '#86181d', padding: 8, borderRadius: 4, marginBottom: 12 }}>
                    {error}
                </div>
            )}
            <Section title="Orderpanel">
                <OrderForm />
            </Section>
            <Section title="Aktiva ordrar">
                {loading ? <div>Laddar…</div> : <OrdersTable />}
            </Section>
        </div>
    );
});
