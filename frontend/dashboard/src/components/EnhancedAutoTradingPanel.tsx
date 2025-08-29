import React, { useEffect, useState } from 'react';
import { get, post } from '@lib/api';
import { TEST_SYMBOLS } from '@lib/testSymbols';

interface EnhancedAutoStatus {
    active_symbols: string[];
    last_signals: Record<string, {
        signal_type: string;
        confidence_score: number;
        trading_probability: number;
        strength: string;
        timestamp: string;
    }>;
    last_trades: Record<string, string>;
}

const EnhancedAutoTradingPanel: React.FC = () => {
    const [status, setStatus] = useState<EnhancedAutoStatus | null>(null);
    const [selectedSymbol, setSelectedSymbol] = useState<string>('');
    const [loading, setLoading] = useState(false);
    const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

    // Hämta status
    const fetchStatus = async () => {
        try {
            setLoading(true);
            const data = await get('/api/v2/enhanced-auto/status');
            console.log('Enhanced Auto Status:', data);
            console.log('Active symbols:', data?.active_symbols);
            console.log('Last signals:', data?.last_signals);
            setStatus(data);
            setLastUpdate(new Date());
        } catch (error) {
            console.error('Fel vid hämtning av enhanced auto-status:', error);
        } finally {
            setLoading(false);
        }
    };

    // Starta enhanced auto-trading
    const startEnhancedTrading = async (symbol: string) => {
        try {
            setLoading(true);
            const result = await post(`/api/v2/enhanced-auto/start?symbol=${symbol}`);
            console.log('Enhanced auto-trading startad:', result);
            await fetchStatus(); // Uppdatera status
        } catch (error) {
            console.error('Fel vid start av enhanced auto-trading:', error);
        } finally {
            setLoading(false);
        }
    };

    // Stoppa enhanced auto-trading
    const stopEnhancedTrading = async (symbol: string) => {
        try {
            setLoading(true);
            const result = await post(`/api/v2/enhanced-auto/stop?symbol=${symbol}`);
            console.log('Enhanced auto-trading stoppad:', result);
            await fetchStatus(); // Uppdatera status
        } catch (error) {
            console.error('Fel vid stopp av enhanced auto-trading:', error);
        } finally {
            setLoading(false);
        }
    };

    // Stoppa all enhanced auto-trading
    const stopAllEnhancedTrading = async () => {
        try {
            setLoading(true);
            const result = await post('/api/v2/enhanced-auto/stop-all');
            console.log('All enhanced auto-trading stoppad:', result);
            await fetchStatus(); // Uppdatera status
        } catch (error) {
            console.error('Fel vid stopp av all enhanced auto-trading:', error);
        } finally {
            setLoading(false);
        }
    };

    // Hämta status vid mount och var 60:e sekund
    useEffect(() => {
        fetchStatus();
        const interval = setInterval(fetchStatus, 300000); // Öka till 5 minuter
        return () => clearInterval(interval);
    }, []);

    const isActive = (symbol: string) => status?.active_symbols.includes(symbol) || false;

    const getSignalInfo = (symbol: string) => {
        return status?.last_signals[symbol];
    };

    const getLastTrade = (symbol: string) => {
        return status?.last_trades[symbol];
    };

    const formatTimestamp = (timestamp: string) => {
        return new Date(timestamp).toLocaleString('sv-SE');
    };

    return (
        <div className="panel">
            <div className="panel-header">
                <h3>🤖 Enhanced Auto-Trading</h3>
                <div className="panel-controls">
                    <button
                        onClick={fetchStatus}
                        disabled={loading}
                        className="btn btn-secondary"
                    >
                        {loading ? 'Laddar...' : '🔄 Uppdatera'}
                    </button>
                    {status && status.active_symbols.length > 0 && (
                        <button
                            onClick={stopAllEnhancedTrading}
                            disabled={loading}
                            className="btn btn-danger"
                        >
                            🛑 Stoppa Alla
                        </button>
                    )}
                </div>
            </div>

            <div className="panel-content">
                {/* Status översikt */}
                <div className="status-overview">
                    <div className="status-item">
                        <span className="label">Aktiva symboler:</span>
                        <span className="value">{status?.active_symbols.length || 0}</span>
                    </div>
                    <div className="status-item">
                        <span className="label">Senaste uppdatering:</span>
                        <span className="value">
                            {lastUpdate ? lastUpdate.toLocaleTimeString('sv-SE') : 'Aldrig'}
                        </span>
                    </div>
                </div>

                {/* Symbol kontroller */}
                <div className="symbol-controls">
                    <h4>Symbol Kontroller</h4>
                    <div className="symbol-selector">
                        <select
                            value={selectedSymbol}
                            onChange={(e) => setSelectedSymbol(e.target.value)}
                            className="form-select"
                        >
                            <option value="">Välj symbol...</option>
                            {TEST_SYMBOLS.map((symbol: { symbol: string; name: string }) => (
                                <option key={symbol.symbol} value={symbol.symbol}>{symbol.symbol}</option>
                            ))}
                        </select>
                        {selectedSymbol && (
                            <button
                                onClick={() => startEnhancedTrading(selectedSymbol)}
                                disabled={loading || isActive(selectedSymbol)}
                                className="btn btn-success"
                            >
                                ▶️ Starta
                            </button>
                        )}
                    </div>
                </div>

                {/* Aktiva symboler */}
                {status && status.active_symbols.length > 0 && (
                    <div className="active-symbols">
                        <h4>Aktiva Symboler</h4>
                        <div className="symbol-grid">
                            {status.active_symbols.map((symbol: string) => {
                                const signalInfo = getSignalInfo(symbol);
                                const lastTrade = getLastTrade(symbol);

                                return (
                                    <div key={symbol} className="symbol-card">
                                        <div className="symbol-header">
                                            <h5>{symbol}</h5>
                                            <button
                                                onClick={() => stopEnhancedTrading(symbol)}
                                                disabled={loading}
                                                className="btn btn-sm btn-danger"
                                            >
                                                🛑 Stoppa
                                            </button>
                                        </div>

                                        {signalInfo && (
                                            <div className="signal-info">
                                                <div className="signal-item">
                                                    <span className="label">Signal:</span>
                                                    <span className={`value signal-${signalInfo.signal_type.toLowerCase()}`}>
                                                        {signalInfo.signal_type}
                                                    </span>
                                                </div>
                                                <div className="signal-item">
                                                    <span className="label">Confidence:</span>
                                                    <span className="value">{signalInfo.confidence_score.toFixed(1)}%</span>
                                                </div>
                                                <div className="signal-item">
                                                    <span className="label">Probability:</span>
                                                    <span className="value">{signalInfo.trading_probability.toFixed(1)}%</span>
                                                </div>
                                                <div className="signal-item">
                                                    <span className="label">Styrka:</span>
                                                    <span className={`value strength-${signalInfo.strength.toLowerCase()}`}>
                                                        {signalInfo.strength}
                                                    </span>
                                                </div>
                                                <div className="signal-item">
                                                    <span className="label">Senaste signal:</span>
                                                    <span className="value">{formatTimestamp(signalInfo.timestamp)}</span>
                                                </div>
                                            </div>
                                        )}

                                        {!signalInfo && (
                                            <div className="signal-info">
                                                <div className="signal-item">
                                                    <span className="label">Status:</span>
                                                    <span className="value">Ingen signal än</span>
                                                </div>
                                            </div>
                                        )}

                                        {lastTrade && (
                                            <div className="trade-info">
                                                <div className="trade-item">
                                                    <span className="label">Senaste trade:</span>
                                                    <span className="value">{formatTimestamp(lastTrade)}</span>
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                )}

                {/* Inaktiva symboler med senaste signals */}
                {status?.last_signals && Object.keys(status.last_signals).length > 0 && (
                    <div className="inactive-symbols">
                        <h4>Senaste Signals (Inaktiva)</h4>
                        <div className="signal-grid">
                            {Object.entries(status.last_signals)
                                .filter(([symbol]) => !status?.active_symbols?.includes(symbol))
                                .map(([symbol, signalInfo]) => (
                                    <div key={symbol} className="signal-card inactive">
                                        <div className="signal-header">
                                            <h5>{symbol}</h5>
                                            <button
                                                onClick={() => startEnhancedTrading(symbol)}
                                                disabled={loading}
                                                className="btn btn-sm btn-success"
                                            >
                                                ▶️ Starta
                                            </button>
                                        </div>

                                        <div className="signal-info">
                                            <div className="signal-item">
                                                <span className="label">Signal:</span>
                                                <span className={`value signal-${signalInfo.signal_type.toLowerCase()}`}>
                                                    {signalInfo.signal_type}
                                                </span>
                                            </div>
                                            <div className="signal-item">
                                                <span className="label">Confidence:</span>
                                                <span className="value">{signalInfo.confidence_score.toFixed(1)}%</span>
                                            </div>
                                            <div className="signal-item">
                                                <span className="label">Probability:</span>
                                                <span className="value">{signalInfo.trading_probability.toFixed(1)}%</span>
                                            </div>
                                            <div className="signal-item">
                                                <span className="label">Styrka:</span>
                                                <span className={`value strength-${signalInfo.strength.toLowerCase()}`}>
                                                    {signalInfo.strength}
                                                </span>
                                            </div>
                                            <div className="signal-item">
                                                <span className="label">Senaste:</span>
                                                <span className="value">{formatTimestamp(signalInfo.timestamp)}</span>
                                            </div>
                                        </div>
                                    </div>
                                ))}
                        </div>
                    </div>
                )}
            </div>

            <style>{`
        .panel {
          background: #1a1a1a;
          border: 1px solid #333;
          border-radius: 8px;
          margin: 10px 0;
        }

        .panel-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 15px;
          border-bottom: 1px solid #333;
        }

        .panel-header h3 {
          margin: 0;
          color: #fff;
        }

        .panel-controls {
          display: flex;
          gap: 10px;
        }

        .panel-content {
          padding: 15px;
        }

        .status-overview {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 15px;
          margin-bottom: 20px;
          padding: 15px;
          background: #2a2a2a;
          border-radius: 6px;
        }

        .status-item {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .status-item .label {
          color: #ccc;
          font-weight: 500;
        }

        .status-item .value {
          color: #fff;
          font-weight: bold;
        }

        .symbol-controls {
          margin-bottom: 20px;
        }

        .symbol-controls h4 {
          color: #fff;
          margin-bottom: 10px;
        }

        .symbol-selector {
          display: flex;
          gap: 10px;
          align-items: center;
        }

        .form-select {
          flex: 1;
          padding: 8px 12px;
          background: #2a2a2a;
          border: 1px solid #444;
          border-radius: 4px;
          color: #fff;
        }

        .symbol-grid, .signal-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
          gap: 15px;
        }

        .symbol-card, .signal-card {
          background: #2a2a2a;
          border: 1px solid #444;
          border-radius: 6px;
          padding: 15px;
        }

        .symbol-card.inactive {
          opacity: 0.7;
        }

        .symbol-header, .signal-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 10px;
        }

        .symbol-header h5, .signal-header h5 {
          margin: 0;
          color: #fff;
        }

        .signal-info, .trade-info {
          display: grid;
          gap: 8px;
        }

        .signal-item, .trade-item {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .signal-item .label, .trade-item .label {
          color: #ccc;
          font-size: 0.9em;
        }

        .signal-item .value, .trade-item .value {
          color: #fff;
          font-weight: 500;
        }

        .signal-buy {
          color: #4caf50 !important;
        }

        .signal-sell {
          color: #f44336 !important;
        }

        .signal-hold {
          color: #ff9800 !important;
        }

        .strength-strong {
          color: #4caf50 !important;
        }

        .strength-medium {
          color: #ff9800 !important;
        }

        .strength-weak {
          color: #f44336 !important;
        }

        .btn {
          padding: 8px 16px;
          border: none;
          border-radius: 4px;
          cursor: pointer;
          font-weight: 500;
          transition: all 0.2s;
        }

        .btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .btn-success {
          background: #4caf50;
          color: white;
        }

        .btn-danger {
          background: #f44336;
          color: white;
        }

        .btn-secondary {
          background: #666;
          color: white;
        }

        .btn-sm {
          padding: 4px 8px;
          font-size: 0.8em;
        }

        h4 {
          color: #fff;
          margin: 20px 0 10px 0;
        }
      `}</style>
        </div>
    );
};

export default EnhancedAutoTradingPanel;
