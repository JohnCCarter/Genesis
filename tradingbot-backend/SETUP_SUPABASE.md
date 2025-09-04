# 🚀 Supabase MCP Server Setup

## 📋 **Vad du behöver göra:**

### **1. Skapa .env-fil**

Skapa en `.env`-fil i `tradingbot-backend/` med följande innehåll:

```bash
# Supabase MCP Server
SUPABASE_URL=https://kxibqgvpdfmklvwhmcry.supabase.co
SUPABASE_ANON_KEY=din_anon_key_här
SUPABASE_SERVICE_ROLE_KEY=din_service_role_key_här
MCP_SERVER_URL=https://kxibqgvpdfmklvwhmcry.supabase.co/functions/v1/mcp_server
```

### **2. Hämta Supabase-nycklar**

1. Gå till [Supabase Dashboard](https://supabase.com/dashboard)
2. Välj ditt projekt
3. Gå till **Settings** → **API**
4. Kopiera:
   - **Project URL** → `SUPABASE_URL`
   - **anon public** → `SUPABASE_ANON_KEY`
   - **service_role secret** → `SUPABASE_SERVICE_ROLE_KEY`

### **3. Skapa nödvändiga tabeller**

Kör följande SQL i Supabase SQL Editor:

```sql
-- Trading status tabell
CREATE TABLE IF NOT EXISTS trading_status (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL UNIQUE,
    status TEXT DEFAULT 'idle',
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Trades tabell
CREATE TABLE IF NOT EXISTS trades (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    quantity DECIMAL NOT NULL,
    price DECIMAL NOT NULL,
    executed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- MCP sessions tabell
CREATE TABLE IF NOT EXISTS mcp_sessions (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL UNIQUE,
    user_id TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_activity TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Lägg till RLS (Row Level Security)
ALTER TABLE trading_status ENABLE ROW LEVEL SECURITY;
ALTER TABLE trades ENABLE ROW LEVEL SECURITY;
ALTER TABLE mcp_sessions ENABLE ROW LEVEL SECURITY;

-- Skapa policies (tillåt alla för nu, kan begränsas senare)
CREATE POLICY "Allow all operations" ON trading_status FOR ALL USING (true);
CREATE POLICY "Allow all operations" ON trades FOR ALL USING (true);
CREATE POLICY "Allow all operations" ON mcp_sessions FOR ALL USING (true);

-- Lägg till testdata
INSERT INTO trading_status (user_id, status)
VALUES ('genesis_bot', 'idle')
ON CONFLICT (user_id) DO NOTHING;
```

### **4. Testa integrationen**

```bash
# Från projektroten
cd tradingbot-backend
python test_mcp_integration_simple.py
```

## 🔧 **Vad som händer:**

1. **MCP-klienten** ansluter till din Supabase Edge Function
2. **Genesis** kan nu använda MCP-tools för:
   - Hämta trading-status
   - Exekvera trades
   - Hantera sessions
3. **Alla data** sparas i Supabase för persistent lagring

## 🚨 **Viktigt:**

- **Lägg aldrig till .env i Git** (redan i .gitignore)
- **Service Role Key** har full åtkomst - håll den säker
- **Anon Key** kan delas offentligt (begränsad åtkomst)

## ✅ **När du är klar:**

- MCP-servern är integrerad med Genesis
- Du kan använda `/api/v2/mcp/*` endpoints
- Trading-data sparas i Supabase
- Allt fungerar via JSON-RPC 2.0 protokollet
