"""
CI/CD Test Pipeline för Unified Configuration System

Kör alla tester med olika konfigurationer och genererar rapporter.
"""

import os
import sys
import json
import time
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional
import argparse


class CITestPipeline:
    """CI/CD test pipeline."""

    def __init__(self):
        """Initiera CI pipeline."""
        self.project_root = Path(__file__).parent.parent
        self.results = {}
        self.start_time = None

    def run_pipeline(self, config: str = "full") -> Dict[str, Any]:
        """Kör hela test pipeline."""
        print("🚀 Startar CI/CD Test Pipeline...")
        self.start_time = time.time()

        # Ändra till projekt-root
        os.chdir(self.project_root)

        # Definiera test-steg baserat på konfiguration
        if config == "quick":
            steps = self._get_quick_test_steps()
        elif config == "full":
            steps = self._get_full_test_steps()
        elif config == "security":
            steps = self._get_security_test_steps()
        else:
            raise ValueError(f"Okänd konfiguration: {config}")

        # Kör test-steg
        for step in steps:
            print(f"\n📋 Kör steg: {step['name']}")
            result = self._run_step(step)
            self.results[step['name']] = result

            if not result['success'] and step.get('critical', False):
                print(f"❌ Kritiskt steg misslyckades: {step['name']}")
                break

        # Generera sammanfattning
        summary = self._generate_summary()

        # Spara rapporter
        self._save_reports(summary)

        return summary

    def _get_quick_test_steps(self) -> List[Dict[str, Any]]:
        """Hämta snabba test-steg."""
        return [
            {
                "name": "Unit Tests",
                "command": ["python", "-m", "pytest", "tests/test_unified_config_system.py::TestConfigStore", "-v"],
                "critical": True,
            },
            {
                "name": "Basic Integration",
                "command": [
                    "python",
                    "-m",
                    "pytest",
                    "tests/test_unified_config_system.py::TestUnifiedConfigManager",
                    "-v",
                ],
                "critical": True,
            },
            {
                "name": "Code Formatting",
                "command": ["python", "-m", "black", "--check", "services/", "config/"],
                "critical": False,
            },
        ]

    def _get_full_test_steps(self) -> List[Dict[str, Any]]:
        """Hämta fullständiga test-steg."""
        return [
            {
                "name": "Setup Test Environment",
                "command": ["python", "tests/setup_test_environment.py"],
                "critical": True,
            },
            {
                "name": "Unit Tests",
                "command": ["python", "-m", "pytest", "tests/test_unified_config_system.py", "-v", "--tb=short"],
                "critical": True,
            },
            {
                "name": "API Tests",
                "command": ["python", "-m", "pytest", "tests/test_config_api.py", "-v", "--tb=short"],
                "critical": True,
            },
            {
                "name": "Redis Integration Tests",
                "command": ["python", "-m", "pytest", "tests/test_redis_integration.py", "-v", "--tb=short"],
                "critical": False,
            },
            {
                "name": "Code Formatting",
                "command": ["python", "-m", "black", "--check", "services/", "config/", "tests/"],
                "critical": False,
            },
            {
                "name": "Linting",
                "command": ["python", "-m", "ruff", "check", "services/", "config/", "tests/"],
                "critical": False,
            },
            {"name": "Type Checking", "command": ["python", "-m", "mypy", "services/", "config/"], "critical": False},
            {
                "name": "Security Scan",
                "command": ["python", "-m", "bandit", "-r", "services/", "config/"],
                "critical": False,
            },
        ]

    def _get_security_test_steps(self) -> List[Dict[str, Any]]:
        """Hämta säkerhetstest-steg."""
        return [
            {
                "name": "Security Scan",
                "command": ["python", "-m", "bandit", "-r", "services/", "config/", "-f", "json"],
                "critical": True,
            },
            {
                "name": "RBAC Tests",
                "command": ["python", "-m", "pytest", "tests/test_config_api.py::TestAPISecurity", "-v"],
                "critical": True,
            },
            {
                "name": "Sensitive Data Tests",
                "command": ["python", "-m", "pytest", "tests/test_unified_config_system.py::TestEdgeCases", "-v"],
                "critical": True,
            },
            {
                "name": "Input Validation Tests",
                "command": ["python", "-m", "pytest", "tests/test_unified_config_system.py::TestConfigValidator", "-v"],
                "critical": True,
            },
        ]

    def _run_step(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """Kör enskilt test-steg."""
        start_time = time.time()

        try:
            # Kör kommando
            result = subprocess.run(step["command"], capture_output=True, text=True, timeout=300)  # 5 minuter timeout

            duration = time.time() - start_time
            success = result.returncode == 0

            return {
                "success": success,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "duration": duration,
                "command": " ".join(step["command"]),
            }

        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            return {
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": f"Timeout efter {duration:.1f} sekunder",
                "duration": duration,
                "command": " ".join(step["command"]),
            }
        except Exception as e:
            duration = time.time() - start_time
            return {
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
                "duration": duration,
                "command": " ".join(step["command"]),
            }

    def _generate_summary(self) -> Dict[str, Any]:
        """Generera sammanfattning av pipeline-resultat."""
        total_steps = len(self.results)
        successful_steps = sum(1 for result in self.results.values() if result["success"])
        failed_steps = total_steps - successful_steps

        total_duration = time.time() - self.start_time if self.start_time else 0

        # Identifiera kritiska fel
        critical_failures = []
        for step_name, result in self.results.items():
            if not result["success"]:
                critical_failures.append(step_name)

        return {
            "total_steps": total_steps,
            "successful_steps": successful_steps,
            "failed_steps": failed_steps,
            "success_rate": (successful_steps / total_steps * 100) if total_steps > 0 else 0,
            "total_duration": total_duration,
            "critical_failures": critical_failures,
            "all_critical_passed": len(critical_failures) == 0,
            "step_results": self.results,
        }

    def _save_reports(self, summary: Dict[str, Any]):
        """Spara CI-rapporter."""
        # Console report
        self._print_console_report(summary)

        # JSON report
        self._save_json_report(summary)

        # JUnit XML (för CI/CD system)
        self._save_junit_xml(summary)

    def _print_console_report(self, summary: Dict[str, Any]):
        """Skriv console rapport."""
        print("\n" + "=" * 70)
        print("🏗️  CI/CD TEST PIPELINE - RESULTAT")
        print("=" * 70)

        print(f"📊 Totalt antal steg: {summary['total_steps']}")
        print(f"✅ Lyckade steg: {summary['successful_steps']}")
        print(f"❌ Misslyckade steg: {summary['failed_steps']}")
        print(f"📈 Framgångsgrad: {summary['success_rate']:.1f}%")
        print(f"⏱️  Total tid: {summary['total_duration']:.1f} sekunder")

        # Status
        if summary['all_critical_passed']:
            print("\n🎉 ALLA KRITISKA TESTER GODKÄNDA!")
        else:
            print(f"\n⚠️  {len(summary['critical_failures'])} KRITISKA TESTER MISSLYCKADES")
            for failure in summary['critical_failures']:
                print(f"   - {failure}")

        # Detaljerade resultat
        print("\n📋 Detaljerade resultat:")
        for step_name, result in summary['step_results'].items():
            status = "✅" if result['success'] else "❌"
            duration = result['duration']
            print(f"   {status} {step_name} ({duration:.1f}s)")

            if not result['success'] and result['stderr']:
                print(f"      Fel: {result['stderr'][:100]}...")

        print("=" * 70)

    def _save_json_report(self, summary: Dict[str, Any]):
        """Spara JSON rapport."""
        report_path = "ci_test_report.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"📄 CI JSON rapport sparad: {report_path}")

    def _save_junit_xml(self, summary: Dict[str, Any]):
        """Spara JUnit XML rapport."""
        xml_content = self._generate_junit_xml(summary)
        report_path = "ci_test_report.xml"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(xml_content)
        print(f"📄 CI JUnit XML rapport sparad: {report_path}")

    def _generate_junit_xml(self, summary: Dict[str, Any]) -> str:
        """Generera JUnit XML rapport."""
        total_tests = summary['total_steps']
        failures = summary['failed_steps']
        time_str = f"{summary['total_duration']:.3f}"

        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="Unified Configuration System CI Tests" 
           tests="{total_tests}" 
           failures="{failures}" 
           time="{time_str}">
"""

        for step_name, result in summary['step_results'].items():
            test_name = step_name.replace(" ", "_").lower()
            duration = f"{result['duration']:.3f}"

            if result['success']:
                xml += f"""    <testcase name="{test_name}" time="{duration}"/>
"""
            else:
                xml += f"""    <testcase name="{test_name}" time="{duration}">
        <failure message="Step failed">
            <![CDATA[
Command: {result['command']}
Return code: {result['returncode']}
Stderr: {result['stderr']}
            ]]>
        </failure>
    </testcase>
"""

        xml += "</testsuite>"
        return xml


def main():
    """Huvudfunktion för CI pipeline."""
    parser = argparse.ArgumentParser(description="CI/CD Test Pipeline")
    parser.add_argument(
        "--config", choices=["quick", "full", "security"], default="full", help="Test-konfiguration att köra"
    )
    parser.add_argument("--output", type=str, help="Output-katalog för rapporter")

    args = parser.parse_args()

    # Sätt output-katalog
    if args.output:
        os.chdir(args.output)

    # Kör pipeline
    pipeline = CITestPipeline()
    results = pipeline.run_pipeline(args.config)

    # Exit code baserat på resultat
    exit_code = 0 if results['all_critical_passed'] else 1
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
