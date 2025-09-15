import React from 'react';
import { getWith, post } from '@lib/api';

interface CircuitBreakerStatus {
    name: string;
    type: string;
    state: 'closed' | 'open' | 'half_open';
    failure_count: number;
    success_count: number;
    last_failure_time: string | null;
    last_success_time: string | null;
    opened_at: string | null;
    next_attempt_time: string | null;
    half_open_calls: number;
    total_requests: number;
    total_failures: number;
    total_successes: number;
    config: {
        failure_threshold: number;
        recovery_timeout: number;
        half_open_max_calls: number;
        failure_window: number;
        exponential_backoff: boolean;
        max_backoff: number;
    };
}

interface CircuitBreakerOverview {
    timestamp: string;
    circuit_breakers: Record<string, CircuitBreakerStatus>;
    total_circuit_breakers: number;
    open_circuit_breakers: number;
}

export function UnifiedCircuitBreakerPanel() {
    const [overview, setOverview] = React.useState<CircuitBreakerOverview | null>(null);
    const [loading, setLoading] = React.useState(false);
    const [error, setError] = React.useState<string | null>(null);
    const [lastUpdate, setLastUpdate] = React.useState<Date | null>(null);
    const [selectedCB, setSelectedCB] = React.useState<string>('all');

    const refresh = React.useCallback(async () => {
        try {
            setLoading(true);
            setError(null);
            const data = await getWith('/api/v2/circuit-breaker/status', { timeout: 8000, maxRetries: 0, doNotRecordCB: true });
            setOverview(data);
            setLastUpdate(new Date());
        } catch (e: any) {
            setError(e?.message || 'Kunde inte hämta circuit breaker status');
        } finally {
            setLoading(false);
        }
    }, []);

    const resetCircuitBreaker = React.useCallback(async (name: string) => {
        try {
            await post('/api/v2/circuit-breaker/reset', { name });
            await refresh();
        } catch (e: any) {
            setError(e?.message || 'Kunde inte resetta circuit breaker');
        }
    }, [refresh]);

    const recordSuccess = React.useCallback(async (name: string) => {
        try {
            setLoading(true);
            await post('/api/v2/circuit-breaker/record-success', { name });
            await refresh();
        } catch (e: any) {
            setError(e?.message || 'Kunde inte registrera success');
        } finally {
            setLoading(false);
        }
    }, [refresh]);

    const recordFailure = React.useCallback(async (name: string, errorType: string = 'generic') => {
        try {
            setLoading(true);
            await post('/api/v2/circuit-breaker/record-failure', { name, error_type: errorType });
            await refresh();
        } catch (e: any) {
            setError(e?.message || 'Kunde inte registrera failure');
        } finally {
            setLoading(false);
        }
    }, [refresh]);

    const resetCB = React.useCallback(async (name: string) => {
        try {
            setLoading(true);
            await post('/api/v2/circuit-breaker/reset', { name });
            await refresh();
        } catch (e: any) {
            setError(e?.message || 'Kunde inte återställa circuit breaker');
        } finally {
            setLoading(false);
        }
    }, [refresh]);

    const resetAllCBs = React.useCallback(async () => {
        try {
            setLoading(true);
            await post('/api/v2/circuit-breaker/reset');
            await refresh();
        } catch (e: any) {
            setError(e?.message || 'Kunde inte återställa alla circuit breakers');
        } finally {
            setLoading(false);
        }
    }, [refresh]);

    React.useEffect(() => {
        refresh();
        const interval = setInterval(refresh, 30000); // Uppdatera var 30:e sekund
        return () => clearInterval(interval);
    }, [refresh]);

    const getStateColor = (state: string) => {
        switch (state) {
            case 'closed': return '#28a745'; // Grön
            case 'open': return '#dc3545'; // Röd
            case 'half_open': return '#ffc107'; // Gul
            default: return '#6c757d'; // Grå
        }
    };

    const getStateIcon = (state: string) => {
        switch (state) {
            case 'closed': return '🟢';
            case 'open': return '🔴';
            case 'half_open': return '🟡';
            default: return '⚪';
        }
    };

    const getTypeIcon = (type: string) => {
        switch (type) {
            case 'transport': return '🌐';
            case 'trading': return '💰';
            case 'rate_limiter': return '⏱️';
            case 'custom': return '⚙️';
            default: return '🔧';
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

    const getFilteredCBs = () => {
        if (!overview) return {};
        if (selectedCB === 'all') return overview.circuit_breakers;
        
        return { [selectedCB]: overview.circuit_breakers[selectedCB] };
    };

    if (!overview) {
        return (
            <div style={{ border: '1px solid #e1e4e8', borderRadius: 6, padding: 12 }}>
                <h3 style={{ margin: 0 }}>⚡ Unified Circuit Breakers</h3>
                <div style={{ padding: 20, textAlign: 'center' }}>
                    {loading ? 'Laddar...' : 'Ingen data tillgänglig'}
                </div>
            </div>
        );
    }

    return (
        <div style={{ border: '1px solid #e1e4e8', borderRadius: 6, padding: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <h3 style={{ margin: 0 }}>⚡ Unified Circuit Breakers</h3>
                <div style={{ display: 'flex', gap: 8 }}>
                    <button onClick={refresh} disabled={loading}>
                        {loading ? 'Laddar...' : '🔄 Uppdatera'}
                    </button>
                    <button 
                        onClick={resetAllCBs} 
                        disabled={loading}
                        style={{ background: '#dc3545', color: 'white' }}
                    >
                        🔄 Återställ Alla
                    </button>
                </div>
            </div>

            {error && (
                <div style={{ background: '#ffebe9', color: '#86181d', padding: 8, borderRadius: 4, marginBottom: 12 }}>
                    {error}
                </div>
            )}

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
                    <div style={{ fontSize: 12, color: '#555' }}>Totalt Circuit Breakers</div>
                    <div style={{ fontSize: 16, fontWeight: 'bold' }}>
                        {overview.total_circuit_breakers}
                    </div>
                </div>
                <div>
                    <div style={{ fontSize: 12, color: '#555' }}>Öppna Circuit Breakers</div>
                    <div style={{ 
                        fontSize: 16, 
                        fontWeight: 'bold',
                        color: overview.open_circuit_breakers > 0 ? '#dc3545' : '#28a745'
                    }}>
                        {overview.open_circuit_breakers}
                    </div>
                </div>
                <div>
                    <div style={{ fontSize: 12, color: '#555' }}>Senaste uppdatering</div>
                    <div style={{ fontSize: 12 }}>
                        {lastUpdate ? lastUpdate.toLocaleTimeString() : '-'}
                    </div>
                </div>
            </div>

            {/* Circuit Breaker Filter */}
            <div style={{ marginBottom: 16 }}>
                <h4 style={{ margin: '0 0 8px' }}>Circuit Breakers</h4>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
                    <button
                        onClick={() => setSelectedCB('all')}
                        style={{
                            padding: '4px 8px',
                            fontSize: 12,
                            background: selectedCB === 'all' ? '#007bff' : '#f8f9fa',
                            color: selectedCB === 'all' ? 'white' : '#333',
                            border: '1px solid #dee2e6',
                            borderRadius: 4,
                            cursor: 'pointer'
                        }}
                    >
                        Alla ({overview.total_circuit_breakers})
                    </button>
                    {Object.entries(overview.circuit_breakers).map(([name, cb]) => (
                        <button
                            key={name}
                            onClick={() => setSelectedCB(name)}
                            style={{
                                padding: '4px 8px',
                                fontSize: 12,
                                background: selectedCB === name ? getStateColor(cb.state) : '#f8f9fa',
                                color: selectedCB === name ? 'white' : '#333',
                                border: '1px solid #dee2e6',
                                borderRadius: 4,
                                cursor: 'pointer'
                            }}
                        >
                            {getTypeIcon(cb.type)} {name} {getStateIcon(cb.state)}
                        </button>
                    ))}
                </div>
            </div>

            {/* Circuit Breaker Details */}
            <div>
                <h4 style={{ margin: '0 0 8px' }}>
                    {selectedCB === 'all' ? 'Alla Circuit Breakers' : `${selectedCB} Circuit Breaker`}
                </h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {Object.entries(getFilteredCBs()).map(([name, cb]) => (
                        <div key={name} style={{ 
                            padding: 12, 
                            background: '#f6f8fa', 
                            borderRadius: 6,
                            border: '1px solid #e1e4e8'
                        }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                <div style={{ flex: 1 }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                                        <span style={{ fontWeight: 'bold', fontSize: 14 }}>
                                            {getTypeIcon(cb.type)} {name}
                                        </span>
                                        <span style={{ 
                                            fontSize: 10, 
                                            padding: '2px 6px', 
                                            background: getStateColor(cb.state),
                                            color: 'white',
                                            borderRadius: 3
                                        }}>
                                            {cb.state.toUpperCase()}
                                        </span>
                                        <span style={{ 
                                            fontSize: 10, 
                                            padding: '2px 6px', 
                                            background: '#6c757d',
                                            color: 'white',
                                            borderRadius: 3
                                        }}>
                                            {cb.type}
                                        </span>
                                    </div>
                                    <div style={{ fontSize: 12, color: '#555', marginBottom: 8 }}>
                                        <div>Failures: <b>{cb.failure_count}</b> · Successes: <b>{cb.success_count}</b></div>
                                        <div>Total Requests: <b>{cb.total_requests}</b> · Total Failures: <b>{cb.total_failures}</b></div>
                                        <div>Last Failure: <b>{formatTime(cb.last_failure_time)}</b> · Last Success: <b>{formatTime(cb.last_success_time)}</b></div>
                                        {cb.opened_at && (
                                            <div>Opened At: <b>{formatTime(cb.opened_at)}</b></div>
                                        )}
                                        {cb.next_attempt_time && (
                                            <div>Next Attempt: <b>{formatTime(cb.next_attempt_time)}</b></div>
                                        )}
                                        {cb.state === 'half_open' && (
                                            <div>Half-Open Calls: <b>{cb.half_open_calls}/{cb.config.half_open_max_calls}</b></div>
                                        )}
                                    </div>
                                    <div style={{ fontSize: 11, color: '#666' }}>
                                        <div>Threshold: <b>{cb.config.failure_threshold}</b> · 
                                        Recovery: <b>{formatDuration(cb.config.recovery_timeout)}</b> · 
                                        Window: <b>{formatDuration(cb.config.failure_window)}</b></div>
                                        <div>Max Backoff: <b>{formatDuration(cb.config.max_backoff)}</b> · 
                                        Exponential: <b>{cb.config.exponential_backoff ? 'Yes' : 'No'}</b></div>
                                    </div>
                                </div>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginLeft: 12 }}>
                                    <button
                                        onClick={() => recordSuccess(name)}
                                        disabled={loading}
                                        style={{
                                            padding: '4px 8px',
                                            fontSize: 12,
                                            background: '#28a745',
                                            color: 'white',
                                            border: 'none',
                                            borderRadius: 4,
                                            cursor: 'pointer'
                                        }}
                                    >
                                        ✅ Success
                                    </button>
                                    <button
                                        onClick={() => recordFailure(name, 'test')}
                                        disabled={loading}
                                        style={{
                                            padding: '4px 8px',
                                            fontSize: 12,
                                            background: '#dc3545',
                                            color: 'white',
                                            border: 'none',
                                            borderRadius: 4,
                                            cursor: 'pointer'
                                        }}
                                    >
                                        ❌ Failure
                                    </button>
                                    <button
                                        onClick={() => resetCB(name)}
                                        disabled={loading}
                                        style={{
                                            padding: '2px 6px',
                                            fontSize: 10,
                                            background: '#6c757d',
                                            color: 'white',
                                            border: 'none',
                                            borderRadius: 3,
                                            cursor: 'pointer'
                                        }}
                                    >
                                        🔄 Reset
                                    </button>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}
