"""
Setup Test Environment för Unified Configuration System

Förbereder testmiljön med mock-data och konfiguration.
"""

import os
import json
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any


class TestEnvironmentSetup:
    """Setup för testmiljö."""

    def __init__(self):
        """Initiera test environment setup."""
        self.test_dir = None
        self.original_cwd = None
        self.test_config = {}

    def setup(self) -> str:
        """Sätt upp testmiljö."""
        print("🔧 Sätter upp testmiljö...")
        
        # Skapa temporär test-katalog
        self.test_dir = tempfile.mkdtemp(prefix="unified_config_test_")
        self.original_cwd = os.getcwd()
        
        # Ändra till test-katalog
        os.chdir(self.test_dir)
        
        # Skapa test-struktur
        self._create_test_structure()
        
        # Skapa test-konfiguration
        self._create_test_config()
        
        # Skapa test-data
        self._create_test_data()
        
        print(f"✅ Testmiljö satt upp i: {self.test_dir}")
        return self.test_dir

    def teardown(self):
        """Rensa upp testmiljö."""
        if self.test_dir and os.path.exists(self.test_dir):
            print("🧹 Rensar upp testmiljö...")
            
            # Återställ original working directory
            if self.original_cwd:
                os.chdir(self.original_cwd)
            
            # Ta bort test-katalog
            shutil.rmtree(self.test_dir)
            print("✅ Testmiljö rensad")

    def _create_test_structure(self):
        """Skapa test-katalogstruktur."""
        directories = [
            "config",
            "services", 
            "rest",
            "tests",
            "logs",
            "data"
        ]
        
        for directory in directories:
            os.makedirs(directory, exist_ok=True)

    def _create_test_config(self):
        """Skapa test-konfiguration."""
        # Trading rules
        trading_rules = {
            "timezone": "UTC",
            "windows": {
                "mon": [["00:00", "23:59"]],
                "tue": [["00:00", "23:59"]],
                "wed": [["00:00", "23:59"]],
                "thu": [["00:00", "23:59"]],
                "fri": [["00:00", "23:59"]],
                "sat": [["00:00", "23:59"]],
                "sun": [["00:00", "23:59"]]
            },
            "max_trades_per_day": 200,
            "trade_cooldown_seconds": 60,
            "paused": False,
            "max_trades_per_symbol_per_day": 0
        }
        
        with open("config/trading_rules.json", "w") as f:
            json.dump(trading_rules, f, indent=2)

        # Environment variables för tester
        test_env = {
            "DRY_RUN_ENABLED": "True",
            "MAX_TRADES_PER_DAY": "200",
            "MAX_TRADES_PER_SYMBOL_PER_DAY": "0",
            "TRADE_COOLDOWN_SECONDS": "60",
            "TRADING_PAUSED": "False",
            "PROB_MODEL_ENABLED": "False",
            "WS_CONNECT_ON_START": "False",
            "SCHEDULER_ENABLED": "False",
            "AUTH_REQUIRED": "False",
            "BITFINEX_API_KEY": "test_api_key",
            "BITFINEX_API_SECRET": "test_api_secret",
            "LOG_LEVEL": "DEBUG"
        }
        
        # Sätt environment variables
        for key, value in test_env.items():
            os.environ[key] = value

        self.test_config = test_env

    def _create_test_data(self):
        """Skapa test-data."""
        # Test trade counter
        trade_counter = {
            "day": "2024-01-01",
            "count": 5,
            "per_symbol": {
                "BTCUSD": 3,
                "ETHUSD": 2
            }
        }
        
        with open("data/trade_counter.json", "w") as f:
            json.dump(trade_counter, f, indent=2)

        # Test bracket state
        bracket_state = {
            "active_brackets": [],
            "last_cleanup": "2024-01-01T00:00:00Z"
        }
        
        with open("data/bracket_state.json", "w") as f:
            json.dump(bracket_state, f, indent=2)

        # Test log file
        with open("logs/test.log", "w") as f:
            f.write("Test log file\n")

    def get_test_config(self) -> Dict[str, Any]:
        """Hämta test-konfiguration."""
        return self.test_config.copy()

    def create_test_database(self, db_path: str = "test.db") -> str:
        """Skapa test-databas."""
        import sqlite3
        
        conn = sqlite3.connect(db_path)
        
        # Skapa tabeller
        conn.execute("""
            CREATE TABLE IF NOT EXISTS config_values (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                source TEXT NOT NULL,
                generation INTEGER NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                user TEXT
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS config_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                source TEXT NOT NULL,
                generation INTEGER NOT NULL,
                created_at REAL NOT NULL,
                user TEXT,
                action TEXT
            )
        """)
        
        conn.commit()
        conn.close()
        
        return os.path.abspath(db_path)

    def create_test_redis_config(self) -> Dict[str, Any]:
        """Skapa Redis test-konfiguration."""
        return {
            "host": "localhost",
            "port": 6379,
            "db": 15,  # Test database
            "decode_responses": True,
            "socket_timeout": 1.0,
            "socket_connect_timeout": 1.0,
            "retry_on_timeout": True,
            "max_connections": 10
        }


# Global test environment instance
_test_env = None


def setup_test_environment() -> str:
    """Sätt upp global testmiljö."""
    global _test_env
    if _test_env is None:
        _test_env = TestEnvironmentSetup()
    return _test_env.setup()


def teardown_test_environment():
    """Rensa upp global testmiljö."""
    global _test_env
    if _test_env:
        _test_env.teardown()
        _test_env = None


def get_test_environment() -> TestEnvironmentSetup:
    """Hämta global testmiljö."""
    global _test_env
    if _test_env is None:
        _test_env = TestEnvironmentSetup()
        _test_env.setup()
    return _test_env


# Pytest fixtures
import pytest


@pytest.fixture(scope="session")
def test_environment():
    """Pytest fixture för testmiljö."""
    env = setup_test_environment()
    yield env
    teardown_test_environment()


@pytest.fixture
def test_db():
    """Pytest fixture för test-databas."""
    env = get_test_environment()
    db_path = env.create_test_database()
    yield db_path
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def test_config():
    """Pytest fixture för test-konfiguration."""
    env = get_test_environment()
    return env.get_test_config()


@pytest.fixture
def test_redis_config():
    """Pytest fixture för Redis test-konfiguration."""
    env = get_test_environment()
    return env.create_test_redis_config()


if __name__ == "__main__":
    # Standalone test av setup
    env = TestEnvironmentSetup()
    try:
        test_dir = env.setup()
        print(f"Testmiljö skapad i: {test_dir}")
        print("Test-konfiguration:")
        for key, value in env.get_test_config().items():
            print(f"  {key} = {value}")
    finally:
        env.teardown()
