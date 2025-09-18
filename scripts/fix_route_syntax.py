"""
# AI Change: Fix quoting and parentheses in REST error redactions
(Agent: Codex, Date: 2025-09-18)

Purpose: clean up accidental escaped quotes and extra parentheses produced by
previous automated replacements in routes/active_orders.
"""

from __future__ import annotations

import pathlib
import re


FILES = [
    pathlib.Path("tradingbot-backend/rest/routes.py"),
    pathlib.Path("tradingbot-backend/rest/active_orders.py"),
]


def fix_text(src: str) -> str:
    out = src
    # Unescape specific tokens that should be plain strings in code
    out = out.replace('\\"internal_error\\"', '"internal_error"')
    out = out.replace('\\"ws_not_authenticated\\"', '"ws_not_authenticated"')
    # Fix notification payload dicts accidentally closed
    out = out.replace('"error": "internal_error")},', '"error": "internal_error"},')
    # Fix double closing parenthesis in OrderResponse returns
    out = re.sub(r'(return\s+OrderResponse\([^\n]*\))\)', r'\1', out)
    # Fix specific ws update failed variant
    out = out.replace('error="internal_error" or "ws_update_failed")', 'error="ws_update_failed")')
    return out


def main() -> int:
    changed = False
    for path in FILES:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        fixed = fix_text(text)
        if fixed != text:
            path.write_text(fixed, encoding="utf-8")
            print(f"fixed: {path}")
            changed = True
        else:
            print(f"nochange: {path}")
    return 0 if changed else 0


if __name__ == "__main__":
    raise SystemExit(main())
