import { getWith, post } from '@lib/api';
import React from 'react';

interface RiskStatus {
    timestamp: string;
    current_equity: number;
    daily_loss_percentage: number;
    drawdown_percentage: number;
    trade_constraints: {
        open: boolean;
        paused: boolean;
        next_open: string | null;
        limits: {
            max_trades_per_day: number;
            trade_cooldown_seconds: number;
            max_trades_per_symbol_per_day: number;
        };
        trades: {
            day: string;
            count: number;
            max_per_day: number;
            cooldown_seconds: number;
            cooldown_active: boolean;
        };
    };
    circuit_breaker: {
        open: boolean;
        opened_at: string | null;
        error_count: number;
        error_threshold: number;
    };
    guards: Record<string, {
        enabled: boolean;
        triggered: boolean;
        triggered_at: string | null;
        reason: string | null;
    }>;
    guards_full: Record<string, any>; // Komplett guards data
    overall_status: 'healthy' | 'degraded' | 'error';
}

export function UnifiedRiskPanel() {
    const [status, setStatus] = React.useState<RiskStatus | null>(null);
    const [loading, setLoading] = React.useState(false);
    const [error, setError] = React.useState<string | null>(null);
    const [lastUpdate, setLastUpdate] = React.useState<Date | null>(null);

    const refresh = React.useCallback(async () => {
        try {
            setLoading(true);
            setError(null);
            const data = await getWith('/api/v2/risk/unified/status', { timeout: 10000, maxRetries: 0 });
            setStatus(data);
            setLastUpdate(new Date());
        } catch (e: any) {
            setError(e?.message || 'Kunde inte hämta risk status');
        } finally {
            setLoading(false);
        }
    }, []);

    const resetGuard = React.useCallback(async (guardName: string) => {
        try {
            setLoading(true);
            await post('/api/v2/risk/unified/reset-guard', { guard_name: guardName });
            await refresh();
        } catch (e: any) {
            setError(e?.message || 'Kunde inte återställa riskvakt');
        } finally {
            setLoading(false);
        }
    }, [refresh]);

    const resetCircuitBreaker = React.useCallback(async () => {
        try {
            setLoading(true);
            await post('/api/v2/risk/unified/reset-circuit-breaker');
            await refresh();
        } catch (e: any) {
            setError(e?.message || 'Kunde inte återställa circuit breaker');
        } finally {
            setLoading(false);
        }
    }, [refresh]);

    React.useEffect(() => {
        refresh();
        const interval = setInterval(refresh, 30000); // Uppdatera var 30:e sekund
        return () => clearInterval(interval);
    }, [refresh]);

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'healthy': return '#28a745'; // Grön
            case 'degraded': return '#ffc107'; // Gul
            case 'error': return '#dc3545'; // Röd
            default: return '#6c757d'; // Grå
        }
    };

    const formatTime = (timeStr: string | null) => {
        if (!timeStr) return '-';
        try {
            return new Date(timeStr).toLocaleTimeString();
        } catch {
            return timeStr;
        }
    };

    const formatDuration = (seconds: number) => {
        if (seconds < 60) return `${seconds}s`;
        if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
        return `${Math.round(seconds / 3600)}h`;
    };

    return (
        <div style={{ border: '1px solid #e1e4e8', borderRadius: 6, padding: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <h3 style={{ margin: 0 }}>🛡️ Unified Risk Management</h3>
                <div style={{ display: 'flex', gap: 8 }}>
                    <button onClick={refresh} disabled={loading}>
                        {loading ? 'Laddar...' : '🔄 Uppdatera'}
                    </button>
                    {status?.circuit_breaker.open && (
                        <button
                            onClick={resetCircuitBreaker}
                            disabled={loading}
                            style={{ background: '#dc3545', color: 'white' }}
                        >
                            🔄 Återställ CB
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
                            <div style={{ fontSize: 12, color: '#555' }}>Övergripande Status</div>
                            <div style={{
                                fontSize: 16,
                                fontWeight: 'bold',
                                color: getStatusColor(status.overall_status)
                            }}>
                                {status.overall_status === 'healthy' ? '🟢 Friskt' :
                                 status.overall_status === 'degraded' ? '🟡 Försämrat' : '🔴 Fel'}
                            </div>
                        </div>
                        <div>
                            <div style={{ fontSize: 12, color: '#555' }}>Aktuell Equity</div>
                            <div style={{ fontSize: 16, fontWeight: 'bold', color: '#0366d6' }}>
                                ${status.current_equity.toLocaleString()}
                            </div>
                        </div>
                        <div>
                            <div style={{ fontSize: 12, color: '#555' }}>Daglig Förlust</div>
                            <div style={{
                                fontSize: 16,
                                fontWeight: 'bold',
                                color: status.daily_loss_percentage > 0 ? '#dc3545' : '#28a745'
                            }}>
                                {status.daily_loss_percentage.toFixed(2)}%
                            </div>
                        </div>
                        <div>
                            <div style={{ fontSize: 12, color: '#555' }}>Drawdown</div>
                            <div style={{
                                fontSize: 16,
                                fontWeight: 'bold',
                                color: status.drawdown_percentage > 0 ? '#dc3545' : '#28a745'
                            }}>
                                {status.drawdown_percentage.toFixed(2)}%
                            </div>
                        </div>
                        <div>
                            <div style={{ fontSize: 12, color: '#555' }}>Circuit Breaker</div>
                            <div style={{
                                fontSize: 16,
                                fontWeight: 'bold',
                                color: status.circuit_breaker.open ? '#dc3545' : '#28a745'
                            }}>
                                {status.circuit_breaker.open ? '🔴 Öppen' : '🟢 Stängd'}
                            </div>
                        </div>
                        <div>
                            <div style={{ fontSize: 12, color: '#555' }}>Trading Window</div>
                            <div style={{
                                fontSize: 16,
                                fontWeight: 'bold',
                                color: status.trade_constraints.open ? '#28a745' : '#dc3545'
                            }}>
                                {status.trade_constraints.open ? '🟢 Öppen' : '🔴 Stängd'}
                            </div>
                        </div>
                        <div>
                            <div style={{ fontSize: 12, color: '#555' }}>Senaste uppdatering</div>
                            <div style={{ fontSize: 12 }}>
                                {lastUpdate ? lastUpdate.toLocaleTimeString() : '-'}
                            </div>
                        </div>
                    </div>

                    {/* Trade Constraints */}
                    <div style={{ marginBottom: 16 }}>
                        <h4 style={{ margin: '0 0 8px' }}>Trade Constraints</h4>
                        <div style={{
                            display: 'grid',
                            gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
                            gap: 8,
                            fontSize: 12
                        }}>
                            <div style={{
                                padding: 8,
                                background: '#f6f8fa',
                                borderRadius: 4,
                                border: '1px solid #e1e4e8'
                            }}>
                                <div style={{ fontWeight: 'bold' }}>Dagliga Trades</div>
                                <div style={{ color: '#555' }}>
                                    {(() => {
                                        const t = (status as any).trade_constraints?.trades;
                                        if (!t) return '—';
                                        const max = Number(t.max_per_day ?? 0);
                                        const cnt = Number(t.count ?? 0);
                                        const rem = Math.max(0, max - cnt);
                                        return `${rem} kvar (${cnt}/${max})`;
                                    })()}
                                </div>
                            </div>
                            <div style={{
                                padding: 8,
                                background: '#f6f8fa',
                                borderRadius: 4,
                                border: '1px solid #e1e4e8'
                            }}>
                                <div style={{ fontWeight: 'bold' }}>Cooldown</div>
                                <div style={{ color: '#555' }}>
                                    {(status as any).trade_constraints?.trades?.cooldown_active ?
                                        formatDuration((status as any).trade_constraints?.trades?.cooldown_seconds ?? 0) :
                                        'Inaktiv'}
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Circuit Breaker */}
                    <div style={{ marginBottom: 16 }}>
                        <h4 style={{ margin: '0 0 8px' }}>Circuit Breaker</h4>
                        <div style={{
                            padding: 12,
                            background: status.circuit_breaker.open ? '#ffebe9' : '#f6f8fa',
                            borderRadius: 6,
                            border: `1px solid ${status.circuit_breaker.open ? '#dc3545' : '#e1e4e8'}`
                        }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <div>
                                    <div style={{ fontWeight: 'bold' }}>
                                        Status: {status.circuit_breaker.open ? 'Öppen' : 'Stängd'}
                                    </div>
                                    <div style={{ fontSize: 12, color: '#555' }}>
                                        Fel: {status.circuit_breaker.error_count}/{status.circuit_breaker.error_threshold}
                                    </div>
                                    {status.circuit_breaker.opened_at && (
                                        <div style={{ fontSize: 12, color: '#555' }}>
                                            Öppnad: {formatTime(status.circuit_breaker.opened_at)}
                                        </div>
                                    )}
                                </div>
                                {status.circuit_breaker.open && (
                                    <button
                                        onClick={resetCircuitBreaker}
                                        disabled={loading}
                                        style={{
                                            padding: '4px 8px',
                                            fontSize: 12,
                                            background: '#dc3545',
                                            color: 'white',
                                            border: 'none',
                                            borderRadius: 4
                                        }}
                                    >
                                        Återställ
                                    </button>
                                )}
                            </div>
                        </div>
                    </div>

                    {/* Risk Guards */}
                    <div>
                        <h4 style={{ margin: '0 0 8px' }}>Risk Guards</h4>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                            {Object.entries(status.guards).map(([guardName, guard]) => (
                                <div key={guardName} style={{
                                    padding: 12,
                                    background: guard.triggered ? '#ffebe9' : '#f6f8fa',
                                    borderRadius: 6,
                                    border: `1px solid ${guard.triggered ? '#dc3545' : '#e1e4e8'}`
                                }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                        <div>
                                            <div style={{ fontWeight: 'bold', textTransform: 'capitalize' }}>
                                                {guardName.replace('_', ' ')}
                                            </div>
                                            <div style={{ fontSize: 12, color: '#555' }}>
                                                Status: {guard.enabled ?
                                                    (guard.triggered ? '🔴 Triggad' : '🟢 Aktiv') :
                                                    '⚪ Inaktiverad'}
                                            </div>
                                            {guard.triggered && guard.reason && (
                                                <div style={{ fontSize: 12, color: '#dc3545', marginTop: 4 }}>
                                                    {guard.reason}
                                                </div>
                                            )}
                                            {guard.triggered_at && (
                                                <div style={{ fontSize: 12, color: '#555' }}>
                                                    Triggad: {formatTime(guard.triggered_at)}
                                                </div>
                                            )}
                                        </div>
                                        {guard.triggered && (
                                            <button
                                                onClick={() => resetGuard(guardName)}
                                                disabled={loading}
                                                style={{
                                                    padding: '4px 8px',
                                                    fontSize: 12,
                                                    background: '#28a745',
                                                    color: 'white',
                                                    border: 'none',
                                                    borderRadius: 4
                                                }}
                                            >
                                                Återställ
                                            </button>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </>
            )}
        </div>
    );
}
