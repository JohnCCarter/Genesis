import React from 'react';
import { post } from '../lib/api';

type Modes = {
    dry_run_enabled?: boolean;
    trading_paused?: boolean;
    prob_model_enabled?: boolean;
    autotrade_enabled?: boolean;
    scheduler_running?: boolean;
    ws_strategy_enabled?: boolean;
    validation_on_start?: boolean;
};

export function Toggles({ modes, onChanged }: { modes?: Modes | null; onChanged: (path?: string, enabled?: boolean) => Promise<void> | void }) {
    const [busyKey, setBusyKey] = React.useState<string | null>(null);

    async function call(path: string, enabled: boolean) {
        const k = `${path}:${enabled ? '1' : '0'}`;
        try {
            setBusyKey(k);
            await post(path, { enabled });
        } finally {
            setBusyKey(null);
            // Kör refresh utan att blockera nästa klick
            try { void onChanged?.(path, enabled); } catch {}
        }
    }

    const chip = (on: boolean | undefined) => (
        <span style={{
            display: 'inline-block', padding: '2px 6px', borderRadius: 10,
            fontSize: 11, color: '#fff', background: on ? '#2ea44f' : '#6a737d', marginRight: 6,
        }}>{on ? 'On' : 'Off'}</span>
    );

    return (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(200px,1fr))', gap: 8, marginBottom: 16 }}>
            <div>
                <div style={{ marginBottom: 4 }}>WS Strategy {chip(!!modes?.ws_strategy_enabled)}</div>
            <button disabled={busyKey === '/api/v2/mode/ws-strategy:1'} onClick={() => call('/api/v2/mode/ws-strategy', true)}>WS Strategy On</button>
            <button disabled={busyKey === '/api/v2/mode/ws-strategy:0'} onClick={() => call('/api/v2/mode/ws-strategy', false)}>WS Strategy Off</button>
            </div>
            <div>
                <div style={{ marginBottom: 4 }}>Validation Warmup {chip(!!modes?.validation_on_start)}</div>
            <button disabled={busyKey === '/api/v2/mode/validation-warmup:1'} onClick={() => call('/api/v2/mode/validation-warmup', true)}>Validation On</button>
            <button disabled={busyKey === '/api/v2/mode/validation-warmup:0'} onClick={() => call('/api/v2/mode/validation-warmup', false)}>Validation Off</button>
            </div>
            <div>
                <div style={{ marginBottom: 4 }}>Dry Run {chip(!!modes?.dry_run_enabled)}</div>
            <button disabled={busyKey === '/api/v2/mode/dry-run:1'} onClick={() => call('/api/v2/mode/dry-run', true)}>Dry Run On</button>
            <button disabled={busyKey === '/api/v2/mode/dry-run:0'} onClick={() => call('/api/v2/mode/dry-run', false)}>Dry Run Off</button>
            </div>
            <div>
                <div style={{ marginBottom: 4 }}>Trading Paused {chip(!!modes?.trading_paused)}</div>
            <button disabled={busyKey === '/api/v2/mode/trading-paused:1'} onClick={() => call('/api/v2/mode/trading-paused', true)}>Pause Trading</button>
            <button disabled={busyKey === '/api/v2/mode/trading-paused:0'} onClick={() => call('/api/v2/mode/trading-paused', false)}>Resume Trading</button>
            </div>
            <div>
                <div style={{ marginBottom: 4 }}>Prob Model {chip(!!modes?.prob_model_enabled)}</div>
            <button disabled={busyKey === '/api/v2/mode/prob-model:1'} onClick={() => call('/api/v2/mode/prob-model', true)}>Prob Model On</button>
            <button disabled={busyKey === '/api/v2/mode/prob-model:0'} onClick={() => call('/api/v2/mode/prob-model', false)}>Prob Model Off</button>
            </div>
            <div>
                <div style={{ marginBottom: 4 }}>Autotrade {chip(!!modes?.autotrade_enabled)}</div>
            <button disabled={busyKey === '/api/v2/mode/autotrade:1'} onClick={() => call('/api/v2/mode/autotrade', true)}>Autotrade On</button>
            <button disabled={busyKey === '/api/v2/mode/autotrade:0'} onClick={() => call('/api/v2/mode/autotrade', false)}>Autotrade Off</button>
            </div>
            <div>
                <div style={{ marginBottom: 4 }}>Scheduler {chip(!!modes?.scheduler_running)}</div>
            <button disabled={busyKey === '/api/v2/mode/scheduler:1'} onClick={() => call('/api/v2/mode/scheduler', true)}>Start Scheduler</button>
            <button disabled={busyKey === '/api/v2/mode/scheduler:0'} onClick={() => call('/api/v2/mode/scheduler', false)}>Stop Scheduler</button>
            </div>
        </div>
    );
}
