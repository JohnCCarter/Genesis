import React from 'react';

type NodeProps = {
    name?: string;
    data: any;
    level: number;
    defaultCollapseLevel: number;
    expandAllSignal: number;
    collapseAllSignal: number;
};

function isObject(v: any) {
    return v !== null && typeof v === 'object' && !Array.isArray(v);
}

function Key({ children }: { children: React.ReactNode }) {
    return <span style={{ color: '#0b7285' }}>{children}</span>;
}

function Val({ v }: { v: any }) {
    if (typeof v === 'number') return <span style={{ color: '#5c7cfa', fontFamily: 'monospace' }}>{v}</span>;
    if (typeof v === 'boolean') return <span style={{ color: v ? '#2f9e44' : '#e03131' }}>{String(v)}</span>;
    if (v === null) return <span style={{ color: '#868e96' }}>null</span>;
    return <span style={{ color: '#495057' }}>'{String(v)}'</span>;
}

function Summary({ data }: { data: any }) {
    if (Array.isArray(data)) return <em style={{ color: '#868e96' }}>[{data.length} items]</em>;
    if (isObject(data)) return <em style={{ color: '#868e96' }}>{`{${Object.keys(data).length} keys}`}</em>;
    return null;
}

function Node({ name, data, level, defaultCollapseLevel, expandAllSignal, collapseAllSignal }: NodeProps) {
    const isContainer = Array.isArray(data) || isObject(data);
    const [collapsed, setCollapsed] = React.useState<boolean>(level >= defaultCollapseLevel);

    React.useEffect(() => {
        if (expandAllSignal > 0) setCollapsed(false);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [expandAllSignal]);
    React.useEffect(() => {
        if (collapseAllSignal > 0) setCollapsed(true);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [collapseAllSignal]);

    const indent = 12 * level;
    const toggle = () => setCollapsed(c => !c);
    const hasName = name !== undefined && name !== '';

    if (!isContainer) {
        return (
            <div style={{ paddingLeft: indent }}>
                {hasName && <><Key>{name}</Key>: </>}
                <Val v={data} />
            </div>
        );
    }

    const entries = Array.isArray(data)
        ? data.map((v, i) => ({ k: String(i), v }))
        : Object.keys(data).map(k => ({ k, v: (data as any)[k] }));

    return (
        <div style={{ paddingLeft: indent }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <button onClick={toggle} style={{ border: '1px solid #dee2e6', background: '#fff', borderRadius: 4, padding: '0 6px', fontSize: 11, height: 20, lineHeight: '18px', cursor: 'pointer' }}>
                    {collapsed ? '▶' : '▼'}
                </button>
                {hasName && <Key>{name}</Key>}
                <span style={{ color: '#868e96' }}>{Array.isArray(data) ? 'Array' : 'Object'}</span>
                <Summary data={data} />
            </div>
            {!collapsed && (
                <div style={{ marginTop: 4 }}>
                    {entries.map(({ k, v }) => (
                        <Node
                            key={k}
                            name={k}
                            data={v}
                            level={level + 1}
                            defaultCollapseLevel={defaultCollapseLevel}
                            expandAllSignal={expandAllSignal}
                            collapseAllSignal={collapseAllSignal}
                        />
                    ))}
                </div>
            )}
        </div>
    );
}

export function JsonTree({ data, defaultCollapseLevel = 2, controls, expandAllSignal, collapseAllSignal }: { data: any; defaultCollapseLevel?: number; controls?: React.ReactNode; expandAllSignal?: number; collapseAllSignal?: number }) {
    const expandSig = expandAllSignal ?? 0;
    const collapseSig = collapseAllSignal ?? 0;
    return (
        <div style={{ background: '#f6f8fa', border: '1px solid #e9ecef', borderRadius: 6, padding: 8 }}>
            {controls}
            <Node
                data={data}
                level={0}
                defaultCollapseLevel={defaultCollapseLevel}
                expandAllSignal={expandSig}
                collapseAllSignal={collapseSig}
            />
        </div>
    );
}
