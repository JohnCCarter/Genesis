import argparse
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


TERMINAL_STATES = {"completed", "failed", "cancelled", "expired"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Poll an OpenAI Batch job and download results")
    parser.add_argument("--batch-id", required=True, help="The batch id (bat_...) to poll")
    parser.add_argument("--out", default="results", help="Output directory for results")
    parser.add_argument("--interval", type=float, default=5.0, help="Polling interval in seconds")
    parser.add_argument(
        "--max-wait", type=int, default=3600, help="Max seconds to wait before exiting"
    )
    return parser.parse_args()


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> None:
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is not set. Put it in .env or export it before running.")

    args = parse_args()
    client = OpenAI()

    start = time.time()
    backoff = args.interval
    while True:
        batch = client.batches.retrieve(args.batch_id)
        print(json.dumps({"id": batch.id, "status": batch.status}, ensure_ascii=False))

        if batch.status in TERMINAL_STATES:
            break

        if (time.time() - start) > args.max_wait:
            raise SystemExit("Max wait time exceeded")

        time.sleep(backoff)
        backoff = min(backoff * 1.5, 60)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if getattr(batch, "output_file_id", None):
        resp = client.files.content(batch.output_file_id)
        content = getattr(resp, "text", None)
        if content is None:
            # Fallback if the SDK returns bytes-like
            try:
                content = resp.read().decode("utf-8")  # type: ignore[attr-defined]
            except Exception:
                content = str(resp)
        write_text(out_dir / f"{batch.id}_output.jsonl", content)
        print(f"Saved output to {out_dir / f'{batch.id}_output.jsonl'}")

    if getattr(batch, "error_file_id", None):
        eresp = client.files.content(batch.error_file_id)
        econtent = getattr(eresp, "text", None)
        if econtent is None:
            try:
                econtent = eresp.read().decode("utf-8")  # type: ignore[attr-defined]
            except Exception:
                econtent = str(eresp)
        write_text(out_dir / f"{batch.id}_errors.jsonl", econtent)
        print(f"Saved errors to {out_dir / f'{batch.id}_errors.jsonl'}")

    if batch.status != "completed":
        raise SystemExit(f"Batch finished with status: {batch.status}")


if __name__ == "__main__":
    main()
