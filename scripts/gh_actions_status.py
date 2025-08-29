from __future__ import annotations

import argparse
import io
import json
import os
import sys
import tempfile
import textwrap
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional


GITHUB_API = "https://api.github.com"


def load_token() -> Optional[str]:
    for key in ("GITHUB_TOKEN", "GH_TOKEN", "GITHUB_PAT"):
        val = os.environ.get(key)
        if val:
            return val.strip()
    env_path = Path(".env")
    if env_path.exists():
        try:
            for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    if k.strip() in {"GITHUB_TOKEN", "GH_TOKEN", "GITHUB_PAT"}:
                        return v.strip().strip('"').strip("'")
        except Exception:
            pass
    return None


def http_get(url: str, token: Optional[str], accept: Optional[str] = None) -> bytes:
    req = urllib.request.Request(url)
    if accept:
        req.add_header("Accept", accept)
    else:
        req.add_header("Accept", "application/vnd.github+json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="ignore")
        except Exception:
            body = str(e)
        raise SystemExit(f"HTTPError {e.code} for {url}: {body}")
    except urllib.error.URLError as e:
        raise SystemExit(f"URLError for {url}: {e}")


def http_get_json(url: str, token: Optional[str]) -> Dict[str, Any]:
    data = http_get(url, token, accept=None)
    return json.loads(data.decode("utf-8"))


def list_runs(
    owner: str, repo: str, branch: Optional[str], per_page: int, token: Optional[str]
) -> Dict[str, Any]:
    q = f"?per_page={per_page}"
    if branch:
        q += f"&branch={branch}"
    url = f"{GITHUB_API}/repos/{owner}/{repo}/actions/runs{q}"
    return http_get_json(url, token)


def list_jobs(owner: str, repo: str, run_id: int, token: Optional[str]) -> Dict[str, Any]:
    url = f"{GITHUB_API}/repos/{owner}/{repo}/actions/runs/{run_id}/jobs"
    return http_get_json(url, token)


def download_logs(owner: str, repo: str, run_id: int, out_dir: Path, token: Optional[str]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    url = f"{GITHUB_API}/repos/{owner}/{repo}/actions/runs/{run_id}/logs"
    # Accept */* to avoid 415 for binary stream
    blob = http_get(url, token, accept="*/*")
    zip_path = out_dir / f"run_{run_id}_logs.zip"
    zip_path.write_bytes(blob)
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        zf.extractall(out_dir)
    return zip_path


def download_job_logs(owner: str, repo: str, job_id: int, token: Optional[str]) -> List[str]:
    url = f"{GITHUB_API}/repos/{owner}/{repo}/actions/jobs/{job_id}/logs"
    blob = http_get(url, token, accept="*/*")
    out_lines: List[str] = []
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            # Concatenate tails of all .txt entries
            for name in zf.namelist():
                if not name.lower().endswith(".txt"):
                    continue
                data = zf.read(name).decode("utf-8", errors="ignore").splitlines()
                tail = data[-80:]
                out_lines.append(f"==== {name} (last {len(tail)} lines) ====")
                out_lines.extend(tail)
    except zipfile.BadZipFile:
        # Some endpoints may return plain text
        try:
            text = blob.decode("utf-8", errors="ignore")
            out_lines.extend(text.splitlines()[-200:])
        except Exception:
            pass
    return out_lines


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--owner", required=True)
    p.add_argument("--repo", required=True)
    p.add_argument("--branch", default=None)
    p.add_argument("--per-page", type=int, default=5)
    p.add_argument("--show-jobs", action="store_true")
    p.add_argument("--download-logs", action="store_true")
    p.add_argument("--logs-dir", default=".ci_logs")
    p.add_argument("--print-failed-job-logs", action="store_true")
    args = p.parse_args()

    token = load_token()

    runs = list_runs(args.owner, args.repo, args.branch, args.per_page, token)
    items: List[Dict[str, Any]] = runs.get("workflow_runs", [])

    if not items:
        print("No runs found.")
        return

    print(f"Latest {len(items)} runs for {args.owner}/{args.repo} (branch={args.branch or '-'}):")
    for i, r in enumerate(items, 1):
        print(
            f"{i}. id={r.get('id')} name={r.get('name')} status={r.get('status')} "
            f"conclusion={r.get('conclusion')} event={r.get('event')} url={r.get('html_url')}"
        )

    latest = items[0]
    run_id = int(latest.get("id"))
    failed_jobs: List[Dict[str, Any]] = []

    if args.show_jobs and run_id:
        print("\nJobs for latest run:")
        jobs = list_jobs(args.owner, args.repo, run_id, token)
        for j in jobs.get("jobs", []):
            name = j.get("name")
            status = j.get("status")
            concl = j.get("conclusion")
            print(
                f"- job={name} status={status} conclusion={concl} "
                f"started_at={j.get('started_at')} finished_at={j.get('completed_at')}"
            )
            if concl and concl != "success":
                failed_jobs.append(j)
            steps = j.get("steps") or []
            for s in steps:
                if s.get("conclusion") and s.get("conclusion") != "success":
                    print(
                        f"    step: {s.get('name')} status={s.get('status')} conclusion={s.get('conclusion')}"
                    )

    if args.download_logs and run_id:
        out_dir = Path(args.logs_dir)
        zip_path = download_logs(args.owner, args.repo, run_id, out_dir, token)
        print(f"\nLogs downloaded to: {zip_path}")
        print(f"Extracted to: {out_dir.resolve()}\n")
        candidates = list(out_dir.rglob("*.txt"))
        for c in candidates[:10]:
            print(f" - {c.relative_to(out_dir)}")

    if args.print_failed_job_logs and failed_jobs:
        print("\n=== Failed job logs (tails) ===")
        for j in failed_jobs:
            job_id = int(j.get("id"))
            name = j.get("name")
            print(f"\n--- {name} (job_id={job_id}) ---")
            lines = download_job_logs(args.owner, args.repo, job_id, token)
            for ln in lines:
                print(ln)


if __name__ == "__main__":
    main()
