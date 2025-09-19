"""
Test Runner för Unified Configuration System

Kör alla tester och genererar rapporter.
"""

import pytest
import sys
import os
import json
import time
from pathlib import Path
from typing import Dict, List, Any

# Lägg till projekt-root i Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class TestRunner:
    """Test runner för unified configuration system."""

    def __init__(self):
        """Initiera test runner."""
        self.test_results = {}
        self.start_time = None
        self.end_time = None

    def run_all_tests(self) -> Dict[str, Any]:
        """Kör alla tester och returnera resultat."""
        print("🚀 Kör Unified Configuration System Tester...")
        self.start_time = time.time()

        # Definiera test-filer
        test_files = [
            "tests/test_unified_config_system.py",
            "tests/test_config_api.py", 
            "tests/test_redis_integration.py"
        ]

        # Kör tester
        results = []
        for test_file in test_files:
            if os.path.exists(test_file):
                print(f"📋 Kör {test_file}...")
                result = self._run_test_file(test_file)
                results.append(result)
            else:
                print(f"⚠️  Testfil {test_file} hittades inte")

        self.end_time = time.time()
        
        # Sammanställ resultat
        summary = self._generate_summary(results)
        
        # Generera rapporter
        self._generate_reports(summary)
        
        return summary

    def _run_test_file(self, test_file: str) -> Dict[str, Any]:
        """Kör enskild testfil."""
        try:
            # Kör pytest på filen
            result = pytest.main([
                test_file,
                "-v",
                "--tb=short"
            ])
            
            # Skapa enkel json result (eftersom pytest-json-report inte är installerat)
            json_result = {"summary": {"passed": 0 if result != 0 else 1, "failed": 1 if result != 0 else 0, "total": 1}}

            return {
                "file": test_file,
                "result": result,
                "json_result": json_result,
                "success": result == 0
            }
            
        except Exception as e:
            return {
                "file": test_file,
                "result": -1,
                "json_result": {"summary": {"passed": 0, "failed": 1, "total": 1}},
                "success": False,
                "error": str(e)
            }

    def _generate_summary(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generera sammanfattning av testresultat."""
        total_passed = 0
        total_failed = 0
        total_tests = 0
        failed_files = []

        for result in results:
            if "json_result" in result and "summary" in result["json_result"]:
                summary = result["json_result"]["summary"]
                total_passed += summary.get("passed", 0)
                total_failed += summary.get("failed", 0)
                total_tests += summary.get("total", 0)
                
                if not result["success"]:
                    failed_files.append(result["file"])

        duration = self.end_time - self.start_time if self.end_time and self.start_time else 0

        return {
            "total_tests": total_tests,
            "total_passed": total_passed,
            "total_failed": total_failed,
            "success_rate": (total_passed / total_tests * 100) if total_tests > 0 else 0,
            "duration_seconds": duration,
            "failed_files": failed_files,
            "all_passed": total_failed == 0,
            "test_results": results
        }

    def _generate_reports(self, summary: Dict[str, Any]):
        """Generera testrapporter."""
        # Console report
        self._print_console_report(summary)
        
        # JSON report
        self._save_json_report(summary)
        
        # HTML report (enkel)
        self._save_html_report(summary)

    def _print_console_report(self, summary: Dict[str, Any]):
        """Skriv console rapport."""
        print("\n" + "="*60)
        print("📊 UNIFIED CONFIGURATION SYSTEM - TEST RESULTAT")
        print("="*60)
        
        # Sammanfattning
        print(f"📈 Totalt antal tester: {summary['total_tests']}")
        print(f"✅ Godkända: {summary['total_passed']}")
        print(f"❌ Misslyckade: {summary['total_failed']}")
        print(f"📊 Framgångsgrad: {summary['success_rate']:.1f}%")
        print(f"⏱️  Tid: {summary['duration_seconds']:.2f} sekunder")
        
        # Status
        if summary['all_passed']:
            print("\n🎉 ALLA TESTER GODKÄNDA!")
        else:
            print(f"\n⚠️  {summary['total_failed']} TESTER MISSLYCKADES")
            if summary['failed_files']:
                print("📁 Misslyckade testfiler:")
                for file in summary['failed_files']:
                    print(f"   - {file}")
        
        print("="*60)

    def _save_json_report(self, summary: Dict[str, Any]):
        """Spara JSON rapport."""
        report_path = "test_report.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"📄 JSON rapport sparad: {report_path}")

    def _save_html_report(self, summary: Dict[str, Any]):
        """Spara HTML rapport."""
        html_content = self._generate_html_report(summary)
        report_path = "test_report.html"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"🌐 HTML rapport sparad: {report_path}")

    def _generate_html_report(self, summary: Dict[str, Any]) -> str:
        """Generera HTML rapport."""
        status_color = "#4CAF50" if summary['all_passed'] else "#F44336"
        status_icon = "🎉" if summary['all_passed'] else "⚠️"
        
        html = f"""
<!DOCTYPE html>
<html lang="sv">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Unified Configuration System - Test Rapport</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, {status_color}, #2196F3);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 2.5em;
            font-weight: 300;
        }}
        .header .subtitle {{
            margin-top: 10px;
            opacity: 0.9;
            font-size: 1.2em;
        }}
        .summary {{
            padding: 30px;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
        }}
        .stat-card {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            border-left: 4px solid {status_color};
        }}
        .stat-card h3 {{
            margin: 0 0 10px 0;
            color: #333;
            font-size: 1.1em;
        }}
        .stat-card .number {{
            font-size: 2.5em;
            font-weight: bold;
            color: {status_color};
        }}
        .details {{
            padding: 30px;
            border-top: 1px solid #eee;
        }}
        .test-file {{
            margin-bottom: 20px;
            padding: 15px;
            border-radius: 6px;
            border-left: 4px solid #ddd;
        }}
        .test-file.passed {{
            background: #f0f9ff;
            border-left-color: #4CAF50;
        }}
        .test-file.failed {{
            background: #fff5f5;
            border-left-color: #F44336;
        }}
        .test-file h4 {{
            margin: 0 0 10px 0;
            font-family: 'Courier New', monospace;
        }}
        .timestamp {{
            text-align: center;
            padding: 20px;
            color: #666;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{status_icon} Test Rapport</h1>
            <div class="subtitle">Unified Configuration System</div>
        </div>
        
        <div class="summary">
            <div class="stat-card">
                <h3>Totalt antal tester</h3>
                <div class="number">{summary['total_tests']}</div>
            </div>
            <div class="stat-card">
                <h3>Godkända</h3>
                <div class="number">{summary['total_passed']}</div>
            </div>
            <div class="stat-card">
                <h3>Misslyckade</h3>
                <div class="number">{summary['total_failed']}</div>
            </div>
            <div class="stat-card">
                <h3>Framgångsgrad</h3>
                <div class="number">{summary['success_rate']:.1f}%</div>
            </div>
            <div class="stat-card">
                <h3>Körtid</h3>
                <div class="number">{summary['duration_seconds']:.1f}s</div>
            </div>
        </div>
        
        <div class="details">
            <h2>Detaljerade resultat</h2>
"""
        
        # Lägg till testfiler
        for result in summary['test_results']:
            status_class = "passed" if result['success'] else "failed"
            status_text = "✅ Godkänd" if result['success'] else "❌ Misslyckad"
            
            html += f"""
            <div class="test-file {status_class}">
                <h4>{result['file']}</h4>
                <p><strong>Status:</strong> {status_text}</p>
"""
            
            if 'json_result' in result and 'summary' in result['json_result']:
                test_summary = result['json_result']['summary']
                html += f"""
                <p><strong>Tester:</strong> {test_summary.get('total', 0)} | 
                   <strong>Godkända:</strong> {test_summary.get('passed', 0)} | 
                   <strong>Misslyckade:</strong> {test_summary.get('failed', 0)}</p>
"""
            
            if 'error' in result:
                html += f"<p><strong>Fel:</strong> {result['error']}</p>"
            
            html += "</div>"
        
        html += """
        </div>
        
        <div class="timestamp">
            Genererad: """ + time.strftime("%Y-%m-%d %H:%M:%S") + """
        </div>
    </div>
</body>
</html>
"""
        
        return html


def main():
    """Huvudfunktion för test runner."""
    runner = TestRunner()
    results = runner.run_all_tests()
    
    # Exit code baserat på resultat
    exit_code = 0 if results['all_passed'] else 1
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
