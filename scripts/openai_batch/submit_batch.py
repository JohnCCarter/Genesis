import argparse
import os
from pathlib import Path

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
    return parser.parse_args()


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

    client = OpenAI()

    # 1) Upload the JSONL as a file with purpose=batch
    with input_path.open("rb") as f:
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
        {
            "batch_id": batch.id,
            "status": batch.status,
            "input_file_id": uploaded.id,
            "endpoint": args.endpoint,
            "window": args.window,
        }
    )


if __name__ == "__main__":
    main()
