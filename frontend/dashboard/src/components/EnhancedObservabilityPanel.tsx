import { getWith } from '@lib/api';
import React from 'react';

interface ComprehensiveMetrics {
    timestamp: string;
    system: {
        cpu_percent: number;
        memory_percent: number;
        memory_used_gb: number;
        memory_total_gb: number;
        disk_percent: number;
        disk_used_gb: number;
        disk_total_gb: number;
        load_average: number[];
    };
    rate_limiter: {
        tokens_available: Record<string, number>;
        utilization_percent: Record<string, number>;
        requests_per_second: Record<string, number>;
        blocked_requests: Record<string, number>;
        endpoint_patterns: Record<string, any>;
    };
    exchange: {
        total_requests: number;
        failed_requests: number;
        rate_limited_requests: number;
        average_latency_ms: number;
        p95_latency_ms: number;
        p99_latency_ms: number;
        error_rate_percent: number;
    };
    circuit_breaker: {
        trading_open: boolean;
        transport_open: boolean;
        trading_errors_count: number;
        transport_errors_count: number;
    };
    websocket: {
        connected_sockets: number;
        max_sockets: number;
        active_subscriptions: number;
        max_subscriptions: number;
        messages_per_second: number;
        reconnect_count: number;
    };
    trading: {
        total_orders: number;
        successful_orders: number;
        failed_orders: number;
        order_success_rate: number;
        average_order_latency_ms: number;
        orders_per_minute: number;
    };
    summary: {
        overall_health: 'healthy' | 'warning' | 'critical' | 'error' | 'unknown';
        critical_alerts: string[];
    };
}

export function EnhancedObservabilityPanel() {
    const [metrics, setMetrics] = React.useState<ComprehensiveMetrics | null>(null);
    const [loading, setLoading] = React.useState(false);
    const [error, setError] = React.useState<string | null>(null);
    const [lastUpdate, setLastUpdate] = React.useState<Date | null>(null);

    const refresh = React.useCallback(async () => {
        try {
            setLoading(true);
            setError(null);
            const data = await getWith('/api/v2/observability/comprehensive', { timeout: 12000, maxRetries: 1 });
            setMetrics(data);
            setLastUpdate(new Date());
        } catch (e: any) {
            setError(e?.message || 'Kunde inte hämta observability metrics');
        } finally {
            setLoading(false);
        }
    }, []);

    React.useEffect(() => {
        refresh();
        const interval = setInterval(refresh, 30000); // Uppdatera var 30:e sekund
        return () => clearInterval(interval);
    }, [refresh]);

    const getHealthColor = (health: string) => {
        switch (health) {
            case 'healthy': return '#28a745'; // Grön
            case 'warning': return '#ffc107'; // Gul
            case 'critical': return '#dc3545'; // Röd
            case 'error': return '#6c757d'; // Grå
            default: return '#6c757d'; // Grå
        }
    };

    const getHealthIcon = (health: string) => {
        switch (health) {
            case 'healthy': return '🟢';
            case 'warning': return '🟡';
            case 'critical': return '🔴';
            case 'error': return '⚫';
            default: return '⚪';
        }
    };

    const formatBytes = (bytes: number) => {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    };

    const formatNumber = (num: number, decimals: number = 2) => {
        return num.toFixed(decimals);
    };

    if (!metrics) {
        return (
            <div style={{ border: '1px solid #e1e4e8', borderRadius: 6, padding: 12 }}>
                <h3 style={{ margin: 0 }}>📊 Enhanced Observability</h3>
                <div style={{ padding: 20, textAlign: 'center' }}>
                    {loading ? 'Laddar...' : 'Ingen data tillgänglig'}
                </div>
            </div>
        );
    }

    return (
        <div style={{ border: '1px solid #e1e4e8', borderRadius: 6, padding: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <h3 style={{ margin: 0 }}>📊 Enhanced Observability</h3>
                <div style={{ display: 'flex', gap: 8 }}>
                    <button onClick={refresh} disabled={loading}>
                        {loading ? 'Laddar...' : '🔄 Uppdatera'}
                    </button>
                </div>
            </div>

            {error && (
                <div style={{ background: '#ffebe9', color: '#86181d', padding: 8, borderRadius: 4, marginBottom: 12 }}>
                    {error}
                </div>
            )}

            {/* Övergripande hälsa */}
            <div style={{ 
                padding: 12, 
                background: '#f6f8fa', 
                borderRadius: 6,
                border: '1px solid #e1e4e8',
                marginBottom: 16
            }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                        <div style={{ fontSize: 16, fontWeight: 'bold' }}>
                            {getHealthIcon(metrics.summary.overall_health)} 
                            Övergripande Hälsa: {metrics.summary.overall_health.toUpperCase()}
                        </div>
                        <div style={{ fontSize: 12, color: '#555' }}>
                            Senaste uppdatering: {lastUpdate ? lastUpdate.toLocaleTimeString() : '-'}
                        </div>
                    </div>
                    <div style={{ 
                        fontSize: 12, 
                        color: getHealthColor(metrics.summary.overall_health),
                        fontWeight: 'bold'
                    }}>
                        {metrics.summary.critical_alerts.length} alerts
                    </div>
                </div>
                
                {metrics.summary.critical_alerts.length > 0 && (
                    <div style={{ marginTop: 8 }}>
                        <div style={{ fontSize: 12, fontWeight: 'bold', marginBottom: 4 }}>Kritiska Alerts:</div>
                        {metrics.summary.critical_alerts.map((alert, index) => (
                            <div key={index} style={{ 
                                fontSize: 11, 
                                color: '#dc3545', 
                                padding: '2px 0',
                                borderLeft: '3px solid #dc3545',
                                paddingLeft: 8
                            }}>
                                {alert}
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* System Metrics */}
            <div style={{ marginBottom: 16 }}>
                <h4 style={{ margin: '0 0 8px' }}>🖥️ System Resurser</h4>
                <div style={{ 
                    display: 'grid', 
                    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
                    gap: 8,
                    fontSize: 12
                }}>
                    <div style={{ 
                        padding: 8, 
                        background: '#f6f8fa', 
                        borderRadius: 4,
                        border: '1px solid #e1e4e8'
                    }}>
                        <div style={{ fontWeight: 'bold' }}>CPU</div>
                        <div style={{ color: '#555' }}>
                            {formatNumber(metrics.system.cpu_percent)}%
                        </div>
                    </div>
                    <div style={{ 
                        padding: 8, 
                        background: '#f6f8fa', 
                        borderRadius: 4,
                        border: '1px solid #e1e4e8'
                    }}>
                        <div style={{ fontWeight: 'bold' }}>RAM</div>
                        <div style={{ color: '#555' }}>
                            {formatNumber(metrics.system.memory_percent)}% ({formatNumber(metrics.system.memory_used_gb)} GB)
                        </div>
                    </div>
                    <div style={{ 
                        padding: 8, 
                        background: '#f6f8fa', 
                        borderRadius: 4,
                        border: '1px solid #e1e4e8'
                    }}>
                        <div style={{ fontWeight: 'bold' }}>Disk</div>
                        <div style={{ color: '#555' }}>
                            {formatNumber(metrics.system.disk_percent)}% ({formatNumber(metrics.system.disk_used_gb)} GB)
                        </div>
                    </div>
                    <div style={{ 
                        padding: 8, 
                        background: '#f6f8fa', 
                        borderRadius: 4,
                        border: '1px solid #e1e4e8'
                    }}>
                        <div style={{ fontWeight: 'bold' }}>Load Average</div>
                        <div style={{ color: '#555' }}>
                            {metrics.system.load_average.map(load => formatNumber(load, 2)).join(', ')}
                        </div>
                    </div>
                </div>
            </div>

            {/* Exchange Metrics */}
            <div style={{ marginBottom: 16 }}>
                <h4 style={{ margin: '0 0 8px' }}>📡 Exchange API</h4>
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
                        <div style={{ fontWeight: 'bold' }}>Total Requests</div>
                        <div style={{ color: '#555' }}>
                            {metrics.exchange.total_requests.toLocaleString()}
                        </div>
                    </div>
                    <div style={{ 
                        padding: 8, 
                        background: '#f6f8fa', 
                        borderRadius: 4,
                        border: '1px solid #e1e4e8'
                    }}>
                        <div style={{ fontWeight: 'bold' }}>Error Rate</div>
                        <div style={{ color: '#555' }}>
                            {formatNumber(metrics.exchange.error_rate_percent)}%
                        </div>
                    </div>
                    <div style={{ 
                        padding: 8, 
                        background: '#f6f8fa', 
                        borderRadius: 4,
                        border: '1px solid #e1e4e8'
                    }}>
                        <div style={{ fontWeight: 'bold' }}>Avg Latency</div>
                        <div style={{ color: '#555' }}>
                            {formatNumber(metrics.exchange.average_latency_ms)} ms
                        </div>
                    </div>
                    <div style={{ 
                        padding: 8, 
                        background: '#f6f8fa', 
                        borderRadius: 4,
                        border: '1px solid #e1e4e8'
                    }}>
                        <div style={{ fontWeight: 'bold' }}>P95 Latency</div>
                        <div style={{ color: '#555' }}>
                            {formatNumber(metrics.exchange.p95_latency_ms)} ms
                        </div>
                    </div>
                    <div style={{ 
                        padding: 8, 
                        background: '#f6f8fa', 
                        borderRadius: 4,
                        border: '1px solid #e1e4e8'
                    }}>
                        <div style={{ fontWeight: 'bold' }}>Rate Limited</div>
                        <div style={{ color: '#555' }}>
                            {metrics.exchange.rate_limited_requests.toLocaleString()}
                        </div>
                    </div>
                </div>
            </div>

            {/* Trading Metrics */}
            <div style={{ marginBottom: 16 }}>
                <h4 style={{ margin: '0 0 8px' }}>💰 Trading</h4>
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
                        <div style={{ fontWeight: 'bold' }}>Total Orders</div>
                        <div style={{ color: '#555' }}>
                            {metrics.trading.total_orders.toLocaleString()}
                        </div>
                    </div>
                    <div style={{ 
                        padding: 8, 
                        background: '#f6f8fa', 
                        borderRadius: 4,
                        border: '1px solid #e1e4e8'
                    }}>
                        <div style={{ fontWeight: 'bold' }}>Success Rate</div>
                        <div style={{ color: '#555' }}>
                            {formatNumber(metrics.trading.order_success_rate)}%
                        </div>
                    </div>
                    <div style={{ 
                        padding: 8, 
                        background: '#f6f8fa', 
                        borderRadius: 4,
                        border: '1px solid #e1e4e8'
                    }}>
                        <div style={{ fontWeight: 'bold' }}>Avg Order Latency</div>
                        <div style={{ color: '#555' }}>
                            {formatNumber(metrics.trading.average_order_latency_ms)} ms
                        </div>
                    </div>
                    <div style={{ 
                        padding: 8, 
                        background: '#f6f8fa', 
                        borderRadius: 4,
                        border: '1px solid #e1e4e8'
                    }}>
                        <div style={{ fontWeight: 'bold' }}>Failed Orders</div>
                        <div style={{ color: '#555' }}>
                            {metrics.trading.failed_orders.toLocaleString()}
                        </div>
                    </div>
                </div>
            </div>

            {/* WebSocket Metrics */}
            <div style={{ marginBottom: 16 }}>
                <h4 style={{ margin: '0 0 8px' }}>🔌 WebSocket</h4>
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
                        <div style={{ fontWeight: 'bold' }}>Connected Sockets</div>
                        <div style={{ color: '#555' }}>
                            {metrics.websocket.connected_sockets}/{metrics.websocket.max_sockets}
                        </div>
                    </div>
                    <div style={{ 
                        padding: 8, 
                        background: '#f6f8fa', 
                        borderRadius: 4,
                        border: '1px solid #e1e4e8'
                    }}>
                        <div style={{ fontWeight: 'bold' }}>Active Subscriptions</div>
                        <div style={{ color: '#555' }}>
                            {metrics.websocket.active_subscriptions}/{metrics.websocket.max_subscriptions}
                        </div>
                    </div>
                    <div style={{ 
                        padding: 8, 
                        background: '#f6f8fa', 
                        borderRadius: 4,
                        border: '1px solid #e1e4e8'
                    }}>
                        <div style={{ fontWeight: 'bold' }}>Messages/sec</div>
                        <div style={{ color: '#555' }}>
                            {formatNumber(metrics.websocket.messages_per_second)}
                        </div>
                    </div>
                    <div style={{ 
                        padding: 8, 
                        background: '#f6f8fa', 
                        borderRadius: 4,
                        border: '1px solid #e1e4e8'
                    }}>
                        <div style={{ fontWeight: 'bold' }}>Reconnects</div>
                        <div style={{ color: '#555' }}>
                            {metrics.websocket.reconnect_count}
                        </div>
                    </div>
                </div>
            </div>

            {/* Circuit Breaker Status */}
            <div>
                <h4 style={{ margin: '0 0 8px' }}>⚡ Circuit Breakers</h4>
                <div style={{ 
                    display: 'grid', 
                    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
                    gap: 8,
                    fontSize: 12
                }}>
                    <div style={{ 
                        padding: 8, 
                        background: metrics.circuit_breaker.trading_open ? '#ffebe9' : '#f6f8fa', 
                        borderRadius: 4,
                        border: `1px solid ${metrics.circuit_breaker.trading_open ? '#dc3545' : '#e1e4e8'}`
                    }}>
                        <div style={{ fontWeight: 'bold' }}>Trading Circuit Breaker</div>
                        <div style={{ 
                            color: metrics.circuit_breaker.trading_open ? '#dc3545' : '#28a745',
                            fontWeight: 'bold'
                        }}>
                            {metrics.circuit_breaker.trading_open ? '🔴 Öppen' : '🟢 Stängd'}
                        </div>
                        <div style={{ color: '#555' }}>
                            Fel: {metrics.circuit_breaker.trading_errors_count}
                        </div>
                    </div>
                    <div style={{ 
                        padding: 8, 
                        background: metrics.circuit_breaker.transport_open ? '#ffebe9' : '#f6f8fa', 
                        borderRadius: 4,
                        border: `1px solid ${metrics.circuit_breaker.transport_open ? '#dc3545' : '#e1e4e8'}`
                    }}>
                        <div style={{ fontWeight: 'bold' }}>Transport Circuit Breaker</div>
                        <div style={{ 
                            color: metrics.circuit_breaker.transport_open ? '#dc3545' : '#28a745',
                            fontWeight: 'bold'
                        }}>
                            {metrics.circuit_breaker.transport_open ? '🔴 Öppen' : '🟢 Stängd'}
                        </div>
                        <div style={{ color: '#555' }}>
                            Fel: {metrics.circuit_breaker.transport_errors_count}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
