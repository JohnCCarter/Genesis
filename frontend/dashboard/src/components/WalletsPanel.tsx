import React from 'react';
import { get } from '../lib/api';

type Wallet = any;

export function WalletsPanel() {
    const [wallets, setWallets] = React.useState<Wallet[]>([]);
    const [loading, setLoading] = React.useState(false);
    const [error, setError] = React.useState<string | null>(null);

    const refresh = React.useCallback(async () => {
        try {
            setLoading(true);
            setError(null);
            const res = await get('/api/v2/wallets');
            setWallets(Array.isArray(res) ? res : []);
        } catch (e: any) {
            setError(e?.message || 'Kunde inte hämta wallets');
        } finally {
            setLoading(false);
        }
    }, []);

    React.useEffect(() => {
        refresh();
        const id = setInterval(refresh, 10000);
        return () => clearInterval(id);
    }, [refresh]);

    return (
        <div style={{ border: '1px solid #e1e4e8', borderRadius: 6, padding: 12 }}>
            <h3 style={{ margin: '0 0 8px' }}>Wallets</h3>
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
                                <th align="left">Typ</th>
                                <th align="left">Valuta</th>
                                <th align="left">Saldo</th>
                                <th align="left">Tillgängligt</th>
                            </tr>
                        </thead>
                        <tbody>
                            {wallets?.length ? (
                                wallets.map((w: any, i: number) => (
                                    <tr key={i}>
                                        <td>{w?.wallet_type || '-'}</td>
                                        <td>{(w?.currency || '').toUpperCase()}</td>
                                        <td>{w?.balance ?? '-'}</td>
                                        <td>{w?.available_balance ?? '-'}</td>
                                    </tr>
                                ))
                            ) : (
                                <tr>
                                    <td colSpan={4} style={{ opacity: 0.7, padding: 8 }}>Inga wallets</td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}


