import React from 'react';
import EnhancedAutoTradingPanel from '../components/EnhancedAutoTradingPanel';
import { HistoryPanel } from '../components/HistoryPanel';
import { LiveSignalsPanel } from '../components/LiveSignalsPanel';
import { MarketPanel } from '../components/MarketPanel';
import { PositionsPanel } from '../components/PositionsPanel';
import { QuickTrade } from '../components/QuickTrade';
import { RiskPanel } from '../components/RiskPanel';
import { StatusCard } from '../components/StatusCard';
import { SystemPanel } from '../components/SystemPanel';
import { Toggles } from '../components/Toggles';
import { ValidationPanel } from '../components/ValidationPanel';
import { WalletsPanel } from '../components/WalletsPanel';
import { ensureToken, get, getApiBase } from '../lib/api';

export default function DashboardPage() {
    const [status, setStatus] = React.useState<any>(null);
    const [caps, setCaps] = React.useState<any>(null);
    const [modes, setModes] = React.useState<any>(null);
    const [strategyAuto, setStrategyAuto] = React.useState<{ AUTO_REGIME_ENABLED?: boolean; AUTO_WEIGHTS_ENABLED?: boolean } | null>(null);
    const [log, setLog] = React.useState<string[]>([]);

    const refresh = React.useCallback(async () => {
        setLog(l => [
            `[${new Date().toLocaleTimeString()}] refresh start (base=${getApiBase()})`,
            ...l
        ].slice(0, 50));
        await ensureToken();
        try {
            const s = await get('/api/v2/ws/pool/status');
            setStatus(s);
            Promise.all([
                get('/api/v2/ui/capabilities').catch(() => null),
                get('/api/v2/mode/dry-run').catch(() => null),
                get('/api/v2/mode/trading-paused').catch(() => null),
                get('/api/v2/mode/prob-model').catch(() => null),
                get('/api/v2/mode/autotrade').catch(() => null),
                get('/api/v2/mode/scheduler').catch(() => null),
                get('/api/v2/mode/ws-strategy').catch(() => null),
                get('/api/v2/mode/validation-warmup').catch(() => null),
                get('/api/v2/strategy/auto').catch(() => null),
            ]).then(([c, dry, paused, pm, at, sch, wsst, warm, auto]) => {
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
            });
            setLog(l => [
                `[${new Date().toLocaleTimeString()}] refresh ok`,
                ...l
            ].slice(0, 50));
        } catch (e: any) {
            setLog(l => [
                `[${new Date().toLocaleTimeString()}] refresh error: ${e?.message || e}`,
                ...l
            ].slice(0, 50));
        }
    }, []);

    React.useEffect(() => {
        refresh();
        const id = setInterval(refresh, 5000);
        return () => clearInterval(id);
    }, [refresh]);

    return (
        <div style={{ fontFamily: 'system-ui, sans-serif', padding: 16 }}>
            <h2>Genesis Dashboard</h2>
            <details style={{ marginBottom: 12 }}>
                <summary>Diagnostik</summary>
                <pre style={{ whiteSpace: 'pre-wrap', background: '#f6f8fa', padding: 8, borderRadius: 6, maxHeight: 180, overflow: 'auto' }}>
                    {log.join('\n')}
                </pre>
            </details>
            <StatusCard status={status} caps={caps} modes={modes} strategyAuto={strategyAuto} />
            <Toggles modes={modes} onChanged={() => { void refresh(); }} />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 16 }}>
                <div>
                    <h2 style={{ margin: '16px 0 8px' }}>Quick Trade</h2>
                    <QuickTrade />
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
                    <h2 style={{ margin: '16px 0 8px' }}>Enhanced Auto-Trading</h2>
                    <EnhancedAutoTradingPanel />
                </div>
                <div>
                    <h2 style={{ margin: '16px 0 8px' }}>Live Signals</h2>
                    <LiveSignalsPanel />
                </div>
                <div>
                    <h2 style={{ margin: '16px 0 8px' }}>Historik</h2>
                    <HistoryPanel />
                </div>
                <div>
                    <h2 style={{ margin: '16px 0 8px' }}>System</h2>
                    <SystemPanel />
                </div>
                <div>
                    <h2 style={{ margin: '16px 0 8px' }}>Validation</h2>
                    <ValidationPanel />
                </div>
            </div>
        </div>
    );
}


