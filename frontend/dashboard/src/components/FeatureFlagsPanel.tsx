import { getWith, post } from '@lib/api';
import React from 'react';

interface FeatureFlag {
    value: any;
    default_value: any;
    description: string;
    category: string;
    requires_restart: boolean;
    last_updated: string | null;
}

interface FeatureFlagsStatus {
    timestamp: string;
    total_flags: number;
    categories: string[];
    flags: Record<string, FeatureFlag>;
    ui_capabilities: Record<string, any>;
}

export function FeatureFlagsPanel() {
    const [status, setStatus] = React.useState<FeatureFlagsStatus | null>(null);
    const [loading, setLoading] = React.useState(false);
    const [error, setError] = React.useState<string | null>(null);
    const [lastUpdate, setLastUpdate] = React.useState<Date | null>(null);
    const [selectedCategory, setSelectedCategory] = React.useState<string>('all');

    const refresh = React.useCallback(async () => {
        try {
            setLoading(true);
            setError(null);
            const data = await getWith('/api/v2/feature-flags/status', { timeout: 8000, maxRetries: 0, doNotRecordCB: true });
            setStatus(data);
            setLastUpdate(new Date());
        } catch (e: any) {
            setError(e?.message || 'Kunde inte hämta feature flags status');
        } finally {
            setLoading(false);
        }
    }, []);

    const setFlag = React.useCallback(async (name: string, value: any) => {
        try {
            setLoading(true);
            await post('/api/v2/feature-flags/set', { name, value });
            await refresh();
        } catch (e: any) {
            setError(e?.message || 'Kunde inte uppdatera feature flag');
        } finally {
            setLoading(false);
        }
    }, [refresh]);

    const resetFlag = React.useCallback(async (name: string) => {
        try {
            setLoading(true);
            await post('/api/v2/feature-flags/reset', { name });
            await refresh();
        } catch (e: any) {
            setError(e?.message || 'Kunde inte återställa feature flag');
        } finally {
            setLoading(false);
        }
    }, [refresh]);

    const resetAllFlags = React.useCallback(async () => {
        try {
            setLoading(true);
            await post('/api/v2/feature-flags/reset');
            await refresh();
        } catch (e: any) {
            setError(e?.message || 'Kunde inte återställa alla feature flags');
        } finally {
            setLoading(false);
        }
    }, [refresh]);

    React.useEffect(() => {
        refresh();
        const interval = setInterval(refresh, 60000); // Uppdatera var minut
        return () => clearInterval(interval);
    }, [refresh]);

    const getCategoryColor = (category: string) => {
        switch (category) {
            case 'trading': return '#dc3545'; // Röd
            case 'probability': return '#6f42c1'; // Lila
            case 'websocket': return '#17a2b8'; // Blå
            case 'validation': return '#fd7e14'; // Orange
            case 'scheduler': return '#28a745'; // Grön
            case 'ui': return '#ffc107'; // Gul
            case 'debug': return '#6c757d'; // Grå
            case 'marketdata': return '#20c997'; // Turkos
            case 'rate_limit': return '#e83e8c'; // Rosa
            default: return '#6c757d'; // Grå
        }
    };

    const formatValue = (value: any) => {
        if (typeof value === 'boolean') {
            return value ? '🟢 Aktiverad' : '🔴 Inaktiverad';
        }
        if (typeof value === 'string') {
            return value;
        }
        return String(value);
    };

    const formatTime = (timeStr: string | null) => {
        if (!timeStr) return '-';
        try {
            return new Date(timeStr).toLocaleTimeString();
        } catch {
            return timeStr;
        }
    };

    const getFilteredFlags = () => {
        if (!status) return {};
        if (selectedCategory === 'all') return status.flags;

        const filtered: Record<string, FeatureFlag> = {};
        for (const [name, flag] of Object.entries(status.flags)) {
            if (flag.category === selectedCategory) {
                filtered[name] = flag;
            }
        }
        return filtered;
    };

    // Quick toggle flags - most important ones
    const quickToggleFlags = [
        'dry_run_enabled',
        'trading_paused',
        'autotrade_enabled',
        'ws_strategy_enabled',
        'prob_model_enabled'
    ];

    return (
        <div style={{ border: '1px solid #e1e4e8', borderRadius: 6, padding: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <h3 style={{ margin: 0 }}>🚩 Feature Flags</h3>
                <div style={{ display: 'flex', gap: 8 }}>
                    <button onClick={refresh} disabled={loading}>
                        {loading ? 'Laddar...' : '🔄 Uppdatera'}
                    </button>
                    <button
                        onClick={resetAllFlags}
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

            {status && (
                <>
                    {/* Quick Toggle Section */}
                    <div style={{
                        background: '#f8f9fa',
                        padding: 16,
                        borderRadius: 8,
                        marginBottom: 20,
                        border: '1px solid #e9ecef'
                    }}>
                        <h4 style={{ margin: '0 0 12px 0', fontSize: '16px', color: '#495057' }}>
                            ⚡ Quick Controls
                        </h4>
                        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                            {quickToggleFlags.map(flagName => {
                                const flag = status.flags[flagName];
                                if (!flag) return null;

                                const isEnabled = Boolean(flag.value);
                                const label = flagName.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());

                                return (
                                    <button
                                        key={flagName}
                                        onClick={() => setFlag(flagName, !isEnabled)}
                                        disabled={loading}
                                        style={{
                                            padding: '8px 12px',
                                            background: isEnabled ? '#28a745' : '#6c757d',
                                            color: 'white',
                                            border: 'none',
                                            borderRadius: '6px',
                                            cursor: loading ? 'not-allowed' : 'pointer',
                                            fontSize: '12px',
                                            fontWeight: '500',
                                            opacity: loading ? 0.6 : 1,
                                            transition: 'all 0.2s ease',
                                        }}
                                    >
                                        {isEnabled ? '✅' : '❌'} {label}
                                    </button>
                                );
                            })}
                        </div>
                    </div>

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
                            <div style={{ fontSize: 12, color: '#555' }}>Totalt Flags</div>
                            <div style={{ fontSize: 16, fontWeight: 'bold' }}>
                                {status.total_flags}
                            </div>
                        </div>
                        <div>
                            <div style={{ fontSize: 12, color: '#555' }}>Kategorier</div>
                            <div style={{ fontSize: 16, fontWeight: 'bold' }}>
                                {status.categories.length}
                            </div>
                        </div>
                        <div>
                            <div style={{ fontSize: 12, color: '#555' }}>Senaste uppdatering</div>
                            <div style={{ fontSize: 12 }}>
                                {lastUpdate ? lastUpdate.toLocaleTimeString() : '-'}
                            </div>
                        </div>
                    </div>

                    {/* Kategori-filter */}
                    <div style={{ marginBottom: 16 }}>
                        <h4 style={{ margin: '0 0 8px' }}>Kategorier</h4>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
                            <button
                                onClick={() => setSelectedCategory('all')}
                                style={{
                                    padding: '4px 8px',
                                    fontSize: 12,
                                    background: selectedCategory === 'all' ? '#007bff' : '#f8f9fa',
                                    color: selectedCategory === 'all' ? 'white' : '#333',
                                    border: '1px solid #dee2e6',
                                    borderRadius: 4,
                                    cursor: 'pointer'
                                }}
                            >
                                Alla ({status.total_flags})
                            </button>
                            {status.categories.map(category => {
                                const count = Object.values(status.flags).filter(f => f.category === category).length;
                                return (
                                    <button
                                        key={category}
                                        onClick={() => setSelectedCategory(category)}
                                        style={{
                                            padding: '4px 8px',
                                            fontSize: 12,
                                            background: selectedCategory === category ? getCategoryColor(category) : '#f8f9fa',
                                            color: selectedCategory === category ? 'white' : '#333',
                                            border: '1px solid #dee2e6',
                                            borderRadius: 4,
                                            cursor: 'pointer'
                                        }}
                                    >
                                        {category} ({count})
                                    </button>
                                );
                            })}
                        </div>
                    </div>

                    {/* Feature Flags */}
                    <div>
                        <h4 style={{ margin: '0 0 8px' }}>
                            {selectedCategory === 'all' ? 'Alla Feature Flags' : `${selectedCategory} Flags`}
                        </h4>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                            {Object.entries(getFilteredFlags()).map(([name, flag]) => (
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
                                                    {name}
                                                </span>
                                                <span style={{
                                                    fontSize: 10,
                                                    padding: '2px 6px',
                                                    background: getCategoryColor(flag.category),
                                                    color: 'white',
                                                    borderRadius: 3
                                                }}>
                                                    {flag.category}
                                                </span>
                                                {flag.requires_restart && (
                                                    <span style={{
                                                        fontSize: 10,
                                                        padding: '2px 6px',
                                                        background: '#ffc107',
                                                        color: '#333',
                                                        borderRadius: 3
                                                    }}>
                                                        Restart
                                                    </span>
                                                )}
                                            </div>
                                            <div style={{ fontSize: 12, color: '#555', marginBottom: 8 }}>
                                                {flag.description}
                                            </div>
                                            <div style={{ fontSize: 12, color: '#555' }}>
                                                <div>Värde: {formatValue(flag.value)}</div>
                                                <div>Default: {formatValue(flag.default_value)}</div>
                                                {flag.last_updated && (
                                                    <div>Senast uppdaterad: {formatTime(flag.last_updated)}</div>
                                                )}
                                            </div>
                                        </div>
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginLeft: 12 }}>
                                            {typeof flag.value === 'boolean' ? (
                                                <button
                                                    onClick={() => setFlag(name, !flag.value)}
                                                    disabled={loading}
                                                    style={{
                                                        padding: '4px 8px',
                                                        fontSize: 12,
                                                        background: flag.value ? '#dc3545' : '#28a745',
                                                        color: 'white',
                                                        border: 'none',
                                                        borderRadius: 4,
                                                        cursor: 'pointer'
                                                    }}
                                                >
                                                    {flag.value ? 'Inaktivera' : 'Aktivera'}
                                                </button>
                                            ) : (
                                                <div style={{ fontSize: 12, color: '#555' }}>
                                                    {formatValue(flag.value)}
                                                </div>
                                            )}
                                            {flag.value !== flag.default_value && (
                                                <button
                                                    onClick={() => resetFlag(name)}
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
                                                    Återställ
                                                </button>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* UI Capabilities */}
                    <div style={{ marginTop: 16 }}>
                        <h4 style={{ margin: '0 0 8px' }}>UI Capabilities</h4>
                        <div style={{
                            padding: 12,
                            background: '#f6f8fa',
                            borderRadius: 6,
                            border: '1px solid #e1e4e8',
                            fontSize: 12
                        }}>
                            <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
                                {JSON.stringify(status.ui_capabilities, null, 2)}
                            </pre>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
}
