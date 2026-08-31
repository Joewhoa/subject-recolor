from __future__ import annotations

import os
import platform
import sys
from pathlib import Path

import httpx
import PIL

from .planner import discover_jobs


def run_doctor(workspace: Path, base_url: str, api_key_env: str) -> tuple[list[str], bool]:
    lines = [
        f"[OK] Python {platform.python_version()}",
        f"[OK] Pillow {PIL.__version__}",
        f"[OK] httpx {httpx.__version__}",
    ]
    ok = sys.version_info >= (3, 11)
    if not ok:
        lines.append("[ERROR] Python 3.11 or newer is required")
    if base_url:
        lines.append("[OK] IMAGE_API_BASE_URL is configured")
        if base_url.startswith("http://"):
            lines.append("[WARN] Gateway uses plain HTTP; images and credentials are not encrypted")
    else:
        lines.append("[WARN] IMAGE_API_BASE_URL is not configured (plan/demo still work)")
    if os.getenv(api_key_env):
        lines.append(f"[OK] {api_key_env} is configured")
    else:
        lines.append(f"[WARN] {api_key_env} is not configured (paid runs are unavailable)")
    jobs = discover_jobs(workspace)
    job_status = (
        f"[OK] {len(jobs)} valid job(s) found in {workspace}"
        if jobs
        else f"[WARN] No jobs found in {workspace}"
    )
    lines.append(job_status)
    return lines, ok
