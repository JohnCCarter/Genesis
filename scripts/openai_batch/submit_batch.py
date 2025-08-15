import argparse
import json
import os
from pathlib import Path
import tempfile
import time

from dotenv import load_dotenv
from openai import OpenAI


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Submit an OpenAI Batch job")
    parser.add_argument(
        "--input",
        default=os.getenv("OPENAI_BATCH_INPUT_FILE", "batch_examples.jsonl"),
        help="Path to JSONL input file",
    )
    parser.add_argument(
        "--endpoint",
        default=os.getenv("OPENAI_BATCH_ENDPOINT", "/v1/chat/completions"),
        help="Target endpoint, e.g. /v1/chat/completions",
    )
    parser.add_argument(
        "--window",
        default=os.getenv("OPENAI_BATCH_COMPLETION_WINDOW", "24h"),
        help="Completion window, e.g. 24h",
    )
    parser.add_argument("--desc", default="", help="Optional description/metadata for this batch")
    parser.add_argument(
        "--override-model",
        default=os.getenv("OPENAI_BATCH_MODEL"),
        help="If set, overrides body.model for each JSONL line before upload",
    )
    return parser.parse_args()


def _rewrite_jsonl_with_model(source: Path, model: str) -> Path:
    """Create a temp JSONL with body.model overridden on each line."""
    tmp = Path(tempfile.mkstemp(suffix=".jsonl")[1])
    with source.open("r", encoding="utf-8") as fin, tmp.open("w", encoding="utf-8") as fout:
        for line in fin:
            if not line.strip():
                continue
            obj = json.loads(line)
            body = obj.get("body")
            if isinstance(body, dict):
                body["model"] = model
            else:
                # Fallback if someone put model at root (non-standard)
                obj["model"] = model
            fout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    return tmp


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)  # type: ignore[call-arg]
        return
    except PermissionError:
        time.sleep(0.5)
        try:
            path.unlink(missing_ok=True)  # type: ignore[call-arg]
        except PermissionError:
            return
    except TypeError:
        # Python <3.8 compatibility
        if path.exists():
            try:
                path.unlink()
                return
            except PermissionError:
                time.sleep(0.5)
                try:
                    path.unlink()
                except PermissionError:
                    return


def main() -> None:
    # Load .env if present
    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is not set. Put it in .env or export it before running.")

    args = parse_args()
    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")

    upload_path = input_path
    temp_created = False
    if args.override_model:
        upload_path = _rewrite_jsonl_with_model(input_path, args.override_model)
        temp_created = True

    client = OpenAI()

    # 1) Upload the JSONL as a file with purpose=batch
    with upload_path.open("rb") as f:
        uploaded = client.files.create(file=f, purpose="batch")

    # 2) Create the batch
    metadata = {"description": args.desc} if args.desc else None
    batch = client.batches.create(
        input_file_id=uploaded.id,
        endpoint=args.endpoint,
        completion_window=args.window,
        metadata=metadata,
    )

    print(
        json.dumps(
            {
                "batch_id": batch.id,
                "status": batch.status,
                "input_file_id": uploaded.id,
                "endpoint": args.endpoint,
                "window": args.window,
            },
            ensure_ascii=False,
        )
    )

    if temp_created:
        _safe_unlink(upload_path)


if __name__ == "__main__":
    main()
