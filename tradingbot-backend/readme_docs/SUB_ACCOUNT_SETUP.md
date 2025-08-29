# Bitfinex Sub-Account API Setup Guide

## 🔍 **Problem: Sub-Account API-nycklar**

### **Vad som händer:**
- ✅ **API-nycklar:** Från sub-account för simulerad trading
- ✅ **Read permissions:** Fungerar (account info, hämta ordrar)
- ❌ **Write permissions:** Fungerar inte (lägga ordrar)

### **Orsak:**
Sub-accounts för simulerad trading har ofta begränsade permissions för säkerhet.

## 🛠️ **Lösningar:**

### **Alternativ 1: Aktivera Write permissions för sub-account**

1. **Gå till Bitfinex Sub-Account settings:**
   - Logga in på https://www.bitfinex.com
   - Gå till **Account** → **Sub-Accounts**
   - Välj ditt sub-account

2. **Kontrollera API permissions:**
   - Gå till **API Keys** för sub-account
   - Kontrollera att följande är aktiverade:
     - ✅ **Read** - För att läsa account info
     - ✅ **Write** - För att lägga ordrar
     - ✅ **Trading** - För att handla

3. **Aktivera Write permissions:**
   - Om Write permissions inte är aktiverade, aktivera dem
   - Detta kan kräva 2FA-bekräftelse

### **Alternativ 2: Skapa API-nycklar för huvudaccount**

1. **Gå till huvudaccount:**
   - Logga in på https://www.bitfinex.com
   - Gå till **Account** → **API Keys**

2. **Skapa nya API-nycklar:**
   - Klicka **Create New API Key**
   - Aktivera:
     - ✅ **Read**
     - ✅ **Write**
     - ✅ **Trading**

3. **Uppdatera .env-filen:**
   ```env
   BITFINEX_API_KEY=din_nya_api_key
   BITFINEX_API_SECRET=din_nya_api_secret
   ```

### **Alternativ 3: Använd Paper Trading**

Om du vill testa utan risk, använd paper trading:

1. **Skapa paper trading account**
2. **Skapa API-nycklar för paper trading**
3. **Uppdatera .env-filen**

## 🔧 **Testa efter ändringar:**

```bash
python test_bitfinex_direct.py
```

## ⚠️ **Viktigt:**

- **Sub-accounts** har ofta begränsade permissions
- **Write permissions** krävs för orderläggning
- **Trading permissions** krävs för att faktiskt handla
- **2FA** kan krävas för att ändra permissions

## 📋 **Checklista:**

- [ ] Kontrollera sub-account API permissions
- [ ] Aktivera Write permissions om nödvändigt
- [ ] Testa med nya API-nycklar
- [ ] Verifiera att orderläggning fungerar
