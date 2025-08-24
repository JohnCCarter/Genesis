import React from 'react';
import { get, post } from '../lib/api';

export function DebugPage() {
    const [subs, setSubs] = React.useState<any>(null);
    const [channel, setChannel] = React.useState<'ticker' | 'trades' | 'candles'>('ticker');
    const [timeframe, setTimeframe] = React.useState('1m');
    const [symbol, setSymbol] = React.useState('tTESTBTC:TESTUSD');
    const [log, setLog] = React.useState<string[]>([]);

    async function refreshSubs() {
        try {
            const s = await get('/api/v2/ws/pool/status');
            setSubs(s);
        } catch {}
    }

    async function subscribe() {
        try {
            await post('/api/v2/ws/subscribe', { channel, symbol, timeframe });
            setLog((l) => [ `subscribed ${channel}:${symbol}:${timeframe}`, ...l ].slice(0, 200));
            await refreshSubs();
        } catch (e: any) {
            setLog((l) => [ `error sub: ${e?.message}`, ...l ].slice(0, 200));
        }
    }

    async function unsubscribe() {
        try {
            await post('/api/v2/ws/unsubscribe', { channel, symbol, timeframe });
            setLog((l) => [ `unsub ${channel}:${symbol}:${timeframe}`, ...l ].slice(0, 200));
            await refreshSubs();
        } catch (e: any) {
            setLog((l) => [ `error unsub: ${e?.message}`, ...l ].slice(0, 200));
        }
    }

    React.useEffect(() => { refreshSubs(); }, []);

    return (
        <div>
            <h3>WS Debug</h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(160px, 1fr))', gap: 8 }}>
                <div>
                    <label>Channel</label>
                    <select value={channel} onChange={(e) => setChannel(e.target.value as any)} style={{ width: '100%' }}>
                        <option value="ticker">ticker</option>
                        <option value="trades">trades</option>
                        <option value="candles">candles</option>
                    </select>
                </div>
                <div>
                    <label>Timeframe</label>
                    <input value={timeframe} onChange={(e) => setTimeframe(e.target.value)} style={{ width: '100%' }} />
                </div>
                <div>
                    <label>Symbol</label>
                    <input value={symbol} onChange={(e) => setSymbol(e.target.value)} style={{ width: '100%' }} />
                </div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'end' }}>
                    <button onClick={subscribe}>Subscribe</button>
                    <button onClick={unsubscribe}>Unsubscribe</button>
                    <button onClick={refreshSubs}>Refresh</button>
                </div>
            </div>
            <div style={{ marginTop: 12 }}>
                <h4>Aktiva subs</h4>
                <pre style={{ background: '#f6f8fa', padding: 8, borderRadius: 6 }}>{JSON.stringify(subs, null, 2)}</pre>
            </div>
            <div style={{ marginTop: 12 }}>
                <h4>Logg</h4>
                <pre style={{ background: '#f6f8fa', padding: 8, borderRadius: 6 }}>{log.join('\n')}</pre>
            </div>
        </div>
    );
}


