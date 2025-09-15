import React from 'react';
import EnhancedAutoTradingPanel from '../components/EnhancedAutoTradingPanel';
import { HistoryPanel } from '../components/HistoryPanel';
import { LiveSignalsPanel } from '../components/LiveSignalsPanel';
import { MarketPanel } from '../components/MarketPanel';
import { PositionsPanel } from '../components/PositionsPanel';
import { QuickTrade } from '../components/QuickTrade';
import { RiskGuardsPanel } from '../components/RiskGuardsPanel';
import { RiskPanel } from '../components/RiskPanel';
import { StatusCard } from '../components/StatusCard';
import { SystemPanel } from '../components/SystemPanel';
// import { Toggles } from '../components/Toggles'; // Removed - replaced with Feature Flags
import { ensureToken, getApiBase, getWith } from '@lib/api';
import { useThrottledValue } from '@lib/useThrottledValue';
import { AcceptanceBadge } from '../components/AcceptanceBadge';
import { AuthStatus } from '../components/AuthStatus';
import { EnhancedObservabilityPanel } from '../components/EnhancedObservabilityPanel';
import { FeatureFlagsPanel } from '../components/FeatureFlagsPanel';
import { PerformancePanel } from '../components/PerformancePanel';
import { ReadOnlyHistoryPanel } from '../components/ReadOnlyHistoryPanel';
import { RefreshManagerPanel } from '../components/RefreshManagerPanel';
import { TestValidationPanel } from '../components/TestValidationPanel';
import { UnifiedCircuitBreakerPanel } from '../components/UnifiedCircuitBreakerPanel';
import { UnifiedRiskPanel } from '../components/UnifiedRiskPanel';
import { ValidationPanel } from '../components/ValidationPanel';
import { WalletsPanel } from '../components/WalletsPanel';

// Tab component for better organization
interface TabProps {
  id: string;
  label: string;
  icon: string;
  color: string;
  children: React.ReactNode;
}

function Tab({ id, label, icon, color, children }: TabProps) {
  return (
    <div id={id} style={{ display: 'none' }}>
      {children}
    </div>
  );
}

function TabButton({
  id,
  label,
  icon,
  color,
  isActive,
  onClick,
}: TabProps & { isActive: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '12px 20px',
        border: 'none',
        background: isActive ? color : '#f8f9fa',
        color: isActive ? 'white' : '#495057',
        borderRadius: '8px 8px 0 0',
        cursor: 'pointer',
        fontSize: '14px',
        fontWeight: isActive ? '600' : '400',
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        transition: 'all 0.2s ease',
        borderBottom: isActive ? `3px solid ${color}` : '3px solid transparent',
      }}
    >
      <span style={{ fontSize: '16px' }}>{icon}</span>
      {label}
    </button>
  );
}

export default function DashboardPage() {
  const [status, setStatus] = React.useState<any>(null);
  const [caps, setCaps] = React.useState<any>(null);
  const [modes, setModes] = React.useState<any>(null);
  const statusT = useThrottledValue(status, 400);
  const capsT = useThrottledValue(caps, 400);
  const modesT = useThrottledValue(modes, 400);
  const [strategyAuto, setStrategyAuto] = React.useState<{
    AUTO_REGIME_ENABLED?: boolean;
    AUTO_WEIGHTS_ENABLED?: boolean;
  } | null>(null);
  const [log, setLog] = React.useState<string[]>([]);
  const [acceptance, setAcceptance] = React.useState<any>(null);
  const [activeTab, setActiveTab] = React.useState('trading');

  const refresh = React.useCallback(async () => {
    setLog((l) =>
      [
        `[${new Date().toLocaleTimeString()}] refresh start (base=${getApiBase()})`,
        ...l,
      ].slice(0, 50)
    );
    await ensureToken(true);
    try {
      // Batcha API-anrop för bättre prestanda
      const [s, c, dry, paused, pm, at, sch, wsst, warm, auto, acc] =
        await Promise.all([
          getWith('/api/v2/ws/pool/status', { timeout: 12000, maxRetries: 1 }),
          getWith('/api/v2/ui/capabilities', { timeout: 10000, maxRetries: 1 }).catch(() => null),
          getWith('/api/v2/mode/dry-run', { timeout: 8000, maxRetries: 0 }).catch(() => null),
          getWith('/api/v2/mode/trading-paused', { timeout: 8000, maxRetries: 0 }).catch(() => null),
          getWith('/api/v2/mode/prob-model', { timeout: 8000, maxRetries: 0 }).catch(() => null),
          getWith('/api/v2/mode/autotrade', { timeout: 8000, maxRetries: 0 }).catch(() => null),
          getWith('/api/v2/mode/scheduler', { timeout: 8000, maxRetries: 0 }).catch(() => null),
          getWith('/api/v2/mode/ws-strategy', { timeout: 8000, maxRetries: 0 }).catch(() => null),
          getWith('/api/v2/mode/validation-warmup', { timeout: 8000, maxRetries: 0 }).catch(() => null),
          getWith('/api/v2/strategy/auto', { timeout: 10000, maxRetries: 1 }).catch(() => null),
          getWith('/api/v2/metrics/acceptance', { timeout: 8000, maxRetries: 0, doNotRecordCB: true }).catch(() => null),
        ]);

      setStatus(s);
      if (c) setCaps(c);
      if (auto) setStrategyAuto(auto);
      if (acc) setAcceptance(acc);
      setModes({
        dry_run_enabled: dry ? !!dry.dry_run_enabled : undefined,
        trading_paused: paused ? !!paused.trading_paused : undefined,
        prob_model_enabled: pm ? !!pm.prob_model_enabled : undefined,
        autotrade_enabled: at ? !!at.autotrade_enabled : undefined,
        scheduler_running: sch ? !!sch.scheduler_running : undefined,
        ws_strategy_enabled: wsst ? !!wsst.ws_strategy_enabled : undefined,
        validation_on_start: warm ? !!warm.validation_on_start : undefined,
      });

      setLog((l) =>
        [`[${new Date().toLocaleTimeString()}] refresh ok`, ...l].slice(0, 50)
      );
    } catch (e: any) {
      setLog((l) =>
        [
          `[${new Date().toLocaleTimeString()}] refresh error: ${
            e?.message || e
          }`,
          ...l,
        ].slice(0, 50)
      );
    }
  }, []);

  React.useEffect(() => {
    // Add a small delay to prevent overwhelming the backend on startup
    const delayedRefresh = async () => {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      await refresh();
    };
    delayedRefresh();
    const id = setInterval(refresh, 60000); // 1 minut för stabilitet
    return () => clearInterval(id);
  }, [refresh]);

  // Tab configuration
  const tabs = [
    { id: 'trading', label: 'Trading', icon: '🚀', color: '#28a745' },
    { id: 'risk', label: 'Risk Management', icon: '🛡️', color: '#dc3545' },
    { id: 'analytics', label: 'Analytics', icon: '📈', color: '#007bff' },
    { id: 'system', label: 'System', icon: '⚙️', color: '#ffc107' },
    { id: 'admin', label: 'Admin', icon: '🔧', color: '#6c757d' },
  ];

  const handleTabClick = (tabId: string) => {
    setActiveTab(tabId);
    // Show/hide tab content
    tabs.forEach((tab) => {
      const element = document.getElementById(tab.id);
      if (element) {
        element.style.display = tab.id === tabId ? 'block' : 'none';
      }
    });
  };

  React.useEffect(() => {
    // Initialize tab visibility
    handleTabClick(activeTab);
  }, [activeTab]);

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', padding: 16 }}>
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <h1
          style={{
            margin: '0 0 16px 0',
            fontSize: '32px',
            fontWeight: '700',
            color: '#212529',
          }}
        >
          🎯 Genesis Trading Dashboard
        </h1>
        <div
          style={{
            display: 'flex',
            gap: 12,
            alignItems: 'center',
            flexWrap: 'wrap',
            marginBottom: 16,
          }}
        >
          <AcceptanceBadge acceptance={acceptance} />
          <AuthStatus />
        </div>

        {/* Quick Status Overview */}
        <div
          style={{
            background: '#f8f9fa',
            padding: 16,
            borderRadius: 12,
            marginBottom: 16,
            border: '1px solid #e9ecef',
          }}
        >
          <StatusCard
            status={statusT}
            caps={capsT}
            modes={modesT}
            strategyAuto={strategyAuto}
          />
        </div>

        {/* Quick Status - Simplified */}
        <div
          style={{
            display: 'flex',
            gap: 16,
            alignItems: 'center',
            marginBottom: 16,
            padding: 12,
            background: '#f8f9fa',
            borderRadius: 8,
            border: '1px solid #e9ecef',
          }}
        >
          <div style={{ fontSize: '14px', color: '#6c757d' }}>
            <strong>Quick Status:</strong>{' '}
            {statusT?.connected ? '🟢 Connected' : '🔴 Disconnected'}
          </div>
          <div style={{ fontSize: '14px', color: '#6c757d' }}>
            <strong>Mode:</strong>{' '}
            {modesT?.dry_run_enabled ? '🧪 Dry Run' : '🚀 Live Trading'}
          </div>
          <div style={{ fontSize: '14px', color: '#6c757d' }}>
            <strong>Auto:</strong>{' '}
            {modesT?.autotrade_enabled ? '✅ On' : '❌ Off'}
          </div>
        </div>
      </div>

      {/* Tab Navigation */}
      <div
        style={{
          display: 'flex',
          gap: 4,
          marginBottom: 24,
          borderBottom: '2px solid #e9ecef',
          paddingBottom: 0,
        }}
      >
        {tabs.map((tab) => (
          <TabButton
            key={tab.id}
            id={tab.id}
            label={tab.label}
            icon={tab.icon}
            color={tab.color}
            isActive={activeTab === tab.id}
            onClick={() => handleTabClick(tab.id)} children={undefined}          />
        ))}
      </div>

      {/* Tab Content */}
      <div style={{ minHeight: '600px' }}>
        {/* 🚀 TRADING TAB */}
        <Tab id="trading" label="Trading" icon="🚀" color="#28a745">
          <div
            style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}
          >
            {/* Left Column - Core Trading */}
            <div>
              <div
                style={{
                  background: '#d4edda',
                  padding: 16,
                  borderRadius: 12,
                  marginBottom: 20,
                  border: '1px solid #c3e6cb',
                }}
              >
                <h2
                  style={{
                    margin: '0 0 12px 0',
                    color: '#155724',
                    fontSize: '20px',
                  }}
                >
                  🚀 Quick Trade
                </h2>
                <QuickTrade />
              </div>

              <div
                style={{
                  background: '#fff',
                  padding: 16,
                  borderRadius: 12,
                  marginBottom: 20,
                  border: '1px solid #e9ecef',
                }}
              >
                <h2 style={{ margin: '0 0 12px 0', fontSize: '18px' }}>
                  📊 Positions
                </h2>
                <PositionsPanel />
              </div>

              <div
                style={{
                  background: '#fff',
                  padding: 16,
                  borderRadius: 12,
                  marginBottom: 20,
                  border: '1px solid #e9ecef',
                }}
              >
                <h2 style={{ margin: '0 0 12px 0', fontSize: '18px' }}>
                  💰 Wallets
                </h2>
                <WalletsPanel />
              </div>
            </div>

            {/* Right Column - Signals & Auto-Trading */}
            <div>
              <div
                style={{
                  background: '#fff',
                  padding: 16,
                  borderRadius: 12,
                  marginBottom: 20,
                  border: '1px solid #e9ecef',
                }}
              >
                <h2 style={{ margin: '0 0 12px 0', fontSize: '18px' }}>
                  📡 Live Signals
                </h2>
                <LiveSignalsPanel />
              </div>

              <div
                style={{
                  background: '#fff',
                  padding: 16,
                  borderRadius: 12,
                  marginBottom: 20,
                  border: '1px solid #e9ecef',
                }}
              >
                <h2 style={{ margin: '0 0 12px 0', fontSize: '18px' }}>
                  🤖 Enhanced Auto-Trading
                </h2>
                <EnhancedAutoTradingPanel />
              </div>

              <div
                style={{
                  background: '#fff',
                  padding: 16,
                  borderRadius: 12,
                  marginBottom: 20,
                  border: '1px solid #e9ecef',
                }}
              >
                <h2 style={{ margin: '0 0 12px 0', fontSize: '18px' }}>
                  📈 Market Data
                </h2>
                <MarketPanel />
              </div>
            </div>
          </div>
        </Tab>

        {/* 🛡️ RISK MANAGEMENT TAB */}
        <Tab id="risk" label="Risk Management" icon="🛡️" color="#dc3545">
          <div
            style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}
          >
            <div>
              <div
                style={{
                  background: '#f8d7da',
                  padding: 16,
                  borderRadius: 12,
                  marginBottom: 20,
                  border: '1px solid #f5c6cb',
                }}
              >
                <h2
                  style={{
                    margin: '0 0 12px 0',
                    color: '#721c24',
                    fontSize: '20px',
                  }}
                >
                  🛡️ Unified Risk Management
                </h2>
                <UnifiedRiskPanel />
              </div>

              <div
                style={{
                  background: '#fff',
                  padding: 16,
                  borderRadius: 12,
                  marginBottom: 20,
                  border: '1px solid #e9ecef',
                }}
              >
                <h2 style={{ margin: '0 0 12px 0', fontSize: '18px' }}>
                  🚨 Risk Guards
                </h2>
                <RiskGuardsPanel />
              </div>
            </div>

            <div>
              <div
                style={{
                  background: '#fff',
                  padding: 16,
                  borderRadius: 12,
                  marginBottom: 20,
                  border: '1px solid #e9ecef',
                }}
              >
                <h2 style={{ margin: '0 0 12px 0', fontSize: '18px' }}>
                  ⚡ Circuit Breakers
                </h2>
                <UnifiedCircuitBreakerPanel />
              </div>

              <div
                style={{
                  background: '#fff',
                  padding: 16,
                  borderRadius: 12,
                  marginBottom: 20,
                  border: '1px solid #e9ecef',
                }}
              >
                <h2 style={{ margin: '0 0 12px 0', fontSize: '18px' }}>
                  📊 Risk Panel
                </h2>
                <RiskPanel />
              </div>
            </div>
          </div>
        </Tab>

        {/* 📈 ANALYTICS TAB */}
        <Tab id="analytics" label="Analytics" icon="📈" color="#007bff">
          <div
            style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}
          >
            <div>
              <div
                style={{
                  background: '#d1ecf1',
                  padding: 16,
                  borderRadius: 12,
                  marginBottom: 20,
                  border: '1px solid #bee5eb',
                }}
              >
                <h2
                  style={{
                    margin: '0 0 12px 0',
                    color: '#0c5460',
                    fontSize: '20px',
                  }}
                >
                  📈 Performance Monitor
                </h2>
                <PerformancePanel />
              </div>

              <div
                style={{
                  background: '#fff',
                  padding: 16,
                  borderRadius: 12,
                  marginBottom: 20,
                  border: '1px solid #e9ecef',
                }}
              >
                <h2 style={{ margin: '0 0 12px 0', fontSize: '18px' }}>
                  📚 History
                </h2>
                <HistoryPanel />
              </div>
            </div>

            <div>
              <div
                style={{
                  background: '#fff',
                  padding: 16,
                  borderRadius: 12,
                  marginBottom: 20,
                  border: '1px solid #e9ecef',
                }}
              >
                <h2 style={{ margin: '0 0 12px 0', fontSize: '18px' }}>
                  📊 Enhanced Observability
                </h2>
                <EnhancedObservabilityPanel />
              </div>

              <div
                style={{
                  background: '#fff',
                  padding: 16,
                  borderRadius: 12,
                  marginBottom: 20,
                  border: '1px solid #e9ecef',
                }}
              >
                <h2 style={{ margin: '0 0 12px 0', fontSize: '18px' }}>
                  📋 Read-Only History
                </h2>
                <ReadOnlyHistoryPanel />
              </div>
            </div>
          </div>
        </Tab>

        {/* ⚙️ SYSTEM TAB */}
        <Tab id="system" label="System" icon="⚙️" color="#ffc107">
          <div
            style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}
          >
            <div>
              <div
                style={{
                  background: '#fff3cd',
                  padding: 16,
                  borderRadius: 12,
                  marginBottom: 20,
                  border: '1px solid #ffeaa7',
                }}
              >
                <h2
                  style={{
                    margin: '0 0 12px 0',
                    color: '#856404',
                    fontSize: '20px',
                  }}
                >
                  ⚙️ System Status
                </h2>
                <SystemPanel />
              </div>

              <div
                style={{
                  background: '#fff',
                  padding: 16,
                  borderRadius: 12,
                  marginBottom: 20,
                  border: '1px solid #e9ecef',
                }}
              >
                <h2 style={{ margin: '0 0 12px 0', fontSize: '18px' }}>
                  🚩 Feature Flags
                </h2>
                <FeatureFlagsPanel />
              </div>
            </div>

            <div>
              <div
                style={{
                  background: '#fff',
                  padding: 16,
                  borderRadius: 12,
                  marginBottom: 20,
                  border: '1px solid #e9ecef',
                }}
              >
                <h2 style={{ margin: '0 0 12px 0', fontSize: '18px' }}>
                  🔄 Refresh Manager
                </h2>
                <RefreshManagerPanel />
              </div>

              <div
                style={{
                  background: '#fff',
                  padding: 16,
                  borderRadius: 12,
                  marginBottom: 20,
                  border: '1px solid #e9ecef',
                }}
              >
                <h2 style={{ margin: '0 0 12px 0', fontSize: '18px' }}>
                  🧪 Validation & Testing
                </h2>
                <TestValidationPanel />
              </div>
            </div>
          </div>
        </Tab>

        {/* 🔧 ADMIN TAB */}
        <Tab id="admin" label="Admin" icon="🔧" color="#6c757d">
          <div
            style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}
          >
            <div>
              {/* MCP Integration removed */}

              <div
                style={{
                  background: '#fff',
                  padding: 16,
                  borderRadius: 12,
                  marginBottom: 20,
                  border: '1px solid #e9ecef',
                }}
              >
                <h2 style={{ margin: '0 0 12px 0', fontSize: '18px' }}>
                  🧪 Validation Panel
                </h2>
                <ValidationPanel />
              </div>
            </div>

            <div>
              <div
                style={{
                  background: '#fff',
                  padding: 16,
                  borderRadius: 12,
                  marginBottom: 20,
                  border: '1px solid #e9ecef',
                }}
              >
                <h2 style={{ margin: '0 0 12px 0', fontSize: '18px' }}>
                  🔍 Diagnostics
                </h2>
                <details style={{ marginBottom: 12 }}>
                  <summary>System Logs</summary>
                  <pre
                    style={{
                      whiteSpace: 'pre-wrap',
                      background: '#f6f8fa',
                      padding: 8,
                      borderRadius: 6,
                      maxHeight: 180,
                      overflow: 'auto',
                      fontSize: '12px',
                    }}
                  >
                    {log.join('\n')}
                  </pre>
                </details>
              </div>
            </div>
          </div>
        </Tab>
      </div>
    </div>
  );
}
