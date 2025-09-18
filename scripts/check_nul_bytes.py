# AI Change: Pre-commit check for NUL bytes in text files (Agent: Codex, Date: 2025-09-18)
from __future__ import annotations

import sys
from pathlib import Path


TEXT_SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".json",
    ".md",
    ".toml",
    ".ini",
    ".yml",
    ".yaml",
    ".txt",
    ".ps1",
    ".psm1",
    ".psd1",
    ".sh",
    ".bat",
    ".cfg",
    ".sql",
    ".html",
    ".css",
    ".scss",
    ".tsv",
    ".csv",
    ".mdx",
    ".graphql",
    ".gql",
    ".proto",
    ".conf",
    ".properties",
}


def has_nul_bytes(path: Path) -> bool:
    try:
        data = path.read_bytes()
    except Exception:
        return False
    return b"\x00" in data


def main(argv: list[str]) -> int:
    if not argv:
        # Fallback: scan repo root
        candidates = [
            p
            for p in Path(".").rglob("*")
            if p.is_file() and (p.suffix.lower() in TEXT_SUFFIXES or p.name in {".gitattributes", ".editorconfig", "README.md"})
        ]
    else:
        candidates = [Path(a) for a in argv]

    bad: list[Path] = []
    for p in candidates:
        if has_nul_bytes(p):
            bad.append(p)

    if bad:
        sys.stderr.write("NUL bytes detected in files (block commit):\n")
        for p in bad:
            sys.stderr.write(f" - {p}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
