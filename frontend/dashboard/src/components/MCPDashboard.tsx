import React, { useState, useEffect } from 'react';
import { getApiBase } from '../lib/api';

interface MCPTool {
  name: string;
  description: string;
  inputSchema: Record<string, any>;
}

interface TradingStatus {
  user_id: string;
  status: string;
  active_positions: number;
  total_pnl: number;
  daily_pnl: number;
  risk_level: string;
}

interface PerformanceMetrics {
  user_id: string;
  timeframe: string;
  total_return: number;
  sharpe_ratio: number;
  max_drawdown: number;
  win_rate: number;
  total_trades: number;
  profitable_trades: number;
  average_trade_duration: string;
  last_updated: string;
}

export function MCPDashboard() {
  const [tools, setTools] = useState<MCPTool[]>([]);
  const [tradingStatus, setTradingStatus] = useState<TradingStatus | null>(null);
  const [performanceMetrics, setPerformanceMetrics] = useState<PerformanceMetrics | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState('overview');

  // Trade execution state
  const [tradeForm, setTradeForm] = useState({
    symbol: 'BTCUSD',
    side: 'buy',
    amount: 0.001
  });

  // Strategy update state
  const [strategyForm, setStrategyForm] = useState({
    name: 'default_strategy',
    parameters: '{"param1": "value1", "param2": 42}'
  });

  useEffect(() => {
    loadMCPData();
  }, []);

  const loadMCPData = async () => {
    setLoading(true);
    setError(null);

    try {
      console.log('🔄 Loading MCP data from backend...');

      // Load tools via backend MCP endpoints
      console.log('📋 Loading tools...');
      const toolsResponse = await fetch(`${getApiBase()}/api/v2/mcp/tools`);
      console.log('📋 Tools response status:', toolsResponse.status);

      if (!toolsResponse.ok) {
        const errorText = await toolsResponse.text();
        throw new Error(`Tools API failed: ${toolsResponse.status} - ${errorText}`);
      }

      const toolsData = await toolsResponse.json();
      console.log('📋 Tools data:', toolsData);
      setTools(toolsData);

      // Load trading status via backend MCP endpoints
      console.log('📊 Loading trading status...');
      const statusResponse = await fetch(`${getApiBase()}/api/v2/mcp/trading/status`);
      console.log('📊 Status response status:', statusResponse.status);

      if (!statusResponse.ok) {
        const errorText = await statusResponse.text();
        throw new Error(`Status API failed: ${statusResponse.status} - ${errorText}`);
      }

      const statusData = await statusResponse.json();
      console.log('📊 Status data:', statusData);
      setTradingStatus(statusData);

      // Load performance metrics via backend MCP endpoints
      console.log('📈 Loading performance metrics...');
      const metricsResponse = await fetch(`${getApiBase()}/api/v2/mcp/trading/performance`);
      console.log('📈 Metrics response status:', metricsResponse.status);

      if (!metricsResponse.ok) {
        const errorText = await metricsResponse.text();
        throw new Error(`Metrics API failed: ${metricsResponse.status} - ${errorText}`);
      }

      const metricsData = await metricsResponse.json();
      console.log('📈 Metrics data:', metricsData);
      setPerformanceMetrics(metricsData);

    } catch (err: any) {
      console.error('❌ MCP data loading failed:', err);
      setError(err.message || 'Kunde inte ladda MCP-data');
    } finally {
      setLoading(false);
    }
  };

  const executeTrade = async () => {
    // MCP Dashboard ska INTE hantera trading - det ska Genesis Dashboard göra via WebSocket
    alert('Trading ska göras via Genesis Dashboard, inte MCP Dashboard. MCP är endast för data och loggning.');
  };

  const updateStrategy = async () => {
    try {
      const params = JSON.parse(strategyForm.parameters);
      const response = await fetch(`${getApiBase()}/api/v2/mcp/strategy/update`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          strategy_name: strategyForm.name,
          params
        })
      });

      const result = await response.json();
      if (result.success) {
        alert('Strategi uppdaterad framgångsrikt!');
      }
    } catch (err: any) {
      alert(`Strategi-uppdatering misslyckades: ${err.message}`);
    }
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '2rem' }}>
        <div style={{ fontSize: '1.125rem' }}>Laddar MCP-data...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: '1rem', border: '1px solid #ef4444', borderRadius: '0.5rem', backgroundColor: '#fef2f2' }}>
        <div style={{ color: '#dc2626', textAlign: 'center' }}>
          <p>❌ {error}</p>
          <button
            onClick={loadMCPData}
            style={{
              marginTop: '1rem',
              padding: '0.5rem 1rem',
              backgroundColor: '#3b82f6',
              color: 'white',
              border: 'none',
              borderRadius: '0.375rem',
              cursor: 'pointer'
            }}
          >
            Försök igen
          </button>
        </div>
      </div>
    );
  }

  const tabStyle = (tab: string) => ({
    padding: '0.75rem 1.5rem',
    border: 'none',
    backgroundColor: activeTab === tab ? '#3b82f6' : '#f3f4f6',
    color: activeTab === tab ? 'white' : '#374151',
    cursor: 'pointer',
    borderRadius: '0.375rem',
    marginRight: '0.5rem'
  });

  const cardStyle = {
    padding: '1.5rem',
    border: '1px solid #e5e7eb',
    borderRadius: '0.5rem',
    backgroundColor: 'white',
    marginBottom: '1rem'
  };

  return (
    <div style={{ padding: '1.5rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <h1 style={{ fontSize: '1.875rem', fontWeight: 'bold' }}>MCP Dashboard</h1>
        <button
          onClick={loadMCPData}
          style={{
            padding: '0.5rem 1rem',
            backgroundColor: 'white',
            color: '#374151',
            border: '1px solid #d1d5db',
            borderRadius: '0.375rem',
            cursor: 'pointer'
          }}
        >
          Uppdatera
        </button>
      </div>

      {/* Tab Navigation */}
      <div style={{ marginBottom: '1.5rem' }}>
        <button style={tabStyle('overview')} onClick={() => setActiveTab('overview')}>
          Översikt
        </button>
        <button style={tabStyle('tools')} onClick={() => setActiveTab('tools')}>
          MCP Tools
        </button>
        <button style={tabStyle('trading')} onClick={() => setActiveTab('trading')}>
          Trading
        </button>
        <button style={tabStyle('strategy')} onClick={() => setActiveTab('strategy')}>
          Strategi
        </button>
      </div>

      {/* Overview Tab */}
      {activeTab === 'overview' && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1rem' }}>
          <div style={cardStyle}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
              <h3 style={{ fontSize: '0.875rem', fontWeight: '500' }}>Tillgängliga Tools</h3>
              <span style={{
                padding: '0.25rem 0.5rem',
                backgroundColor: '#6b7280',
                color: 'white',
                borderRadius: '9999px',
                fontSize: '0.75rem'
              }}>
                {tools.length}
              </span>
            </div>
            <div style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>{tools.length}</div>
            <p style={{ fontSize: '0.75rem', color: '#6b7280' }}>
              MCP-tools tillgängliga
            </p>
          </div>

          <div style={cardStyle}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
              <h3 style={{ fontSize: '0.875rem', fontWeight: '500' }}>Trading Status</h3>
              <span style={{
                padding: '0.25rem 0.5rem',
                backgroundColor: tradingStatus?.status === 'active' ? '#10b981' : '#ef4444',
                color: 'white',
                borderRadius: '9999px',
                fontSize: '0.75rem'
              }}>
                {tradingStatus?.status || 'unknown'}
              </span>
            </div>
            <div style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>{tradingStatus?.active_positions || 0}</div>
            <p style={{ fontSize: '0.75rem', color: '#6b7280' }}>
              Aktiva positioner
            </p>
          </div>

          <div style={cardStyle}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
              <h3 style={{ fontSize: '0.875rem', fontWeight: '500' }}>Total PnL</h3>
              <span style={{
                padding: '0.25rem 0.5rem',
                backgroundColor: tradingStatus?.total_pnl && tradingStatus.total_pnl > 0 ? '#10b981' : '#ef4444',
                color: 'white',
                borderRadius: '9999px',
                fontSize: '0.75rem'
              }}>
                {tradingStatus?.total_pnl ? (tradingStatus.total_pnl > 0 ? '+' : '') + tradingStatus.total_pnl.toFixed(2) : '0.00'}
              </span>
            </div>
            <div style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>
              {tradingStatus?.total_pnl ? (tradingStatus.total_pnl > 0 ? '+' : '') + tradingStatus.total_pnl.toFixed(2) : '0.00'}
            </div>
            <p style={{ fontSize: '0.75rem', color: '#6b7280' }}>
              Total vinst/förlust
            </p>
          </div>
        </div>
      )}

      {/* Tools Tab */}
      {activeTab === 'tools' && (
        <div style={cardStyle}>
          <h3 style={{ fontSize: '1.125rem', fontWeight: '600', marginBottom: '1rem' }}>MCP Tools</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {tools.map((tool) => (
              <div key={tool.name} style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '0.75rem',
                border: '1px solid #e5e7eb',
                borderRadius: '0.5rem'
              }}>
                <div>
                  <h4 style={{ fontWeight: '500' }}>{tool.name}</h4>
                  <p style={{ fontSize: '0.875rem', color: '#6b7280' }}>{tool.description}</p>
                </div>
                <span style={{
                  padding: '0.25rem 0.5rem',
                  backgroundColor: '#f3f4f6',
                  color: '#374151',
                  borderRadius: '9999px',
                  fontSize: '0.75rem'
                }}>
                  Available
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Trading Tab */}
      {activeTab === 'trading' && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '1rem' }}>
          <div style={cardStyle}>
            <h3 style={{ fontSize: '1.125rem', fontWeight: '600', marginBottom: '1rem' }}>Trading Information (Read-Only)</h3>
            <div style={{
              padding: '1rem',
              backgroundColor: '#f0f9ff',
              border: '1px solid #0ea5e9',
              borderRadius: '0.5rem',
              marginBottom: '1rem'
            }}>
              <p style={{ margin: 0, color: '#0369a1' }}>
                <strong>ℹ️ Info:</strong> Trading ska göras via Genesis Dashboard (QuickTrade komponenten).
                MCP Dashboard visar endast data och loggning.
              </p>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div>
                <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500' }}>Symbol</label>
                <input
                  type="text"
                  value={tradeForm.symbol}
                  onChange={(e) => setTradeForm({ ...tradeForm, symbol: e.target.value })}
                  placeholder="BTCUSD"
                  style={{
                    width: '100%',
                    padding: '0.5rem',
                    border: '1px solid #d1d5db',
                    borderRadius: '0.375rem',
                    backgroundColor: '#f9fafb'
                  }}
                  disabled
                />
              </div>
              <div>
                <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500' }}>Side</label>
                <select
                  value={tradeForm.side}
                  onChange={(e) => setTradeForm({ ...tradeForm, side: e.target.value })}
                  style={{
                    width: '100%',
                    padding: '0.5rem',
                    border: '1px solid #d1d5db',
                    borderRadius: '0.375rem',
                    backgroundColor: '#f9fafb'
                  }}
                  disabled
                >
                  <option value="buy">Buy</option>
                  <option value="sell">Sell</option>
                </select>
              </div>
              <div>
                <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500' }}>Amount</label>
                <input
                  type="number"
                  step="0.001"
                  value={tradeForm.amount}
                  onChange={(e) => setTradeForm({ ...tradeForm, amount: parseFloat(e.target.value) || 0 })}
                  placeholder="0.001"
                  style={{
                    width: '100%',
                    padding: '0.5rem',
                    border: '1px solid #d1d5db',
                    borderRadius: '0.375rem',
                    backgroundColor: '#f9fafb'
                  }}
                  disabled
                />
              </div>
              <button
                onClick={executeTrade}
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  backgroundColor: '#6b7280',
                  color: 'white',
                  border: 'none',
                  borderRadius: '0.375rem',
                  cursor: 'not-allowed',
                  fontWeight: '500'
                }}
                disabled
              >
                Trading via Genesis Dashboard
              </button>
            </div>
          </div>

          <div style={cardStyle}>
            <h3 style={{ fontSize: '1.125rem', fontWeight: '600', marginBottom: '1rem' }}>Performance Metrics</h3>
            {performanceMetrics ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>Total Return:</span>
                  <span style={{ color: performanceMetrics.total_return >= 0 ? '#10b981' : '#ef4444' }}>
                    {performanceMetrics.total_return >= 0 ? '+' : ''}{performanceMetrics.total_return.toFixed(2)}%
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>Sharpe Ratio:</span>
                  <span>{performanceMetrics.sharpe_ratio.toFixed(2)}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>Max Drawdown:</span>
                  <span style={{ color: '#ef4444' }}>{performanceMetrics.max_drawdown.toFixed(2)}%</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>Win Rate:</span>
                  <span>{performanceMetrics.win_rate.toFixed(1)}%</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>Total Trades:</span>
                  <span>{performanceMetrics.total_trades}</span>
                </div>
              </div>
            ) : (
              <p style={{ color: '#6b7280' }}>Ingen data tillgänglig</p>
            )}
          </div>
        </div>
      )}

      {/* Strategy Tab */}
      {activeTab === 'strategy' && (
        <div style={cardStyle}>
          <h3 style={{ fontSize: '1.125rem', fontWeight: '600', marginBottom: '1rem' }}>Strategy Parameters</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500' }}>Strategy Name</label>
              <input
                type="text"
                value={strategyForm.name}
                onChange={(e) => setStrategyForm({ ...strategyForm, name: e.target.value })}
                placeholder="default_strategy"
                style={{
                  width: '100%',
                  padding: '0.5rem',
                  border: '1px solid #d1d5db',
                  borderRadius: '0.375rem'
                }}
              />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500' }}>Parameters (JSON)</label>
              <textarea
                value={strategyForm.parameters}
                onChange={(e) => setStrategyForm({ ...strategyForm, parameters: e.target.value })}
                placeholder='{"param1": "value1", "param2": 42}'
                rows={4}
                style={{
                  width: '100%',
                  padding: '0.5rem',
                  border: '1px solid #d1d5db',
                  borderRadius: '0.375rem',
                  fontFamily: 'monospace'
                }}
              />
            </div>
            <button
              onClick={updateStrategy}
              style={{
                width: '100%',
                padding: '0.75rem',
                backgroundColor: '#3b82f6',
                color: 'white',
                border: 'none',
                borderRadius: '0.375rem',
                cursor: 'pointer',
                fontWeight: '500'
              }}
            >
              Uppdatera Strategi
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
