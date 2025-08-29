import { DebugPage as DebugComponent } from '../components/DebugPage';

export default function DebugPage() {
    return (
        <div style={{ fontFamily: 'system-ui, sans-serif', padding: 16 }}>
            <h2>Debug</h2>
            <DebugComponent />
        </div>
    );
}
