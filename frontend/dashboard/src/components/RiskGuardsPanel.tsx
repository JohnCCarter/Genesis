import React from 'react';
import { get, post } from '@lib/api';

interface RiskGuard {
    enabled: boolean;
    percentage?: number;
    triggered?: boolean;
    triggered_at?: string;
    reason?: string;
    cooldown_hours?: number;
    max_open_positions?: number;
    max_position_size_percentage?: number;
    max_total_exposure_percentage?: number;
    max_drawdown_percentage?: number;
    max_daily_volatility?: number;
    pause_on_high_volatility?: boolean;
}

interface RiskGuardsStatus {
    current_equity: number;
    daily_loss_percentage: number;
    drawdown_percentage: number;
    guards: {
        max_daily_loss: RiskGuard;
        kill_switch: RiskGuard;
        exposure_limits: RiskGuard;
        volatility_guards: RiskGuard;
    };
    last_updated: string;
}

export function RiskGuardsPanel() {
    const [status, setStatus] = React.useState<RiskGuardsStatus | null>(null);
    const [error, setError] = React.useState<string | null>(null);
    const [loading, setLoading] = React.useState(false);

    const refresh = React.useCallback(async () => {
        try {
            setLoading(true);
            setError(null);
            const data = await get('/api/v2/risk/guards/status');
            setStatus(data);
        } catch (e: any) {
            setError(e?.message || 'Kunde inte hämta risk guards status');
        } finally {
            setLoading(false);
        }
    }, []);

    React.useEffect(() => {
        refresh();
        const id = setInterval(refresh, 30000); // Uppdatera var 30:e sekund
        return () => clearInterval(id);
    }, [refresh]);

    const resetGuard = async (guardName: string) => {
        try {
            setLoading(true);
            await post('/api/v2/risk/guards/reset', { guard_name: guardName });
            await refresh();
        } catch (e: any) {
            setError(e?.message || `Kunde inte återställa ${guardName}`);
        } finally {
            setLoading(false);
        }
    };

    const updateGuardConfig = async (guardName: string, config: Partial<RiskGuard>) => {
        try {
            setLoading(true);
            await post('/api/v2/risk/guards/config', { guard_name: guardName, config });
            await refresh();
        } catch (e: any) {
            setError(e?.message || `Kunde inte uppdatera ${guardName}`);
        } finally {
            setLoading(false);
        }
    };

    const getStatusColor = (triggered: boolean | undefined) => {
        if (triggered) return '#d73a49'; // Röd
        return '#28a745'; // Grön
    };

    const getStatusText = (guard: RiskGuard) => {
        if (!guard.enabled) return 'Inaktiverad';
        if (guard.triggered) return 'Triggad';
        return 'Aktiv';
    };

    if (!status) {
        return (
            <div style={{ border: '1px solid #e1e4e8', borderRadius: 6, padding: 12 }}>
                <h3 style={{ margin: '0 0 8px' }}>Risk Guards</h3>
                {loading ? (
                    <div>Laddar...</div>
                ) : (
                    <div>Ingen data tillgänglig</div>
                )}
            </div>
        );
    }

    return (
        <div style={{ border: '1px solid #e1e4e8', borderRadius: 6, padding: 12 }}>
            <h3 style={{ margin: '0 0 8px' }}>Risk Guards</h3>

            {error && (
                <div style={{ background: '#ffebe9', color: '#86181d', padding: 8, borderRadius: 4, marginBottom: 12 }}>
                    {error}
                </div>
            )}

            {/* Översikt */}
            <div style={{ marginBottom: 16 }}>
                <h4 style={{ margin: '0 0 8px' }}>Översikt</h4>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 8 }}>
                    <div style={{ background: '#f6f8fa', padding: 8, borderRadius: 4 }}>
                        <div style={{ fontSize: '0.9em', color: '#586069' }}>Aktuell Equity</div>
                        <div style={{ fontSize: '1.2em', fontWeight: 'bold' }}>
                            ${status.current_equity.toLocaleString()}
                        </div>
                    </div>
                    <div style={{ background: '#f6f8fa', padding: 8, borderRadius: 4 }}>
                        <div style={{ fontSize: '0.9em', color: '#586069' }}>Daglig Förlust</div>
                        <div style={{
                            fontSize: '1.2em',
                            fontWeight: 'bold',
                            color: status.daily_loss_percentage > 0 ? '#d73a49' : '#28a745'
                        }}>
                            {status.daily_loss_percentage.toFixed(2)}%
                        </div>
                    </div>
                    <div style={{ background: '#f6f8fa', padding: 8, borderRadius: 4 }}>
                        <div style={{ fontSize: '0.9em', color: '#586069' }}>Drawdown</div>
                        <div style={{
                            fontSize: '1.2em',
                            fontWeight: 'bold',
                            color: status.drawdown_percentage > 0 ? '#d73a49' : '#28a745'
                        }}>
                            {status.drawdown_percentage.toFixed(2)}%
                        </div>
                    </div>
                </div>
            </div>

            {/* Risk Guards */}
            <div style={{ display: 'grid', gap: 12 }}>
                {/* Max Daily Loss */}
                <div style={{ border: '1px solid #e1e4e8', borderRadius: 4, padding: 12 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                        <h4 style={{ margin: 0 }}>Max Daily Loss</h4>
                        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                            <span style={{
                                background: getStatusColor(status.guards.max_daily_loss.triggered),
                                color: 'white',
                                padding: '2px 8px',
                                borderRadius: 12,
                                fontSize: '0.8em'
                            }}>
                                {getStatusText(status.guards.max_daily_loss)}
                            </span>
                            {status.guards.max_daily_loss.triggered && (
                                <button
                                    onClick={() => resetGuard('max_daily_loss')}
                                    disabled={loading}
                                    style={{
                                        background: '#0366d6',
                                        color: 'white',
                                        border: 'none',
                                        padding: '4px 8px',
                                        borderRadius: 4,
                                        cursor: loading ? 'not-allowed' : 'pointer'
                                    }}
                                >
                                    Återställ
                                </button>
                            )}
                        </div>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 8, fontSize: '0.9em' }}>
                        <div>
                            <strong>Gräns:</strong> {status.guards.max_daily_loss.percentage}%
                        </div>
                        <div>
                            <strong>Cooldown:</strong> {status.guards.max_daily_loss.cooldown_hours}h
                        </div>
                        {status.guards.max_daily_loss.triggered_at && (
                            <div>
                                <strong>Triggad:</strong> {new Date(status.guards.max_daily_loss.triggered_at).toLocaleString()}
                            </div>
                        )}
                    </div>
                </div>

                {/* Kill Switch */}
                <div style={{ border: '1px solid #e1e4e8', borderRadius: 4, padding: 12 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                        <h4 style={{ margin: 0 }}>Kill Switch</h4>
                        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                            <span style={{
                                background: getStatusColor(status.guards.kill_switch.triggered),
                                color: 'white',
                                padding: '2px 8px',
                                borderRadius: 12,
                                fontSize: '0.8em'
                            }}>
                                {getStatusText(status.guards.kill_switch)}
                            </span>
                            {status.guards.kill_switch.triggered && (
                                <button
                                    onClick={() => resetGuard('kill_switch')}
                                    disabled={loading}
                                    style={{
                                        background: '#0366d6',
                                        color: 'white',
                                        border: 'none',
                                        padding: '4px 8px',
                                        borderRadius: 4,
                                        cursor: loading ? 'not-allowed' : 'pointer'
                                    }}
                                >
                                    Återställ
                                </button>
                            )}
                        </div>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 8, fontSize: '0.9em' }}>
                        <div>
                            <strong>Max Drawdown:</strong> {status.guards.kill_switch.max_drawdown_percentage}%
                        </div>
                        <div>
                            <strong>Cooldown:</strong> {status.guards.kill_switch.cooldown_hours}h
                        </div>
                        {status.guards.kill_switch.reason && (
                            <div style={{ gridColumn: '1 / -1' }}>
                                <strong>Orsak:</strong> {status.guards.kill_switch.reason}
                            </div>
                        )}
                    </div>
                </div>

                {/* Exposure Limits */}
                <div style={{ border: '1px solid #e1e4e8', borderRadius: 4, padding: 12 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                        <h4 style={{ margin: 0 }}>Exposure Limits</h4>
                        <span style={{
                            background: getStatusColor(false),
                            color: 'white',
                            padding: '2px 8px',
                            borderRadius: 12,
                            fontSize: '0.8em'
                        }}>
                            {getStatusText(status.guards.exposure_limits)}
                        </span>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 8, fontSize: '0.9em' }}>
                        <div>
                            <strong>Max Positioner:</strong> {status.guards.exposure_limits.max_open_positions}
                        </div>
                        <div>
                            <strong>Max Position Size:</strong> {status.guards.exposure_limits.max_position_size_percentage}%
                        </div>
                        <div>
                            <strong>Max Total Exposure:</strong> {status.guards.exposure_limits.max_total_exposure_percentage}%
                        </div>
                    </div>
                </div>

                {/* Volatility Guards */}
                <div style={{ border: '1px solid #e1e4e8', borderRadius: 4, padding: 12 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                        <h4 style={{ margin: 0 }}>Volatility Guards</h4>
                        <span style={{
                            background: getStatusColor(false),
                            color: 'white',
                            padding: '2px 8px',
                            borderRadius: 12,
                            fontSize: '0.8em'
                        }}>
                            {getStatusText(status.guards.volatility_guards)}
                        </span>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 8, fontSize: '0.9em' }}>
                        <div>
                            <strong>Max Daglig Volatilitet:</strong> {status.guards.volatility_guards.max_daily_volatility}%
                        </div>
                        <div>
                            <strong>Paus vid Hög Volatilitet:</strong> {status.guards.volatility_guards.pause_on_high_volatility ? 'Ja' : 'Nej'}
                        </div>
                    </div>
                </div>
            </div>

            {/* Senast uppdaterad */}
            <div style={{ marginTop: 12, fontSize: '0.8em', color: '#586069', textAlign: 'center' }}>
                Senast uppdaterad: {new Date(status.last_updated).toLocaleString()}
            </div>
        </div>
    );
}
