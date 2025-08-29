
export function Badge({ ok, label }: { ok: boolean; label: string }) {
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

type Modes = {
    dry_run_enabled?: boolean;
    trading_paused?: boolean;
    prob_model_enabled?: boolean;
    autotrade_enabled?: boolean;
    scheduler_running?: boolean;
    ws_strategy_enabled?: boolean;
    validation_on_start?: boolean;
};

export function StatusCard({ status, caps, modes, strategyAuto }: { status: any; caps: any; modes: Modes | null; strategyAuto: { AUTO_REGIME_ENABLED?: boolean; AUTO_WEIGHTS_ENABLED?: boolean } | null }) {
    return (
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
                    <Badge ok={!modes.trading_paused!} label={modes.trading_paused ? 'Paused' : 'Trading'} />
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
    );
}
