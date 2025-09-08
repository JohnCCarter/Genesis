"""
Tester för RiskGuardsService.
"""

import json
import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from services.risk_guards import RiskGuardsService


class TestRiskGuardsService:
    """Tester för RiskGuardsService."""

    def setup_method(self):
        """Setup för varje test."""
        # Skapa temporär fil för tester
        self.temp_dir = tempfile.mkdtemp()
        self.guards_file = os.path.join(self.temp_dir, "test_risk_guards.json")

        # Mock settings
        with patch("services.risk_guards.Settings") as mock_settings:
            mock_settings.return_value = type("Settings", (), {})()
            self.service = RiskGuardsService()
            self.service.guards_file = self.guards_file

    def teardown_method(self):
        """Cleanup efter varje test."""
        # Rensa temporär fil
        if os.path.exists(self.guards_file):
            os.remove(self.guards_file)
        if os.path.exists(self.temp_dir):
            os.rmdir(self.temp_dir)

    def test_load_guards_creates_defaults(self):
        """Test att default guards skapas när fil inte finns."""
        # Ta bort fil om den finns
        if os.path.exists(self.guards_file):
            os.remove(self.guards_file)

        # Ladda guards
        guards = self.service._load_guards()

        # Verifiera att default guards skapades
        assert "max_daily_loss" in guards
        assert "kill_switch" in guards
        assert "exposure_limits" in guards
        assert "volatility_guards" in guards

        # Verifiera default värden
        assert guards["max_daily_loss"]["enabled"] is True
        assert guards["max_daily_loss"]["percentage"] == 5.0
        assert guards["kill_switch"]["enabled"] is True
        assert guards["kill_switch"]["max_drawdown_percentage"] == 10.0

    def test_save_and_load_guards(self):
        """Test att guards kan sparas och laddas."""
        test_guards = {
            "max_daily_loss": {
                "enabled": True,
                "percentage": 3.0,
                "triggered": False,
                "triggered_at": None,
                "cooldown_hours": 12,
            },
            "kill_switch": {
                "enabled": False,
                "max_drawdown_percentage": 15.0,
                "triggered": False,
                "triggered_at": None,
                "cooldown_hours": 24,
            },
        }

        # Spara test guards
        self.service._save_guards(test_guards)

        # Verifiera att fil skapades
        assert os.path.exists(self.guards_file)

        # Ladda och verifiera
        loaded_guards = self.service._load_guards()
        assert loaded_guards["max_daily_loss"]["percentage"] == 3.0
        assert loaded_guards["kill_switch"]["enabled"] is False

    @patch("services.risk_guards.RiskGuardsService._get_current_equity")
    def test_check_max_daily_loss_not_triggered(self, mock_equity):
        """Test max daily loss när inte triggad."""
        mock_equity.return_value = 10000.0

        # Sätt start equity
        self.service.guards["max_daily_loss"]["daily_start_equity"] = 10000.0
        self.service.guards["max_daily_loss"]["enabled"] = True
        self.service.guards["max_daily_loss"]["percentage"] = 5.0

        # Test - ingen förlust
        blocked, reason = self.service.check_max_daily_loss()
        assert blocked is False
        assert reason is None

    @patch("services.risk_guards.RiskGuardsService._get_current_equity")
    def test_check_max_daily_loss_triggered(self, mock_equity):
        """Test max daily loss när triggad."""
        mock_equity.return_value = 9400.0  # 6% förlust

        # Sätt start equity
        self.service.guards["max_daily_loss"]["daily_start_equity"] = 10000.0
        self.service.guards["max_daily_loss"]["enabled"] = True
        self.service.guards["max_daily_loss"]["percentage"] = 5.0

        # Test - förlust över gränsen
        blocked, reason = self.service.check_max_daily_loss()
        assert blocked is True
        assert "Max daily loss överskriden" in reason
        assert self.service.guards["max_daily_loss"]["triggered"] is True

    @patch("services.risk_guards.RiskGuardsService._get_current_equity")
    def test_check_max_daily_loss_cooldown(self, mock_equity):
        """Test max daily loss cooldown."""
        mock_equity.return_value = 9400.0

        # Sätt triggad status med nyligen timestamp
        self.service.guards["max_daily_loss"]["triggered"] = True
        self.service.guards["max_daily_loss"]["triggered_at"] = datetime.now().isoformat()
        self.service.guards["max_daily_loss"]["cooldown_hours"] = 24

        # Test - cooldown aktiv
        blocked, reason = self.service.check_max_daily_loss()
        assert blocked is True
        assert "cooldown aktiv" in reason

    @patch("services.risk_guards.RiskGuardsService._get_current_equity")
    def test_check_kill_switch_triggered(self, mock_equity):
        """Test kill switch när triggad."""
        mock_equity.return_value = 8500.0  # 15% drawdown

        # Sätt start equity
        self.service.guards["max_daily_loss"]["daily_start_equity"] = 10000.0
        self.service.guards["kill_switch"]["enabled"] = True
        self.service.guards["kill_switch"]["max_drawdown_percentage"] = 10.0

        # Test - drawdown över gränsen
        blocked, reason = self.service.check_kill_switch()
        assert blocked is True
        assert "Max drawdown överskriden" in reason
        assert self.service.guards["kill_switch"]["triggered"] is True

    def test_check_exposure_limits(self):
        """Test exposure limits."""
        self.service.guards["exposure_limits"]["enabled"] = True
        self.service.guards["exposure_limits"]["max_position_size_percentage"] = 20.0

        with patch.object(self.service, "_get_current_equity", return_value=10000.0):
            # Test - position size inom gränsen
            blocked, reason = self.service.check_exposure_limits("tBTCUSD", 0.1, 50000)
            assert blocked is False

            # Test - position size över gränsen
            blocked, reason = self.service.check_exposure_limits("tBTCUSD", 1.0, 50000)
            assert blocked is True
            assert "Position size för stor" in reason

    def test_check_all_guards(self):
        """Test alla guards tillsammans."""
        with (
            patch.object(self.service, "check_max_daily_loss", return_value=(False, None)),
            patch.object(self.service, "check_kill_switch", return_value=(False, None)),
            patch.object(self.service, "check_exposure_limits", return_value=(False, None)),
        ):
            # Test - alla guards passerar
            blocked, reason = self.service.check_all_guards("tBTCUSD", 0.1, 50000)
            assert blocked is False
            assert reason is None

    def test_reset_guard(self):
        """Test återställning av guard."""
        # Sätt triggad status
        self.service.guards["max_daily_loss"]["triggered"] = True
        self.service.guards["max_daily_loss"]["triggered_at"] = datetime.now().isoformat()
        self.service.guards["max_daily_loss"]["reason"] = "Test reason"

        # Återställ
        success = self.service.reset_guard("max_daily_loss")
        assert success is True
        assert self.service.guards["max_daily_loss"]["triggered"] is False
        assert self.service.guards["max_daily_loss"]["triggered_at"] is None
        assert self.service.guards["max_daily_loss"]["reason"] is None

    def test_update_guard_config(self):
        """Test uppdatering av guard konfiguration."""
        # Uppdatera konfiguration
        new_config = {"percentage": 7.5, "cooldown_hours": 36}
        success = self.service.update_guard_config("max_daily_loss", new_config)

        assert success is True
        assert self.service.guards["max_daily_loss"]["percentage"] == 7.5
        assert self.service.guards["max_daily_loss"]["cooldown_hours"] == 36

    @patch("services.risk_guards.RiskGuardsService._get_current_equity")
    def test_get_guards_status(self, mock_equity):
        """Test hämtning av guards status."""
        mock_equity.return_value = 9500.0

        # Sätt start equity
        self.service.guards["max_daily_loss"]["daily_start_equity"] = 10000.0

        # Hämta status
        status = self.service.get_guards_status()

        assert "current_equity" in status
        assert "daily_loss_percentage" in status
        assert "drawdown_percentage" in status
        assert "guards" in status
        assert "last_updated" in status

        assert status["current_equity"] == 9500.0
        assert status["daily_loss_percentage"] == 5.0  # (10000-9500)/10000 * 100
        assert status["drawdown_percentage"] == 5.0


if __name__ == "__main__":
    pytest.main([__file__])
