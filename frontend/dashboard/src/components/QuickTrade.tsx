import React from 'react';
import { get, post } from '../lib/api';
import { TEST_SYMBOLS } from '../lib/testSymbols';

export function QuickTrade() {
    const [symbol, setSymbol] = React.useState<string>(localStorage.getItem('qt_symbol') || 'TESTBTC:TESTUSD');
    const [side, setSide] = React.useState<'buy' | 'sell'>((localStorage.getItem('qt_side') as any) || 'buy');
    const [amount, setAmount] = React.useState<string>(localStorage.getItem('qt_amount') || '0.001');
    const [price, setPrice] = React.useState<string>(localStorage.getItem('qt_price') || '');
    // Nytt: konto (exchange/margin) och ordertyp (MARKET/LIMIT)
    const [account, setAccount] = React.useState<'exchange' | 'margin'>((localStorage.getItem('qt_account') as any) || 'exchange');
    const [orderType, setOrderType] = React.useState<'MARKET' | 'LIMIT'>(((localStorage.getItem('qt_order_type') as any) || 'MARKET') as 'MARKET' | 'LIMIT');
    const [loading, setLoading] = React.useState(false);
    const [msg, setMsg] = React.useState<string | null>(null);
    const [err, setErr] = React.useState<string | null>(null);

    React.useEffect(() => {
        localStorage.setItem('qt_symbol', symbol);
        localStorage.setItem('qt_side', side);
        localStorage.setItem('qt_amount', amount);
        localStorage.setItem('qt_price', price);
        localStorage.setItem('qt_account', account);
        localStorage.setItem('qt_order_type', orderType);
    }, [symbol, side, amount, price, account, orderType]);

    async function preview() {
        try {
            setLoading(true);
            setErr(null);
            const t = await get(`/api/v2/market/ticker/${encodeURIComponent(symbol)}`);
            setMsg(`Ticker: ${JSON.stringify(t)}`);
        } catch (e: any) {
            setErr(e?.message || 'preview_failed');
        } finally {
            setLoading(false);
        }
    }

    async function trade() {
        try {
            setLoading(true);
            setErr(null);
            // Mappa typ beroende på konto
            let computedType = orderType.toUpperCase();
            if (account === 'exchange') {
                computedType = computedType.startsWith('EXCHANGE') ? computedType : `EXCHANGE ${computedType}`;
            } else {
                // margin: ska INTE ha EXCHANGE-prefix
                computedType = computedType.replace(/^EXCHANGE\s+/i, '').toUpperCase();
            }

            if (computedType.includes('LIMIT') && String(price).trim() === '') {
                throw new Error('Pris krävs för LIMIT-order');
            }

            const res = await post('/api/v2/order', {
                symbol,
                amount: String(amount).trim(),
                type: computedType,
                side,
                ...(computedType.includes('LIMIT') ? { price: String(price).trim() } : {}),
            });
            setMsg(JSON.stringify(res));
        } catch (e: any) {
            setErr(e?.message || 'trade_failed');
        } finally {
            setLoading(false);
        }
    }

    return (
        <div style={{ border: '1px solid #e1e4e8', borderRadius: 6, padding: 12 }}>
            {err && <div style={{ background: '#ffebe9', color: '#86181d', padding: 8, borderRadius: 4, marginBottom: 12 }}>{err}</div>}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, minmax(140px, 1fr))', gap: 8, alignItems: 'end' }}>
                <div>
                    <label>Symbol</label>
                    <select value={symbol} onChange={(e) => setSymbol(e.target.value)} style={{ width: '100%' }}>
                        {TEST_SYMBOLS.map((s: { symbol: string; name: string }) => (
                            <option key={s.symbol} value={s.symbol}>{s.symbol}</option>
                        ))}
                    </select>
                </div>
                <div>
                    <label>Konto</label>
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
                    <label>Ordertyp</label>
                    <select value={orderType} onChange={(e) => setOrderType(e.target.value as any)} style={{ width: '100%' }}>
                        <option value="MARKET">Market</option>
                        <option value="LIMIT">Limit</option>
                    </select>
                </div>
                <div>
                    <label>Amount</label>
                    <input value={amount} onChange={(e) => setAmount(e.target.value)} style={{ width: '100%' }} />
                </div>
                {orderType === 'LIMIT' && (
                    <div>
                        <label>Price</label>
                        <input value={price} onChange={(e) => setPrice(e.target.value)} style={{ width: '100%' }} />
                    </div>
                )}
            </div>
            <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                <button onClick={preview} disabled={loading}>{loading ? 'Preview…' : 'Preview'}</button>
                <button onClick={trade} disabled={loading}>{loading ? 'Trading…' : 'Trade'}</button>
            </div>
            {msg && (
                <pre style={{ background: '#f6f8fa', padding: 8, borderRadius: 6, marginTop: 12 }}>{msg}</pre>
            )}
        </div>
    );
}
