import { createRoot } from 'react-dom/client';
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom';
import DashboardPage from './pages/Dashboard';
import DebugPage from './pages/Debug';

function App() {
    return (
        <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
            <div style={{ fontFamily: 'system-ui, sans-serif', padding: 16 }}>
                <h2>Genesis</h2>
                <nav style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
                    <Link to="/">Dashboard</Link>
                    <Link to="/debug">Debug</Link>

                </nav>
                <Routes>
                    <Route path="/" element={<DashboardPage />} />
                    <Route path="/debug" element={<DebugPage />} />

                </Routes>
            </div>
        </BrowserRouter>
    );
}

createRoot(document.getElementById('root')!).render(<App />);
