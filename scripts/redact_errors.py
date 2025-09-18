"""
# AI Change: Redact error exposures in REST responses (Agent: Codex, Date: 2025-09-18)

Replaces patterns like "error": str(e) and error=str(e) with generic values
to eliminate stack-trace/exception detail exposure flagged by CodeQL.
"""

from __future__ import annotations

import pathlib
import re


TARGETS = [
    pathlib.Path("tradingbot-backend/rest/routes.py"),
    pathlib.Path("tradingbot-backend/rest/active_orders.py"),
]


def redact_text(src: str) -> str:
    # JSON dict form: "error": str(...)
    out = re.sub(r'("error"\s*:\s*)str\([^)]*\)', r'\1"internal_error"', src)
    # Kwarg form: error=str(...)
    out = re.sub(r'(error\s*=\s*)str\([^)]*\)', r'\1"internal_error"', out)
    # Cleanup accidental escaped quotes introduced by earlier runs
    out = out.replace('\\"internal_error\\"', '"internal_error"')
    out = out.replace('\\"ws_not_authenticated\\"', '"ws_not_authenticated"')
    # Fix accidental extra parenthesis patterns
    out = re.sub(r'error=\"internal_error\"\s*or\s*\"ws_update_failed\"\)', 'error=\"ws_update_failed\")', out)
    out = re.sub(r'error=\"internal_error\"\)\)', 'error=\"internal_error\")', out)
    out = out.replace('"internal_error")},', '"internal_error"},')
    out = re.sub(r'("error"\s*:\s*"internal_error")\)\}', r'\1}', out)
    return out


def main() -> int:
    changed_any = False
    for path in TARGETS:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        redacted = redact_text(text)
        if redacted != text:
            path.write_text(redacted, encoding="utf-8")
            print(f"redacted: {path}")
            changed_any = True
        else:
            print(f"nochange: {path}")
    return 0 if changed_any else 0


if __name__ == "__main__":
    raise SystemExit(main())
