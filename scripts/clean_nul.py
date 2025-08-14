from pathlib import Path
import sys


def clean_file(path: Path) -> None:
    data = path.read_bytes()
    # Remove NUL bytes
    cleaned = data.replace(b"\x00", b"")
    if cleaned != data:
        path.write_bytes(cleaned)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/clean_nul.py <file> [<file> ...]")
        sys.exit(1)
    for arg in sys.argv[1:]:
        p = Path(arg)
        if p.exists():
            clean_file(p)
            print(f"Cleaned: {p}")
        else:
            print(f"Not found: {p}")


if __name__ == "__main__":
    main()
