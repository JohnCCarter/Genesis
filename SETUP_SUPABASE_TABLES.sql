-- =====================================================
-- Supabase Tabeller för Genesis Trading Bot MCP Server
-- =====================================================

-- 1. Trading Status Tabell
CREATE TABLE IF NOT EXISTS trading_status (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'idle',
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    active_positions INTEGER DEFAULT 0,
    total_pnl DECIMAL(20,8) DEFAULT 0,
    daily_pnl DECIMAL(20,8) DEFAULT 0,
    risk_level TEXT DEFAULT 'medium',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Trades Tabell
CREATE TABLE IF NOT EXISTS trades (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    quantity DECIMAL(20,8) NOT NULL,
    price DECIMAL(20,8) NOT NULL,
    executed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status TEXT DEFAULT 'executed',
    pnl DECIMAL(20,8) DEFAULT 0,
    fees DECIMAL(20,8) DEFAULT 0,
    strategy TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. MCP Sessions Tabell
CREATE TABLE IF NOT EXISTS mcp_sessions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    session_id TEXT UNIQUE NOT NULL,
    user_id TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_activity TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status TEXT DEFAULT 'active'
);

-- 4. Performance Metrics Tabell
CREATE TABLE IF NOT EXISTS performance_metrics (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    win_rate DECIMAL(5,2) DEFAULT 0,
    total_pnl DECIMAL(20,8) DEFAULT 0,
    max_drawdown DECIMAL(20,8) DEFAULT 0,
    sharpe_ratio DECIMAL(10,4) DEFAULT 0,
    calculated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 5. Strategy Parameters Tabell
CREATE TABLE IF NOT EXISTS strategy_parameters (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id TEXT NOT NULL,
    strategy_name TEXT NOT NULL,
    parameters JSONB NOT NULL DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =====================================================
-- Index för prestanda
-- =====================================================

-- Trading status index
CREATE INDEX IF NOT EXISTS idx_trading_status_user_id ON trading_status(user_id);
CREATE INDEX IF NOT EXISTS idx_trading_status_last_updated ON trading_status(last_updated);

-- Trades index
CREATE INDEX IF NOT EXISTS idx_trades_user_id ON trades(user_id);
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_executed_at ON trades(executed_at);
CREATE INDEX IF NOT EXISTS idx_trades_side ON trades(side);

-- MCP sessions index
CREATE INDEX IF NOT EXISTS idx_mcp_sessions_user_id ON mcp_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_mcp_sessions_session_id ON mcp_sessions(session_id);

-- Performance metrics index
CREATE INDEX IF NOT EXISTS idx_performance_metrics_user_id ON performance_metrics(user_id);
CREATE INDEX IF NOT EXISTS idx_performance_metrics_timeframe ON performance_metrics(timeframe);

-- Strategy parameters index
CREATE INDEX IF NOT EXISTS idx_strategy_parameters_user_id ON strategy_parameters(user_id);
CREATE INDEX IF NOT EXISTS idx_strategy_parameters_strategy_name ON strategy_parameters(strategy_name);

-- =====================================================
-- RLS (Row Level Security) Policies
-- =====================================================

-- Aktivera RLS på alla tabeller
ALTER TABLE trading_status ENABLE ROW LEVEL SECURITY;
ALTER TABLE trades ENABLE ROW LEVEL SECURITY;
ALTER TABLE mcp_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE performance_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE strategy_parameters ENABLE ROW LEVEL SECURITY;

-- RLS Policy för trading_status
CREATE POLICY "Users can view own trading status" ON trading_status
    FOR SELECT USING (auth.uid()::text = user_id);

CREATE POLICY "Users can update own trading status" ON trading_status
    FOR UPDATE USING (auth.uid()::text = user_id);

CREATE POLICY "Users can insert own trading status" ON trading_status
    FOR INSERT WITH CHECK (auth.uid()::text = user_id);

-- RLS Policy för trades
CREATE POLICY "Users can view own trades" ON trades
    FOR SELECT USING (auth.uid()::text = user_id);

CREATE POLICY "Users can insert own trades" ON trades
    FOR INSERT WITH CHECK (auth.uid()::text = user_id);

-- RLS Policy för mcp_sessions
CREATE POLICY "Users can view own sessions" ON mcp_sessions
    FOR SELECT USING (auth.uid()::text = user_id);

CREATE POLICY "Users can insert own sessions" ON mcp_sessions
    FOR INSERT WITH CHECK (auth.uid()::text = user_id);

CREATE POLICY "Users can update own sessions" ON mcp_sessions
    FOR UPDATE USING (auth.uid()::text = user_id);

-- RLS Policy för performance_metrics
CREATE POLICY "Users can view own performance" ON performance_metrics
    FOR SELECT USING (auth.uid()::text = user_id);

CREATE POLICY "Users can insert own performance" ON performance_metrics
    FOR INSERT WITH CHECK (auth.uid()::text = user_id);

-- RLS Policy för strategy_parameters
CREATE POLICY "Users can view own strategies" ON strategy_parameters
    FOR SELECT USING (auth.uid()::text = user_id);

CREATE POLICY "Users can insert own strategies" ON strategy_parameters
    FOR INSERT WITH CHECK (auth.uid()::text = user_id);

CREATE POLICY "Users can update own strategies" ON strategy_parameters
    FOR UPDATE USING (auth.uid()::text = user_id);

-- =====================================================
-- Exempel-data för testing
-- =====================================================

-- Lägg till exempel trading status för genesis_bot
INSERT INTO trading_status (user_id, status, active_positions, total_pnl, daily_pnl, risk_level)
VALUES ('genesis_bot', 'active', 2, 1250.50, 45.20, 'medium')
ON CONFLICT (user_id) DO UPDATE SET
    status = EXCLUDED.status,
    last_updated = NOW(),
    active_positions = EXCLUDED.active_positions,
    total_pnl = EXCLUDED.total_pnl,
    daily_pnl = EXCLUDED.daily_pnl,
    risk_level = EXCLUDED.risk_level;

-- Lägg till exempel trades
INSERT INTO trades (user_id, symbol, side, quantity, price, pnl, strategy)
VALUES
    ('genesis_bot', 'BTCUSD', 'buy', 0.001, 45000.00, 25.50, 'trend_following'),
    ('genesis_bot', 'ETHUSD', 'sell', 0.01, 3200.00, -12.30, 'mean_reversion')
ON CONFLICT DO NOTHING;

-- Lägg till exempel performance metrics
INSERT INTO performance_metrics (user_id, timeframe, total_trades, winning_trades, losing_trades, win_rate, total_pnl)
VALUES ('genesis_bot', '1d', 15, 9, 6, 60.00, 1250.50)
ON CONFLICT (user_id, timeframe) DO UPDATE SET
    total_trades = EXCLUDED.total_trades,
    winning_trades = EXCLUDED.winning_trades,
    losing_trades = EXCLUDED.losing_trades,
    win_rate = EXCLUDED.win_rate,
    total_pnl = EXCLUDED.total_pnl,
    calculated_at = NOW();

-- Lägg till exempel strategy parameters
INSERT INTO strategy_parameters (user_id, strategy_name, parameters)
VALUES ('genesis_bot', 'trend_following', '{"rsi_period": 14, "ema_period": 20, "stop_loss": 0.02}')
ON CONFLICT (user_id, strategy_name) DO UPDATE SET
    parameters = EXCLUDED.parameters,
    updated_at = NOW();

-- =====================================================
-- Kommentarer
-- =====================================================

/*
INSTRUKTIONER:

1. Kör denna SQL i Supabase SQL Editor
2. Tabellerna skapas automatiskt med RLS-policies
3. Exempel-data läggs till för testing
4. MCP-servern kan nu lagra och hämta riktig data

NOTERA:
- RLS-policies säkerställer att användare bara kan se sin egen data
- Alla tabeller har index för snabb sökning
- Exempel-data finns för att testa MCP-integrationen
*/
