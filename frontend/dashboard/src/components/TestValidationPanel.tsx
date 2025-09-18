import React from 'react';
import { get, post } from '@lib/api';
import { Sparkline } from './Sparkline';
import { JsonTree } from './JsonTree';

type TestType = 'probability' | 'strategy' | 'backtest';

export function TestValidationPanel() {
    const [activeTest, setActiveTest] = React.useState<TestType>('probability');
    const [symbol, setSymbol] = React.useState('tBTCUSD');
    const [timeframe, setTimeframe] = React.useState('1m');
    const [limit, setLimit] = React.useState(600);
    const [maxSamples, setMaxSamples] = React.useState(500);
    const [initialCapital, setInitialCapital] = React.useState(10000);
    const [loading, setLoading] = React.useState(false);
    const [result, setResult] = React.useState<any>(null);
    const [error, setError] = React.useState<string | null>(null);
    const [validationHistory, setValidationHistory] = React.useState<any[]>([]);

    const runTest = React.useCallback(async () => {
        try {
            setLoading(true);
            setError(null);

            let endpoint = '';
            let params: any = {
                symbol,
                timeframe,
                limit,
                force_refresh: true,
            };

            switch (activeTest) {
                case 'probability':
                    endpoint = '/api/v2/validation/probability';
                    params.max_samples = maxSamples;
                    break;
                case 'strategy':
                    endpoint = '/api/v2/validation/strategy';
                    params.strategy_params = {
                        adx_threshold: 25,
                        ema_period: 20,
                        risk_per_trade: 0.02,
                    };
                    break;
                case 'backtest':
                    endpoint = '/api/v2/validation/backtest';
                    params.initial_capital = initialCapital;
                    params.strategy_params = {
                        position_size: 0.1,
                        stop_loss: 0.02,
                        take_profit: 0.04,
                    };
                    break;
            }

            const res = await post(endpoint, params);
            setResult(res);

            // Uppdatera validation history
            await refreshValidationHistory();

        } catch (e: any) {
            setError(e?.message || 'Test misslyckades');
        } finally {
            setLoading(false);
        }
    }, [activeTest, symbol, timeframe, limit, maxSamples, initialCapital]);

    const refreshValidationHistory = React.useCallback(async () => {
        try {
            const data = await get('/api/v2/validation/history');
            setValidationHistory(data.validation_history || []);
        } catch (e: any) {
            console.error('Kunde inte hämta validation history:', e);
        }
    }, []);

    React.useEffect(() => {
        refreshValidationHistory();
    }, [refreshValidationHistory]);

    const clearResult = React.useCallback(() => {
        setResult(null);
        setError(null);
    }, []);

    const formatNumber = (num: number, decimals: number = 4) => {
        return num.toFixed(decimals);
    };

    const formatTime = (timeStr: string) => {
        try {
            return new Date(timeStr).toLocaleTimeString();
        } catch {
            return timeStr;
        }
    };

    const getTestIcon = (testType: string) => {
        switch (testType) {
            case 'probability_validation': return '🧠';
            case 'strategy_validation': return '📈';
            case 'backtest': return '⏰';
            default: return '🧪';
        }
    };

    const getSuccessColor = (success: boolean) => {
        return success ? '#28a745' : '#dc3545';
    };

    // Härled simpla serier om resultatet innehåller rolling/series
    const brierSeries = React.useMemo(() => {
        if (!result || activeTest !== 'probability') return [];
        const rolling = result?.rolling_metrics || result?.metrics?.rolling || {};
        const series: any[] = Array.isArray(rolling) ? rolling : (Object.values(rolling)[0] as any[] || []);
        return (series || []).map((x: any) => Number(x?.brier || 0)).filter((n: number) => Number.isFinite(n));
    }, [result, activeTest]);

    return (
        <div style={{ border: '1px solid #e1e4e8', borderRadius: 6, padding: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <h3 style={{ margin: 0 }}>🧪 Test & Validation</h3>
                <div style={{ display: 'flex', gap: 8 }}>
                    <button onClick={runTest} disabled={loading}>
                        {loading ? 'Testar...' : '▶️ Kör Test'}
                    </button>
                    <button onClick={clearResult} disabled={loading}>
                        🗑️ Rensa
                    </button>
                </div>
            </div>

            {error && (
                <div style={{ background: '#ffebe9', color: '#86181d', padding: 8, borderRadius: 4, marginBottom: 12 }}>
                    {error}
                </div>
            )}

            {/* Test Type Tabs */}
            <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
                {([
                    { key: 'probability', label: '🧠 Probability', description: 'Validera ML-modell' },
                    { key: 'strategy', label: '📈 Strategy', description: 'Testa trading-strategi' },
                    { key: 'backtest', label: '⏰ Backtest', description: 'Historisk simulering' },
                ] as { key: TestType; label: string; description: string }[]).map(t => (
                    <button
                        key={t.key}
                        onClick={() => setActiveTest(t.key)}
                        style={{
                            padding: '8px 12px',
                            borderRadius: 6,
                            border: '1px solid #ccc',
                            background: activeTest === t.key ? '#e7f5ff' : '#fff',
                            fontSize: 12,
                            cursor: 'pointer',
                            textAlign: 'left',
                            minWidth: 120,
                        }}
                    >
                        <div style={{ fontWeight: 'bold' }}>{t.label}</div>
                        <div style={{ fontSize: 10, color: '#666' }}>{t.description}</div>
                    </button>
                ))}
            </div>

            {/* Test Parameters */}
            <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
                gap: 8,
                alignItems: 'end',
                marginBottom: 16,
                padding: 12,
                background: '#f6f8fa',
                borderRadius: 6,
                border: '1px solid #e1e4e8'
            }}>
                <div>
                    <label style={{ fontSize: 12, fontWeight: 'bold' }}>Symbol</label>
                    <input
                        value={symbol}
                        onChange={(e) => setSymbol(e.target.value)}
                        style={{ width: '100%', padding: '4px 8px', border: '1px solid #ced4da', borderRadius: 4, fontSize: 12 }}
                    />
                </div>
                <div>
                    <label style={{ fontSize: 12, fontWeight: 'bold' }}>Timeframe</label>
                    <input
                        value={timeframe}
                        onChange={(e) => setTimeframe(e.target.value)}
                        style={{ width: '100%', padding: '4px 8px', border: '1px solid #ced4da', borderRadius: 4, fontSize: 12 }}
                    />
                </div>
                <div>
                    <label style={{ fontSize: 12, fontWeight: 'bold' }}>Limit</label>
                    <input
                        type="number"
                        value={limit}
                        onChange={(e) => setLimit(parseInt(e.target.value || '0', 10))}
                        style={{ width: '100%', padding: '4px 8px', border: '1px solid #ced4da', borderRadius: 4, fontSize: 12 }}
                    />
                </div>
                {activeTest === 'probability' && (
                    <div>
                        <label style={{ fontSize: 12, fontWeight: 'bold' }}>Max Samples</label>
                        <input
                            type="number"
                            value={maxSamples}
                            onChange={(e) => setMaxSamples(parseInt(e.target.value || '0', 10))}
                            style={{ width: '100%', padding: '4px 8px', border: '1px solid #ced4da', borderRadius: 4, fontSize: 12 }}
                        />
                    </div>
                )}
                {activeTest === 'backtest' && (
                    <div>
                        <label style={{ fontSize: 12, fontWeight: 'bold' }}>Initial Capital</label>
                        <input
                            type="number"
                            value={initialCapital}
                            onChange={(e) => setInitialCapital(parseFloat(e.target.value || '0'))}
                            style={{ width: '100%', padding: '4px 8px', border: '1px solid #ced4da', borderRadius: 4, fontSize: 12 }}
                        />
                    </div>
                )}
            </div>

            {/* Test Results */}
            {result && (
                <div style={{ marginBottom: 16 }}>
                    <div style={{
                        padding: 12,
                        background: result.success ? '#d4edda' : '#f8d7da',
                        borderRadius: 6,
                        border: `1px solid ${result.success ? '#c3e6cb' : '#f5c6cb'}`,
                        marginBottom: 12
                    }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                            <div style={{ fontSize: 14, fontWeight: 'bold' }}>
                                {getTestIcon(result.test_type)} {result.test_type.replace('_', ' ').toUpperCase()}
                            </div>
                            <div style={{
                                fontSize: 12,
                                color: getSuccessColor(result.success),
                                fontWeight: 'bold'
                            }}>
                                {result.success ? '✅ SUCCESS' : '❌ FAILED'}
                            </div>
                        </div>
                        <div style={{ fontSize: 12, color: '#555' }}>
                            Symbol: <b>{result.symbol}</b> ·
                            Timeframe: <b>{result.timeframe}</b> ·
                            Time: <b>{formatTime(result.timestamp)}</b>
                        </div>
                        {result.error_message && (
                            <div style={{ fontSize: 12, color: '#dc3545', marginTop: 4 }}>
                                Error: {result.error_message}
                            </div>
                        )}
                    </div>

                    {/* Metrics Display */}
                    {result.metrics && (
                        <div>
                            {activeTest === 'probability' && (
                                <div style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap', marginBottom: 12 }}>
                                    <div>
                                        <div style={{ fontSize: 12, color: '#555' }}>Brier Score (sparkline)</div>
                                        <Sparkline data={brierSeries} width={220} height={42} color="#12B886" />
                                    </div>
                                    <div style={{ fontSize: 12, color: '#555' }}>
                                        <div>Accuracy: <b>{formatNumber(result.metrics.accuracy || 0, 3)}</b></div>
                                        <div>Brier Score: <b>{formatNumber(result.metrics.brier_score || 0, 4)}</b></div>
                                        <div>Total Signals: <b>{result.metrics.total_signals || 0}</b></div>
                                        <div>Correct Signals: <b>{result.metrics.correct_signals || 0}</b></div>
                                    </div>
                                </div>
                            )}

                            {activeTest === 'strategy' && (
                                <div style={{ fontSize: 12, color: '#555', marginBottom: 8 }}>
                                    <div>Total Trades: <b>{result.metrics.total_trades || 0}</b></div>
                                    <div>Win Rate: <b>{formatNumber(result.metrics.win_rate || 0, 3)}</b></div>
                                    <div>Total Return: <b>{formatNumber(result.metrics.total_return || 0, 4)}</b></div>
                                    <div>Avg Return/Trade: <b>{formatNumber(result.metrics.avg_return_per_trade || 0, 4)}</b></div>
                                </div>
                            )}

                            {activeTest === 'backtest' && (
                                <div style={{ fontSize: 12, color: '#555', marginBottom: 8 }}>
                                    <div>Initial Capital: <b>${formatNumber(result.metrics.initial_capital || 0, 2)}</b></div>
                                    <div>Final Capital: <b>${formatNumber(result.metrics.final_capital || 0, 2)}</b></div>
                                    <div>Total Return: <b>{formatNumber(result.metrics.total_return || 0, 4)}</b></div>
                                    <div>Total Trades: <b>{result.metrics.total_trades || 0}</b></div>
                                    <div>Max Drawdown: <b>{formatNumber(result.metrics.max_drawdown || 0, 4)}</b></div>
                                    <div>Sharpe Ratio: <b>{formatNumber(result.metrics.sharpe_ratio || 0, 3)}</b></div>
                                </div>
                            )}

                            <div style={{ fontSize: 12, color: '#555', marginBottom: 8 }}>Full Result</div>
                            <JsonTree data={result} />
                        </div>
                    )}
                </div>
            )}

            {/* Validation History */}
            <div>
                <h4 style={{ margin: '0 0 8px' }}>📋 Test History</h4>
                <div style={{
                    maxHeight: 200,
                    overflow: 'auto',
                    border: '1px solid #e1e4e8',
                    borderRadius: 6,
                    background: '#f6f8fa'
                }}>
                    {validationHistory.length === 0 ? (
                        <div style={{ padding: 12, textAlign: 'center', color: '#666' }}>
                            Inga tester körda än
                        </div>
                    ) : (
                        validationHistory.map((test, index) => (
                            <div key={index} style={{
                                padding: 8,
                                borderBottom: '1px solid #e1e4e8',
                                fontSize: 12
                            }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                    <div>
                                        <span style={{ fontWeight: 'bold' }}>
                                            {getTestIcon(test.test_type)} {test.test_type.replace('_', ' ')}
                                        </span>
                                        <span style={{ color: '#666', marginLeft: 8 }}>
                                            {test.symbol} · {formatTime(test.timestamp)}
                                        </span>
                                    </div>
                                    <div style={{
                                        color: getSuccessColor(test.success),
                                        fontWeight: 'bold'
                                    }}>
                                        {test.success ? '✅' : '❌'}
                                    </div>
                                </div>
                                {test.metrics_summary && (
                                    <div style={{ fontSize: 11, color: '#666', marginTop: 4 }}>
                                        {test.metrics_summary.accuracy !== undefined && (
                                            <>Accuracy: {formatNumber(test.metrics_summary.accuracy, 3)} · </>
                                        )}
                                        {test.metrics_summary.total_return !== undefined && (
                                            <>Return: {formatNumber(test.metrics_summary.total_return, 4)} · </>
                                        )}
                                        {test.metrics_summary.final_capital !== undefined && (
                                            <>Capital: ${formatNumber(test.metrics_summary.final_capital, 2)}</>
                                        )}
                                    </div>
                                )}
                            </div>
                        ))
                    )}
                </div>
            </div>
        </div>
    );
}
