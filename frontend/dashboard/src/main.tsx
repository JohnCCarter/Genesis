import React from 'react';
import { createRoot } from 'react-dom/client';
import { ensureToken, get, post } from './lib/api';
import { TradingPanel } from './components/TradingPanel';
import { PositionsPanel } from './components/PositionsPanel';
import { WalletsPanel } from './components/WalletsPanel';
import { RiskPanel } from './components/RiskPanel';
import { HistoryPanel } from './components/HistoryPanel';
import { MarketPanel } from './components/MarketPanel';
import { SystemPanel } from './components/SystemPanel';

function Badge({ ok, label }: { ok: boolean; label: string }) {
    return (
        <span
            style={{
                display: 'inline-block',
                padding: '2px 8px',
                borderRadius: 999,
                fontSize: 12,
                color: '#fff',
                background: ok ? '#2ea44f' : '#d29922',
                marginRight: 8,
            }}
        >
            {label}
        </span>
    );
}

function App() {
    const [status, setStatus] = React.useState<any>(null);
    const [caps, setCaps] = React.useState<any>(null);
    const [modes, setModes] = React.useState<any>(null);
    const [strategyAuto, setStrategyAuto] = React.useState<{ AUTO_REGIME_ENABLED?: boolean; AUTO_WEIGHTS_ENABLED?: boolean } | null>(null);
    const [loading, setLoading] = React.useState(false);

    const refresh = React.useCallback(async () => {
        await ensureToken();
        try {
            const [s, c, dry, paused, pm, at, sch, wsst, warm, auto] = await Promise.all([
                get('/api/v2/ws/pool/status'),
                get('/api/v2/ui/capabilities').catch(() => null),
                get('/api/v2/mode/dry-run').catch(() => null),
                get('/api/v2/mode/trading-paused').catch(() => null),
                get('/api/v2/mode/prob-model').catch(() => null),
                get('/api/v2/mode/autotrade').catch(() => null),
                get('/api/v2/mode/scheduler').catch(() => null),
                get('/api/v2/mode/ws-strategy').catch(() => null),
                get('/api/v2/mode/validation-warmup').catch(() => null),
                get('/api/v2/strategy/auto').catch(() => null),
            ]);
            setStatus(s);
            if (c) setCaps(c);
            if (auto) setStrategyAuto(auto);
            setModes({
                dry_run_enabled: dry ? !!dry.dry_run_enabled : undefined,
                trading_paused: paused ? !!paused.trading_paused : undefined,
                prob_model_enabled: pm ? !!pm.prob_model_enabled : undefined,
                autotrade_enabled: at ? !!at.autotrade_enabled : undefined,
                scheduler_running: sch ? !!sch.scheduler_running : undefined,
                ws_strategy_enabled: wsst ? !!wsst.ws_strategy_enabled : undefined,
                validation_on_start: warm ? !!warm.validation_on_start : undefined,
            });
        } catch {
            // ignore refresh errors here; UI will reflect last known state
        }
    }, []);

    React.useEffect(() => {
        refresh();
        const id = setInterval(refresh, 15000);
        return () => clearInterval(id);
    }, [refresh]);

    async function toggleWsStrategy(enabled: boolean) {
        try {
            setLoading(true);
            await post('/api/v2/mode/ws-strategy', { enabled });
            await refresh();
        } finally {
            setLoading(false);
        }
    }

    async function toggleValidation(enabled: boolean) {
        try {
            setLoading(true);
            await post('/api/v2/mode/validation-warmup', { enabled });
            await refresh();
        } finally {
            setLoading(false);
        }
    }

    async function toggleDryRun(enabled: boolean) {
        try {
            setLoading(true);
            await post('/api/v2/mode/dry-run', { enabled });
            await refresh();
        } finally {
            setLoading(false);
        }
    }

    async function toggleTradingPaused(enabled: boolean) {
        try {
            setLoading(true);
            await post('/api/v2/mode/trading-paused', { enabled });
            await refresh();
        } finally {
            setLoading(false);
        }
    }

    async function toggleProbModel(enabled: boolean) {
        try {
            setLoading(true);
            await post('/api/v2/mode/prob-model', { enabled });
            await refresh();
        } finally {
            setLoading(false);
        }
    }

    async function toggleAutotrade(enabled: boolean) {
        try {
            setLoading(true);
            await post('/api/v2/mode/autotrade', { enabled });
            await refresh();
        } finally {
            setLoading(false);
        }
    }

    async function toggleScheduler(enabled: boolean) {
        try {
            setLoading(true);
            await post('/api/v2/mode/scheduler', { enabled });
            await refresh();
        } finally {
            setLoading(false);
        }
    }

    return (
        <div style={{ fontFamily: 'system-ui, sans-serif', padding: 16 }}>
            <h2>Genesis Dashboard</h2>
            <div style={{ marginBottom: 12 }}>
                {status && (
                    <>
                        <Badge ok={!!status.main?.connected} label={status.main?.connected ? 'WS Connected' : 'WS Disc'} />
                        <Badge ok={!!status.main?.authenticated} label={status.main?.authenticated ? 'WS Auth' : 'No Auth'} />
                    </>
                )}
                {caps && (
                    <>
                        <Badge ok={!!caps.dry_run} label={caps.dry_run ? 'DRY_RUN' : 'LIVE'} />
                    </>
                )}
                {modes && (
                    <>
                        <Badge ok={!modes.trading_paused} label={modes.trading_paused ? 'Paused' : 'Trading'} />
                        {strategyAuto && typeof strategyAuto.AUTO_REGIME_ENABLED === 'boolean' && (
                            <Badge ok={!!strategyAuto.AUTO_REGIME_ENABLED} label={strategyAuto.AUTO_REGIME_ENABLED ? 'Auto‑Regim On' : 'Auto‑Regim Off'} />
                        )}
                        {strategyAuto && typeof strategyAuto.AUTO_WEIGHTS_ENABLED === 'boolean' && (
                            <Badge ok={!!strategyAuto.AUTO_WEIGHTS_ENABLED} label={strategyAuto.AUTO_WEIGHTS_ENABLED ? 'Auto‑Vikter On' : 'Auto‑Vikter Off'} />
                        )}
                        {typeof modes.dry_run_enabled === 'boolean' && (
                            <Badge ok={!!modes.dry_run_enabled} label={modes.dry_run_enabled ? 'DryRun On' : 'DryRun Off'} />
                        )}
                        {typeof modes.ws_strategy_enabled === 'boolean' && (
                            <Badge ok={!!modes.ws_strategy_enabled} label={modes.ws_strategy_enabled ? 'WS Strategy On' : 'WS Strategy Off'} />
                        )}
                        {typeof modes.validation_on_start === 'boolean' && (
                            <Badge ok={!!modes.validation_on_start} label={modes.validation_on_start ? 'Validation On' : 'Validation Off'} />
                        )}
                        {typeof modes.prob_model_enabled === 'boolean' && (
                            <Badge ok={!!modes.prob_model_enabled} label={modes.prob_model_enabled ? 'ProbModel On' : 'ProbModel Off'} />
                        )}
                        {typeof modes.autotrade_enabled === 'boolean' && (
                            <Badge ok={!!modes.autotrade_enabled} label={modes.autotrade_enabled ? 'Autotrade On' : 'Autotrade Off'} />
                        )}
                        {typeof modes.scheduler_running === 'boolean' && (
                            <Badge ok={!!modes.scheduler_running} label={modes.scheduler_running ? 'Scheduler On' : 'Scheduler Off'} />
                        )}
                    </>
                )}
            </div>
            <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
                <button disabled={loading} onClick={() => toggleWsStrategy(true)}>
                    WS Strategy On
                </button>
                <button disabled={loading} onClick={() => toggleWsStrategy(false)}>
                    WS Strategy Off
                </button>
                <button disabled={loading} onClick={() => toggleValidation(true)}>
                    Validation On
                </button>
                <button disabled={loading} onClick={() => toggleValidation(false)}>
                    Validation Off
                </button>
            </div>
            <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
                <button disabled={loading} onClick={() => toggleDryRun(true)}>
                    Dry Run On
                </button>
                <button disabled={loading} onClick={() => toggleDryRun(false)}>
                    Dry Run Off
                </button>
                <button disabled={loading} onClick={() => toggleTradingPaused(true)}>
                    Pause Trading
                </button>
                <button disabled={loading} onClick={() => toggleTradingPaused(false)}>
                    Resume Trading
                </button>
            </div>
            <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
                <button disabled={loading} onClick={() => toggleProbModel(true)}>
                    Prob Model On
                </button>
                <button disabled={loading} onClick={() => toggleProbModel(false)}>
                    Prob Model Off
                </button>
                <button disabled={loading} onClick={() => toggleAutotrade(true)}>
                    Autotrade On
                </button>
                <button disabled={loading} onClick={() => toggleAutotrade(false)}>
                    Autotrade Off
                </button>
                <button disabled={loading} onClick={() => toggleScheduler(true)}>
                    Start Scheduler
                </button>
                <button disabled={loading} onClick={() => toggleScheduler(false)}>
                    Stop Scheduler
                </button>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 16 }}>
                <div>
                    <h2 style={{ margin: '16px 0 8px' }}>Trading</h2>
                    <TradingPanel />
                </div>
                <div>
                    <h2 style={{ margin: '16px 0 8px' }}>Positions</h2>
                    <PositionsPanel />
                </div>
                <div>
                    <h2 style={{ margin: '16px 0 8px' }}>Wallets</h2>
                    <WalletsPanel />
                </div>
                <div>
                    <h2 style={{ margin: '16px 0 8px' }}>Risk</h2>
                    <RiskPanel />
                </div>
                <div>
                    <h2 style={{ margin: '16px 0 8px' }}>Market</h2>
                    <MarketPanel />
                </div>
                <div>
                    <h2 style={{ margin: '16px 0 8px' }}>Historik</h2>
                    <HistoryPanel />
                </div>
                <div>
                    <h2 style={{ margin: '16px 0 8px' }}>System</h2>
                    <SystemPanel />
                </div>
            </div>
            <pre style={{ background: '#f6f8fa', padding: 12, borderRadius: 6 }}>
                {JSON.stringify({ status, caps, modes }, null, 2)}
            </pre>
        </div>
    );
}

createRoot(document.getElementById('root')!).render(<App />);
