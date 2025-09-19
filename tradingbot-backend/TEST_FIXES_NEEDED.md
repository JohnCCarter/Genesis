# Testjusteringar som behöver göras

## 📊 **Aktuell teststatus:**
- **73 totalt tester** skapade
- **55 tester passerar** (75% framgångsgrad)
- **18 tester behöver justeringar**

## 🔧 **Testjusteringar som behöver göras:**

### 1. **ConfigStore - Saknade metoder**
**Problem:** `get_store_stats()` metod saknas
```python
# Behöver läggas till i ConfigStore:
def get_store_stats(self) -> Dict[str, Any]:
    """Hämta statistik för store."""
    with sqlite3.connect(self.db_path) as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM config_values")
        total_keys = cursor.fetchone()[0]
        
        cursor = conn.execute("SELECT COUNT(DISTINCT key) FROM config_values")
        unique_keys = cursor.fetchone()[0]
        
        return {
            "total_keys": total_keys,
            "unique_keys": unique_keys,
            "db_path": self.db_path
        }
```

### 2. **ConfigStore - Database schema problem**
**Problem:** `updated_at` kolumn saknas i history tabellen
```sql
-- Behöver läggas till i _create_tables():
CREATE TABLE IF NOT EXISTS config_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    source TEXT NOT NULL,
    user TEXT,
    generation INTEGER NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,  -- <-- Denna kolumn saknas
    UNIQUE(key, generation)
);
```

### 3. **ConfigStore - atomic_compare_and_set parametrar**
**Problem:** Fel antal parametrar i testet
```python
# Fixa i testet:
success = self.store.atomic_compare_and_set(
    "TEST_KEY",           # key
    "new_value",          # new_value  
    "old_value",          # expected_value
    "test_user"           # user
)
# Ta bort extra parametrar
```

### 4. **ConfigCache - Saknade metoder**
**Problem:** `get_cache_stats()` metod saknas
```python
# Behöver läggas till i ConfigCache:
def get_cache_stats(self) -> Dict[str, Any]:
    """Hämta statistik för cache."""
    return {
        "total_cached": len(self._cache),
        "cache_hits": self._cache_hits,
        "cache_misses": self._cache_misses,
        "last_invalidation": self._last_invalidation
    }
```

### 5. **ConfigCache - Return type problem**
**Problem:** Tester förväntar sig `CacheEntry` objekt men får strängar
```python
# Fixa i ConfigCache.get() metoden:
def get(self, key: str, context: ConfigContext = None) -> CacheEntry | None:
    # Returnera CacheEntry objekt istället för bara värde
    if cache_entry:
        return cache_entry
    return None
```

### 6. **ConfigValidator - Saknade metoder**
**Problem:** `validate_key()` och `validate_configuration()` metoder saknas
```python
# Behöver läggas till i ConfigValidator:
def validate_key(self, key: str, value: Any) -> Dict[str, Any]:
    """Validera enskild nyckel."""
    key_def = self.key_registry.get_key(key)
    if not key_def:
        return {"valid": False, "error": f"Unknown key: {key}"}
    
    return {"valid": key_def.validate_value(value)}

def validate_configuration(self, config: Dict[str, Any]) -> Dict[str, Any]:
    """Validera hel konfiguration."""
    results = {}
    for key, value in config.items():
        results[key] = self.validate_key(key, value)
    return results
```

### 7. **Windows File Locking Problem**
**Problem:** SQLite filer låses av Windows och kan inte tas bort efter tester
```python
# Fixa i test teardown:
def teardown_method(self):
    # Stäng alla connections först
    if hasattr(self, 'store') and self.store:
        self.store.close()  # Lägg till close() metod
    
    # Vänta lite för att låsa ska släppas
    import time
    time.sleep(0.1)
    
    try:
        os.remove(self.db_path)
    except PermissionError:
        # Ignorera om filen fortfarande är låst
        pass
```

### 8. **Mock Redis Transaction Problem**
**Problem:** Mock Redis simulerar inte korrekt transaktionsrollback
```python
# Fixa i MockRedis klassen:
def transaction(self, func):
    """Simulera Redis transaktion."""
    # Spara nuvarande state
    backup = self.data.copy()
    
    try:
        result = func(self)
        # Om func returnerar None, det betyder rollback
        if result is None:
            self.data = backup
            return None
        return result
    except Exception:
        # Rollback vid exception
        self.data = backup
        raise
```

### 9. **Generation Consistency Problem**
**Problem:** Generation nummer ökar inte korrekt
```python
# Fixa i ConfigStore:
def _get_next_generation(self, conn, key: str) -> int:
    """Hämta nästa generation nummer för nyckel."""
    cursor = conn.execute(
        "SELECT MAX(generation) FROM config_values WHERE key = ?",
        (key,)
    )
    result = cursor.fetchone()
    return (result[0] or 0) + 1
```

### 10. **Sensitive Data Redaction Problem**
**Problem:** Känsliga data returneras tomma istället för maskerade
```python
# Fixa i UnifiedConfigManager:
def _redact_sensitive_data(self, key: str, value: Any, user: User = None) -> Any:
    """Maskera känsliga data baserat på användarroller."""
    if not self._is_sensitive(key):
        return value
    
    # Kontrollera om användaren har behörighet
    if user and self._has_sensitive_access(user):
        return value
    
    # Returnera maskerat värde
    key_def = self.key_registry.get_key(key)
    return key_def.get_masked_value(value) if key_def else "***"
```

## 🎯 **Prioritering för fixar:**

### **Hög prioritet (kritiska för funktionalitet):**
1. ConfigStore database schema fix
2. ConfigCache return type fix  
3. ConfigValidator saknade metoder
4. Generation consistency fix

### **Medel prioritet (viktiga för stabilitet):**
5. Windows file locking fix
6. Mock Redis transaction fix
7. Sensitive data redaction fix

### **Låg prioritet (nice-to-have):**
8. Cache stats metod
9. Store stats metod
10. Test parameter fixes

## 📝 **Nästa steg:**
1. Implementera saknade metoder i respektive klasser
2. Fixa database schema för history tabellen
3. Uppdatera testmockar för bättre simulation
4. Lägg till proper cleanup i test teardown
5. Kör testerna igen för att verifiera fixar

## ✅ **Förväntat resultat efter fixar:**
- **73/73 tester passerar** (100% framgångsgrad)
- **Robust testmiljö** för framtida utveckling
- **Kvalitetssäkrad kod** med full testcoverage
