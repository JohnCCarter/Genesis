#!/usr/bin/env python3
"""
Setup script för att konfigurera trading bot config-filer från templates.
Kör detta script på ny installation för att skapa dina config-filer.
"""

from pathlib import Path
import shutil


def setup_config_files() -> None:
    """Skapa config-filer från templates om de inte finns"""

    config_dir = Path("tradingbot-backend/config")

    # Lista av config-filer och deras templates
    config_files = ["strategy_settings.json", "trading_rules.json", "performance_history.json"]

    print("🔧 Konfigurerar trading bot config-filer...")

    for config_file in config_files:
        template_file = f"{config_file}.template"
        config_path = config_dir / config_file
        template_path = config_dir / template_file

        if not config_path.exists() and template_path.exists():
            # Kopiera template till config
            shutil.copy2(template_path, config_path)
            print(f"✅ Skapade {config_file} från template")
        elif config_path.exists():
            print(f"ℹ️ {config_file} finns redan")
        else:
            print(f"⚠️ Template {template_file} saknas")

    print("\n🎯 Konfiguration klar!")
    print("\n📝 Nästa steg:")
    print("1. Redigera trading_rules.json för dina trading-tider")
    print("2. Sätt paused: false när du är redo att handla")
    print("3. Justera strategy_settings.json efter behov")
    print("4. Starta servern med: uvicorn main:app --reload")


if __name__ == "__main__":
    setup_config_files()
