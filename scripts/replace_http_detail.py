"""
AI Change: Mass-replace HTTPException(detail=str(e)) with generic message
(Agent: Codex, Date: 2025-09-18)
"""

from __future__ import annotations

import pathlib
import re


def main() -> int:
    target = pathlib.Path("tradingbot-backend/rest/routes.py")
    if not target.exists():
        return 0
    text = target.read_text(encoding="utf-8")
    # Replace any spacing variant of detail=str(e)
    pattern = re.compile(r"detail\s*=\s*str\(\s*e\s*\)")
    replaced = pattern.sub('detail="Internal server error"', text)
    if replaced != text:
        target.write_text(replaced, encoding="utf-8")
        print("changed")
        return 1
    print("nochange")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
