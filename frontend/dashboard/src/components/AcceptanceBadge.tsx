import React from 'react';

type Acceptance = {
    ok: boolean;
    thresholds?: { p95_ms_max?: number; p99_ms_max?: number; max_429_per_hour?: number; max_503_per_hour?: number };
    observed?: { p95?: number; p99?: number; 429?: number; 503?: number };
};

export function AcceptanceBadge({ acceptance }: { acceptance: Acceptance | null }) {
    const ok = !!acceptance?.ok;
    const p95 = acceptance?.observed?.p95 ?? undefined;
    const p99 = acceptance?.observed?.p99 ?? undefined;
    const e429 = (acceptance?.observed as any)?.["429"]; // numeric key access
    const e503 = (acceptance?.observed as any)?.["503"]; // numeric key access

    const bg = ok ? '#12B886' : '#F03E3E';
    const fg = '#fff';

    return (
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
            <span
                title={ok ? 'Acceptance OK' : 'Acceptance degraded'}
                style={{
                    display: 'inline-block',
                    padding: '4px 10px',
                    borderRadius: 999,
                    background: bg,
                    color: fg,
                    fontSize: 12,
                    fontWeight: 600,
                }}
            >
                {ok ? 'ACCEPTANCE: OK' : 'ACCEPTANCE: DEGRADED'}
            </span>
            <span style={{ fontSize: 12, color: '#555' }}>
                {p95 !== undefined && p99 !== undefined ? `p95=${p95}ms · p99=${p99}ms` : ''}
                {(e429 !== undefined || e503 !== undefined) ? ` · 429=${e429 ?? 0} · 503=${e503 ?? 0}` : ''}
            </span>
        </div>
    );
}
