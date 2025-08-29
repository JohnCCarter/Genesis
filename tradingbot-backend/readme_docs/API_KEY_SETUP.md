# Bitfinex API Key Setup Guide

## 🔑 **API Key Problem: `"apikey: invalid"`**

### **Möjliga orsaker:**

1. **API-nyckeln är inte aktiverad för trading**
2. **API-nyckeln är för testmiljö men används mot production**
3. **API-nyckeln har inte rätt permissions**
4. **API-nyckeln är korrupt eller felaktig**

### **Steg för att fixa:**

#### **1. Kontrollera API Key på Bitfinex:**
- Gå till https://www.bitfinex.com/settings/api
- Kontrollera att API-nyckeln är **aktiverad**
- Kontrollera att den har **trading permissions**
- Kontrollera att den inte är **restricted till vissa IP-adresser**

#### **2. API Key Permissions som krävs:**
- ✅ **Read** - För att läsa account info
- ✅ **Write** - För att lägga ordrar
- ✅ **Trading** - För att handla

#### **3. Test vs Production:**
- Om du använder **test API keys**, använd test URL: `https://test.bitfinex.com`
- Om du använder **production API keys**, använd production URL: `https://api.bitfinex.com`

#### **4. Uppdatera .env filen:**
```env
# För testmiljö
BITFINEX_API_URL=https://test.bitfinex.com
BITFINEX_API_KEY=din_test_api_key
BITFINEX_API_SECRET=din_test_api_secret

# För production
BITFINEX_API_URL=https://api.bitfinex.com
BITFINEX_API_KEY=din_production_api_key
BITFINEX_API_SECRET=din_production_api_secret
```

#### **5. Testa API-nyckeln:**
```bash
python test_bitfinex_direct.py
```

### **Vanliga fel och lösningar:**

| Fel | Orsak | Lösning |
|-----|-------|---------|
| `"apikey: invalid"` | API-nyckeln är inte aktiverad | Aktivera API-nyckeln på Bitfinex |
| `"nonce: small"` | Nonce-värdet är för litet | Använd större nonce (fixat) |
| `"error": "10114"` | API-nyckeln har inte rätt permissions | Lägg till trading permissions |
| `"error": "10100"` | API-nyckeln är felaktig | Skapa ny API-nyckel |

### **Säkerhetsrekommendationer:**

1. **Använd test API keys för utveckling**
2. **Begränsa API-nyckeln till specifika IP-adresser**
3. **Aktivera endast nödvändiga permissions**
4. **Använd starka secrets**
5. **Roterar API-nycklar regelbundet**

### **Testa efter fix:**

```bash
# Testa account info
curl -X POST "https://api.bitfinex.com/v2/auth/r/info/user" \
  -H "bfx-apikey: YOUR_API_KEY" \
  -H "bfx-nonce: $(date +%s%6N)" \
  -H "bfx-signature: YOUR_SIGNATURE" \
  -H "Content-Type: application/json"
```
