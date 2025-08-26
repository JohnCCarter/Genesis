import React from 'react';
import { get } from '../lib/api';

interface PerformanceStats {
    system: {
        cpu_percent: number;
        memory_percent: number;
        memory_available_gb: number;
        disk_percent: number;
        disk_free_gb: number;
    };
    process: {
        memory_mb: number;
        cpu_percent: number;
        active_tasks: number;
        task_types?: Record<string, number>;
    };
    cache: {
        total_entries: number;
        valid_entries: number;
        expired_entries: number;
        cache_ttl_seconds: number;
        active_locks: number;
    };
    timestamp: string;
}

export function PerformancePanel() {
    const [stats, setStats] = React.useState<PerformanceStats | null>(null);
    const [error, setError] = React.useState<string | null>(null);
    const [loading, setLoading] = React.useState(false);

    const refresh = React.useCallback(async () => {
        try {
            setLoading(true);
            setError(null);
            const data = await get('/api/v2/performance/stats');
            setStats(data);
        } catch (e: any) {
            setError(e?.message || 'Kunde inte hämta prestanda-statistik');
        } finally {
            setLoading(false);
        }
    }, []);

    React.useEffect(() => {
        refresh();
        const id = setInterval(refresh, 30000); // Uppdatera var 30:e sekund
        return () => clearInterval(id);
    }, [refresh]);

    const getStatusColor = (value: number, thresholds: { warning: number; critical: number }) => {
        if (value >= thresholds.critical) return '#d73a49'; // Röd
        if (value >= thresholds.warning) return '#f6a434'; // Orange
        return '#28a745'; // Grön
    };

    if (!stats) {
        return (
            <div style={{ border: '1px solid #e1e4e8', borderRadius: 6, padding: 12 }}>
                <h3 style={{ margin: '0 0 8px' }}>Performance Monitor</h3>
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
            <h3 style={{ margin: '0 0 8px' }}>Performance Monitor</h3>
            <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
                <button onClick={refresh} disabled={loading}>
                    {loading ? 'Uppdaterar...' : 'Uppdatera'}
                </button>
                <small style={{ opacity: 0.7 }}>
                    Senast uppdaterad: {new Date(stats.timestamp).toLocaleTimeString()}
                </small>
            </div>

            {error && (
                <div style={{ background: '#ffebe9', color: '#86181d', padding: 8, borderRadius: 4, marginBottom: 12 }}>
                    {error}
                </div>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: 16 }}>
                {/* System-resurser */}
                <div style={{ background: '#f6f8fa', padding: 12, borderRadius: 6 }}>
                    <h4 style={{ margin: '0 0 8px' }}>System</h4>
                    <div style={{ display: 'grid', gap: 4 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                            <span>CPU:</span>
                            <span style={{
                                color: getStatusColor(stats.system.cpu_percent, { warning: 70, critical: 90 }),
                                fontWeight: 'bold'
                            }}>
                                {stats.system.cpu_percent.toFixed(1)}%
                            </span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                            <span>RAM:</span>
                            <span style={{
                                color: getStatusColor(stats.system.memory_percent, { warning: 80, critical: 95 }),
                                fontWeight: 'bold'
                            }}>
                                {stats.system.memory_percent.toFixed(1)}%
                            </span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                            <span>Tillgänglig RAM:</span>
                            <span>{stats.system.memory_available_gb.toFixed(1)} GB</span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                            <span>Disk:</span>
                            <span style={{
                                color: getStatusColor(stats.system.disk_percent, { warning: 85, critical: 95 }),
                                fontWeight: 'bold'
                            }}>
                                {stats.system.disk_percent.toFixed(1)}%
                            </span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                            <span>Ledig disk:</span>
                            <span>{stats.system.disk_free_gb.toFixed(1)} GB</span>
                        </div>
                    </div>
                </div>

                {/* Process-info */}
                <div style={{ background: '#f6f8fa', padding: 12, borderRadius: 6 }}>
                    <h4 style={{ margin: '0 0 8px' }}>Process</h4>
                    <div style={{ display: 'grid', gap: 4 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                            <span>Process RAM:</span>
                            <span>{stats.process.memory_mb.toFixed(1)} MB</span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                            <span>Process CPU:</span>
                            <span style={{
                                color: getStatusColor(stats.process.cpu_percent, { warning: 50, critical: 80 }),
                                fontWeight: 'bold'
                            }}>
                                {stats.process.cpu_percent.toFixed(1)}%
                            </span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                            <span>Aktiva tasks:</span>
                            <span style={{
                                color: getStatusColor(stats.process.active_tasks, { warning: 100, critical: 200 }),
                                fontWeight: 'bold'
                            }}>
                                {stats.process.active_tasks}
                            </span>
                        </div>
                        {stats.process.task_types && (
                            <div style={{ marginTop: 8, fontSize: '0.9em' }}>
                                <div style={{ fontWeight: 'bold', marginBottom: 4 }}>Task-typer:</div>
                                {Object.entries(stats.process.task_types)
                                    .sort(([,a], [,b]) => b - a)
                                    .slice(0, 5)
                                    .map(([type, count]) => (
                                        <div key={type} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8em' }}>
                                            <span>{type}:</span>
                                            <span>{count}</span>
                                        </div>
                                    ))}
                            </div>
                        )}
                    </div>
                </div>

                {/* Cache-statistik */}
                <div style={{ background: '#f6f8fa', padding: 12, borderRadius: 6 }}>
                    <h4 style={{ margin: '0 0 8px' }}>Cache</h4>
                    <div style={{ display: 'grid', gap: 4 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                            <span>Totalt entries:</span>
                            <span>{stats.cache.total_entries}</span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                            <span>Giltiga entries:</span>
                            <span style={{ color: '#28a745', fontWeight: 'bold' }}>
                                {stats.cache.valid_entries}
                            </span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                            <span>Utgångna entries:</span>
                            <span style={{ color: '#6a737d' }}>
                                {stats.cache.expired_entries}
                            </span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                            <span>Cache TTL:</span>
                            <span>{Math.round(stats.cache.cache_ttl_seconds / 60)} min</span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                            <span>Aktiva locks:</span>
                            <span style={{
                                color: getStatusColor(stats.cache.active_locks, { warning: 10, critical: 20 }),
                                fontWeight: 'bold'
                            }}>
                                {stats.cache.active_locks}
                            </span>
                        </div>
                    </div>
                </div>
            </div>

            {/* Prestanda-varningar */}
            <div style={{ marginTop: 16 }}>
                <h4 style={{ margin: '0 0 8px' }}>Prestanda-varningar</h4>
                <div style={{ display: 'grid', gap: 4 }}>
                    {stats.system.cpu_percent > 90 && (
                        <div style={{ background: '#ffebe9', color: '#86181d', padding: 8, borderRadius: 4 }}>
                            ⚠️ Hög CPU-användning: {stats.system.cpu_percent.toFixed(1)}%
                        </div>
                    )}
                    {stats.system.memory_percent > 95 && (
                        <div style={{ background: '#ffebe9', color: '#86181d', padding: 8, borderRadius: 4 }}>
                            ⚠️ Kritisk RAM-användning: {stats.system.memory_percent.toFixed(1)}%
                        </div>
                    )}
                    {stats.process.active_tasks > 200 && (
                        <div style={{ background: '#ffebe9', color: '#86181d', padding: 8, borderRadius: 4 }}>
                            ⚠️ För många aktiva tasks: {stats.process.active_tasks}
                        </div>
                    )}
                    {stats.cache.active_locks > 20 && (
                        <div style={{ background: '#ffebe9', color: '#86181d', padding: 8, borderRadius: 4 }}>
                            ⚠️ För många cache-locks: {stats.cache.active_locks}
                        </div>
                    )}
                    {stats.system.cpu_percent <= 90 && stats.system.memory_percent <= 95 &&
                        stats.process.active_tasks <= 200 && stats.cache.active_locks <= 20 && (
                            <div style={{ background: '#d7f5dd', color: '#1b1f23', padding: 8, borderRadius: 4 }}>
                                ✅ Alla prestanda-mätvärden är normala
                            </div>
                        )}
                </div>
            </div>
        </div>
    );
}
