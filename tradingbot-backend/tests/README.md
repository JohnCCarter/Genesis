# Unified Configuration System - Test Suite

Omfattande testsuite för det enhetliga konfigurationssystemet med fokus på kluster-konsistens, API-säkerhet och edge cases.

## 📋 Översikt

Detta testsuite täcker:

- **Unit Tests**: Grundläggande funktionalitet för alla komponenter
- **Integration Tests**: API-endpoints och service-integration
- **Cluster Consistency Tests**: Redis pub/sub och distributed caching
- **Security Tests**: RBAC, input validation och känsliga data
- **Edge Cases**: Felhantering och edge cases
- **Performance Tests**: Concurrent access och cache performance

## 🚀 Snabbstart

### Installera Test Dependencies

```bash
# Installera test-dependencies
pip install -r tests/requirements-test.txt

# Eller installera specifika paket
pip install pytest pytest-asyncio pytest-mock pytest-cov
```

### Köra Alla Tester

```bash
# Kör alla tester med detaljerad output
python tests/test_runner.py

# Eller använd pytest direkt
pytest tests/ -v --tb=short
```

### Köra Specifika Test-grupper

```bash
# Endast unit tests
pytest tests/test_unified_config_system.py -v

# Endast API tests
pytest tests/test_config_api.py -v

# Endast Redis integration tests
pytest tests/test_redis_integration.py -v

# Endast säkerhetstests
pytest tests/ -k "security" -v
```

## 🏗️ Test-struktur

```
tests/
├── test_unified_config_system.py    # Core system tests
├── test_config_api.py               # API endpoint tests
├── test_redis_integration.py        # Redis & cluster tests
├── test_runner.py                   # Test runner & reporting
├── setup_test_environment.py        # Test environment setup
├── run_ci_tests.py                  # CI/CD pipeline
├── requirements-test.txt            # Test dependencies
├── pytest.ini                      # Pytest configuration
└── README.md                        # Denna fil
```

## 🧪 Test-kategorier

### 1. Unit Tests (`test_unified_config_system.py`)

**TestConfigStore**

- Grundläggande set/get funktionalitet
- Generation tracking
- Atomic batch updates
- Compare-and-set operationer
- History tracking

**TestConfigCache**

- Cache operations och invalidation
- TTL expiration
- Fallback till store
- Generation-baserad invalidation

**TestUnifiedConfigManager**

- Kontextuell prioritet
- Trading rules prioritetsordning
- Validering och error handling
- Effective config generation

**TestConfigValidator**

- Input validation
- Range checking
- Sensitive data validation
- Configuration validation

**TestRollbackService**

- Snapshot creation och management
- Rollback operations
- Staged rollout
- Emergency snapshots

### 2. API Tests (`test_config_api.py`)

**TestUnifiedConfigAPI**

- Lista konfigurationsnycklar
- Hämta/sätta värden
- Validera konfiguration
- RBAC-auktorisering
- Sensitive data redaction
- Audit logging
- Preview/apply workflow
- Batch operationer

**TestRollbackAPI**

- Snapshot management
- Rollback operations
- Staged rollout
- Emergency snapshots

**TestObservabilityAPI**

- Health checks
- Metrics collection
- Event tracking
- Effective config snapshots

### 3. Redis Integration Tests (`test_redis_integration.py`)

**TestRedisIntegration**

- Redis connection och pub/sub
- Pipeline operations
- Error handling

**TestClusterConsistency**

- Cross-node cache invalidation
- Generation consistency
- Concurrent updates
- Split-brain prevention
- Network partition handling

**TestAtomicOperations**

- Atomic batch updates
- Compare-and-set operations
- Transaction rollback

**TestCacheCoherency**

- Cache invalidation propagation
- Eventual consistency
- Cache warming

**TestRedisFailureHandling**

- Connection failure handling
- Timeout handling
- Retry mechanisms

## 🔧 Test Environment Setup

### Automatisk Setup

```python
from tests.setup_test_environment import setup_test_environment, teardown_test_environment

# Sätt upp testmiljö
test_dir = setup_test_environment()

# Kör dina tester här...

# Rensa upp
teardown_test_environment()
```

### Manuell Setup

```bash
# Skapa test-konfiguration
python tests/setup_test_environment.py

# Detta skapar:
# - config/trading_rules.json
# - data/trade_counter.json
# - data/bracket_state.json
# - logs/test.log
# - Environment variables för tester
```

## 📊 Test Rapporter

### Console Output

```bash
python tests/test_runner.py
```

Ger detaljerad console output med:

- Test sammanfattning
- Framgångsgrad
- Misslyckade tester
- Körningstider

### JSON Rapport

```json
{
  "total_tests": 150,
  "total_passed": 145,
  "total_failed": 5,
  "success_rate": 96.7,
  "duration_seconds": 45.2,
  "failed_files": ["test_config_api.py"],
  "all_passed": false
}
```

### HTML Rapport

Genereras automatiskt som `test_report.html` med:

- Visuell sammanfattning
- Detaljerade resultat per testfil
- Status-indikatorer
- Körningstider

## 🏃‍♂️ CI/CD Pipeline

### Kör CI Pipeline

```bash
# Fullständig pipeline
python tests/run_ci_tests.py --config full

# Snabb pipeline
python tests/run_ci_tests.py --config quick

# Säkerhetspipeline
python tests/run_ci_tests.py --config security
```

### CI Pipeline Steps

**Full Configuration:**

1. Setup Test Environment
2. Unit Tests
3. API Tests
4. Redis Integration Tests
5. Code Formatting (Black)
6. Linting (Ruff)
7. Type Checking (MyPy)
8. Security Scan (Bandit)

**Quick Configuration:**

1. Critical Unit Tests
2. Basic Integration Tests
3. Code Formatting

**Security Configuration:**

1. Security Scan
2. RBAC Tests
3. Sensitive Data Tests
4. Input Validation Tests

### CI Output

- **Console Report**: Detaljerad status per steg
- **JSON Report**: `ci_test_report.json`
- **JUnit XML**: `ci_test_report.xml` (för CI/CD system)

## 🎯 Test Markers

Använd pytest markers för att köra specifika test-grupper:

```bash
# Unit tests
pytest -m unit

# Integration tests
pytest -m integration

# API tests
pytest -m api

# Redis tests
pytest -m redis

# Cluster tests
pytest -m cluster

# Security tests
pytest -m security

# Slow tests
pytest -m "not slow"

# Tests som kräver Redis
pytest -m "not requires_redis"
```

## 🔍 Debugging Tests

### Verbose Output

```bash
pytest tests/ -v -s --tb=long
```

### Specific Test

```bash
pytest tests/test_unified_config_system.py::TestConfigStore::test_basic_set_get -v
```

### Debug Mode

```bash
pytest tests/ --pdb --tb=short
```

### Coverage Report

```bash
pytest tests/ --cov=services --cov=config --cov-report=html
```

## 🚨 Troubleshooting

### Vanliga Problem

**1. Import Errors**

```bash
# Lägg till projekt-root i PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

**2. Redis Connection Errors**

```bash
# Mock Redis används automatiskt i testerna
# Ingen riktig Redis-instans krävs
```

**3. Database Lock Errors**

```bash
# Tester använder temporära databaser
# Se till att inga andra processer använder samma filer
```

**4. Permission Errors**

```bash
# Se till att test-katalogen är skrivbar
chmod 755 tests/
```

### Test Environment Issues

```bash
# Rensa test environment
python tests/setup_test_environment.py

# Verifiera environment
python -c "from tests.setup_test_environment import get_test_environment; print(get_test_environment().get_test_config())"
```

## 📈 Performance Testing

### Concurrent Access Tests

```bash
# Test samtidig åtkomst
pytest tests/test_unified_config_system.py::TestEdgeCases::test_concurrent_cache_access -v
```

### Memory Usage

```bash
# Test minnesanvändning
pytest tests/ --memray --memray-bin-path=memray
```

### Benchmark Tests

```bash
# Performance benchmarks
pytest tests/ --benchmark-only --benchmark-sort=mean
```

## 🔒 Security Testing

### RBAC Tests

```bash
# Test behörigheter
pytest tests/test_config_api.py::TestAPISecurity -v
```

### Input Validation

```bash
# Test input validering
pytest tests/test_unified_config_system.py::TestConfigValidator -v
```

### Sensitive Data

```bash
# Test känsliga data
pytest tests/test_config_api.py::TestUnifiedConfigAPI::test_sensitive_data_redaction -v
```

## 📝 Contributing

### Lägga till Nya Tester

1. **Följ namngivningskonventioner:**

   - Testklasser: `TestComponentName`
   - Testmetoder: `test_functionality_description`

2. **Använd lämpliga markers:**

   ```python
   @pytest.mark.unit
   @pytest.mark.integration
   @pytest.mark.slow
   ```

3. **Mock externa dependencies:**

   ```python
   @patch('services.redis.Redis')
   def test_redis_integration(self, mock_redis):
       # Test kod här
   ```

4. **Dokumentera tester:**
   ```python
   def test_important_functionality(self):
       """Test att viktig funktionalitet fungerar korrekt."""
       # Test implementation
   ```

### Test Guidelines

- **En test per funktionalitet**
- **Förutsägbar test data**
- **Cleanup efter tester**
- **Mock externa services**
- **Dokumentera edge cases**
- **Test både happy path och error cases**

## 📚 Ytterligare Resurser

- [Pytest Documentation](https://docs.pytest.org/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [Redis Testing](https://redis.io/docs/manual/testing/)
- [Python Mock](https://docs.python.org/3/library/unittest.mock.html)

## 🤝 Support

För frågor eller problem med test-systemet:

1. Kontrollera denna README
2. Kör `python tests/setup_test_environment.py` för att verifiera setup
3. Använd `pytest --collect-only tests/` för att lista alla tester
4. Skapa issue med detaljerad beskrivning av problemet
