import React from 'react';
import { get, post } from '@lib/api';

interface RefreshManagerStatus {
    status: {
        total_panels: number;
        running: boolean;
        panels: Record<string, {
            priority: string;
            interval_seconds: number;
            last_run: string | null;
            next_run: string | null;
            is_running: boolean;
            error_count: number;
            dependencies: string[];
        }>;
    };
    intervals: Record<string, number>;
    shared_data_timestamp: string;
}

export function RefreshManagerPanel() {
    const [status, setStatus] = React.useState<RefreshManagerStatus | null>(null);
    const [loading, setLoading] = React.useState(false);
    const [error, setError] = React.useState<string | null>(null);
    const [lastUpdate, setLastUpdate] = React.useState<Date | null>(null);

    const refresh = React.useCallback(async () => {
        try {
            setLoading(true);
            setError(null);
            const data = await get('/api/v2/refresh-manager/status');
            setStatus(data);
            setLastUpdate(new Date());
        } catch (e: any) {
            setError(e?.message || 'Kunde inte hämta refresh manager status');
        } finally {
            setLoading(false);
        }
    }, []);

    const forceRefresh = React.useCallback(async (panelId?: string) => {
        try {
            setLoading(true);
            await post('/api/v2/refresh-manager/force-refresh', { panel_id: panelId });
            await refresh(); // Uppdatera status efter force refresh
        } catch (e: any) {
            setError(e?.message || 'Kunde inte tvinga refresh');
        } finally {
            setLoading(false);
        }
    }, [refresh]);

    const startManager = React.useCallback(async () => {
        try {
            setLoading(true);
            await post('/api/v2/refresh-manager/start');
            await refresh();
        } catch (e: any) {
            setError(e?.message || 'Kunde inte starta refresh manager');
        } finally {
            setLoading(false);
        }
    }, [refresh]);

    const stopManager = React.useCallback(async () => {
        try {
            setLoading(true);
            await post('/api/v2/refresh-manager/stop');
            await refresh();
        } catch (e: any) {
            setError(e?.message || 'Kunde inte stoppa refresh manager');
        } finally {
            setLoading(false);
        }
    }, [refresh]);

    React.useEffect(() => {
        refresh();
        const interval = setInterval(refresh, 10000); // Uppdatera var 10:e sekund
        return () => clearInterval(interval);
    }, [refresh]);

    const getPriorityColor = (priority: string) => {
        switch (priority) {
            case 'CRITICAL': return '#dc3545'; // Röd
            case 'HIGH': return '#fd7e14';     // Orange
            case 'MEDIUM': return '#ffc107';    // Gul
            case 'LOW': return '#28a745';       // Grön
            default: return '#6c757d';          // Grå
        }
    };

    const getStatusColor = (isRunning: boolean, errorCount: number) => {
        if (errorCount > 0) return '#dc3545'; // Röd vid fel
        if (isRunning) return '#17a2b8';     // Blå vid körning
        return '#28a745';                     // Grön vid OK
    };

    const formatTime = (timeStr: string | null) => {
        if (!timeStr) return '-';
        try {
            return new Date(timeStr).toLocaleTimeString();
        } catch {
            return timeStr;
        }
    };

    const formatInterval = (seconds: number) => {
        if (seconds < 60) return `${seconds}s`;
        if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
        return `${Math.round(seconds / 3600)}h`;
    };

    return (
        <div style={{ border: '1px solid #e1e4e8', borderRadius: 6, padding: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <h3 style={{ margin: 0 }}>🔄 Refresh Manager</h3>
                <div style={{ display: 'flex', gap: 8 }}>
                    <button onClick={refresh} disabled={loading}>
                        {loading ? 'Laddar...' : '🔄 Uppdatera'}
                    </button>
                    <button onClick={() => forceRefresh()} disabled={loading}>
                        ⚡ Force All
                    </button>
                    {status?.status.running ? (
                        <button onClick={stopManager} disabled={loading} style={{ background: '#dc3545', color: 'white' }}>
                            🛑 Stoppa
                        </button>
                    ) : (
                        <button onClick={startManager} disabled={loading} style={{ background: '#28a745', color: 'white' }}>
                            ▶️ Starta
                        </button>
                    )}
                </div>
            </div>

            {error && (
                <div style={{ background: '#ffebe9', color: '#86181d', padding: 8, borderRadius: 4, marginBottom: 12 }}>
                    {error}
                </div>
            )}

            {status && (
                <>
                    {/* Översikt */}
                    <div style={{ 
                        display: 'grid', 
                        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
                        gap: 12, 
                        marginBottom: 16,
                        padding: 12,
                        background: '#f6f8fa',
                        borderRadius: 6
                    }}>
                        <div>
                            <div style={{ fontSize: 12, color: '#555' }}>Status</div>
                            <div style={{ 
                                fontSize: 16, 
                                fontWeight: 'bold',
                                color: status.status.running ? '#28a745' : '#dc3545'
                            }}>
                                {status.status.running ? '🟢 Aktiv' : '🔴 Inaktiv'}
                            </div>
                        </div>
                        <div>
                            <div style={{ fontSize: 12, color: '#555' }}>Paneler</div>
                            <div style={{ fontSize: 16, fontWeight: 'bold' }}>
                                {status.status.total_panels}
                            </div>
                        </div>
                        <div>
                            <div style={{ fontSize: 12, color: '#555' }}>Senaste uppdatering</div>
                            <div style={{ fontSize: 12 }}>
                                {lastUpdate ? lastUpdate.toLocaleTimeString() : '-'}
                            </div>
                        </div>
                        <div>
                            <div style={{ fontSize: 12, color: '#555' }}>Shared Data</div>
                            <div style={{ fontSize: 12 }}>
                                {formatTime(status.shared_data_timestamp)}
                            </div>
                        </div>
                    </div>

                    {/* Paneler */}
                    <div style={{ marginBottom: 12 }}>
                        <h4 style={{ margin: '0 0 8px' }}>Registrerade Paneler</h4>
                        <div style={{ overflow: 'auto', maxHeight: 400 }}>
                            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                                <thead>
                                    <tr style={{ background: '#f6f8fa' }}>
                                        <th style={{ textAlign: 'left', padding: '8px', fontSize: 12 }}>Panel</th>
                                        <th style={{ textAlign: 'left', padding: '8px', fontSize: 12 }}>Prioritet</th>
                                        <th style={{ textAlign: 'left', padding: '8px', fontSize: 12 }}>Intervall</th>
                                        <th style={{ textAlign: 'left', padding: '8px', fontSize: 12 }}>Status</th>
                                        <th style={{ textAlign: 'left', padding: '8px', fontSize: 12 }}>Senaste</th>
                                        <th style={{ textAlign: 'left', padding: '8px', fontSize: 12 }}>Nästa</th>
                                        <th style={{ textAlign: 'left', padding: '8px', fontSize: 12 }}>Fel</th>
                                        <th style={{ textAlign: 'left', padding: '8px', fontSize: 12 }}>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {Object.entries(status.status.panels).map(([panelId, panel]) => (
                                        <tr key={panelId}>
                                            <td style={{ padding: '6px 8px', fontSize: 12, fontWeight: 'bold' }}>
                                                {panelId}
                                            </td>
                                            <td style={{ padding: '6px 8px', fontSize: 12 }}>
                                                <span style={{ 
                                                    color: getPriorityColor(panel.priority),
                                                    fontWeight: 'bold'
                                                }}>
                                                    {panel.priority}
                                                </span>
                                            </td>
                                            <td style={{ padding: '6px 8px', fontSize: 12 }}>
                                                {formatInterval(panel.interval_seconds)}
                                            </td>
                                            <td style={{ padding: '6px 8px', fontSize: 12 }}>
                                                <span style={{ 
                                                    color: getStatusColor(panel.is_running, panel.error_count),
                                                    fontWeight: 'bold'
                                                }}>
                                                    {panel.is_running ? '🔄 Kör' : 
                                                     panel.error_count > 0 ? '❌ Fel' : '✅ OK'}
                                                </span>
                                            </td>
                                            <td style={{ padding: '6px 8px', fontSize: 12 }}>
                                                {formatTime(panel.last_run)}
                                            </td>
                                            <td style={{ padding: '6px 8px', fontSize: 12 }}>
                                                {formatTime(panel.next_run)}
                                            </td>
                                            <td style={{ padding: '6px 8px', fontSize: 12 }}>
                                                <span style={{ 
                                                    color: panel.error_count > 0 ? '#dc3545' : '#28a745',
                                                    fontWeight: 'bold'
                                                }}>
                                                    {panel.error_count}
                                                </span>
                                            </td>
                                            <td style={{ padding: '6px 8px', fontSize: 12 }}>
                                                <button 
                                                    onClick={() => forceRefresh(panelId)}
                                                    disabled={loading}
                                                    style={{ 
                                                        padding: '2px 6px', 
                                                        fontSize: 10,
                                                        border: '1px solid #ccc',
                                                        borderRadius: 3,
                                                        background: '#fff'
                                                    }}
                                                >
                                                    ⚡
                                                </button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    {/* Refresh Intervall Sammanfattning */}
                    <div>
                        <h4 style={{ margin: '0 0 8px' }}>Refresh Intervall</h4>
                        <div style={{ 
                            display: 'grid', 
                            gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', 
                            gap: 8,
                            fontSize: 12
                        }}>
                            {Object.entries(status.intervals).map(([panelId, interval]) => (
                                <div key={panelId} style={{ 
                                    padding: 8, 
                                    background: '#f6f8fa', 
                                    borderRadius: 4,
                                    border: '1px solid #e1e4e8'
                                }}>
                                    <div style={{ fontWeight: 'bold' }}>{panelId}</div>
                                    <div style={{ color: '#555' }}>{formatInterval(interval)}</div>
                                </div>
                            ))}
                        </div>
                    </div>
                </>
            )}
        </div>
    );
}
