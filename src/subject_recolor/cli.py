from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .config import create_job, load_job_config
from .demo import OfflineDemoGateway, create_demo_job
from .doctor import run_doctor
from .evaluate import evaluate_tasks
from .gateway import OpenAICompatibleGateway
from .pipeline import execute_tasks, summarize_plan
from .planner import build_tasks, resolve_job
from .review import build_review
from .utils import atomic_write_json

ACTIONS = ["init", "plan", "run", "review", "evaluate", "doctor", "demo"]


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(
        prog="subject-recolor",
        description="Plan and execute safe recoloring jobs for a user-selected subject.",
    )
    command.add_argument("action", nargs="?", choices=ACTIONS, default="plan")
    command.add_argument("--workspace", type=Path, default=Path("workspace"))
    choice = command.add_mutually_exclusive_group()
    choice.add_argument("--date", help="Job directory: MMDD, YYYYMMDD, or YYYY-MM-DD")
    choice.add_argument("--latest", action="store_true")
    command.add_argument("--subject", help="Override subject from job.toml")
    command.add_argument("--model", help="Override model from job.toml")
    command.add_argument("--cards", default="", help="Comma-separated color-card stems")
    command.add_argument("--inputs", default="", help="Comma-separated input stems")
    command.add_argument("--limit", type=int, default=0)
    command.add_argument("--yes", action="store_true", help="Skip the interactive paid-run prompt")
    command.add_argument("--expect-calls", type=int, help="Abort if current new_calls differs")
    command.add_argument(
        "--max-paid-calls",
        type=int,
        help="Hard upper bound for new paid calls; independent of --expect-calls",
    )
    command.add_argument("--json", action="store_true", help="Emit a machine-readable plan")
    command.add_argument("--base-url", default=os.getenv("IMAGE_API_BASE_URL", ""))
    command.add_argument("--api-key-env", default="IMAGE_API_KEY")
    command.add_argument("--timeout", type=float, default=240)
    return command


def _selection(value: str) -> set[str] | None:
    return {item.strip() for item in value.split(",") if item.strip()} or None


def _confirm(summary: dict[str, int], job: Path, subject: str, model: str) -> bool:
    print("\nPaid image-edit confirmation")
    print(f"Job: {job.name}\nSubject: {subject}\nModel: {model}")
    print(f"Total tasks: {summary['tasks']}\nCompleted: {summary['complete']}")
    print(f"New paid API calls: {summary['new_calls']}")
    if not sys.stdin.isatty():
        print("ERROR: non-interactive runs require --yes", file=sys.stderr)
        return False
    return input("Continue? [y/N] ").strip().casefold() in {"y", "yes"}


def _job_arguments(args: argparse.Namespace) -> tuple[Path, str, str, int]:
    if not args.date and not args.latest:
        raise ValueError("choose --date or --latest")
    job_dir = resolve_job(args.workspace, args.date, args.latest)
    config = load_job_config(job_dir)
    return (
        job_dir,
        (args.subject or config.subject).strip(),
        (args.model or config.model).strip(),
        config.color_crop_size,
    )


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.action == "init":
            if not args.date or args.latest or not args.subject:
                raise ValueError("init requires --date and --subject")
            model = args.model or os.getenv("IMAGE_MODEL", "gpt-image-2")
            job = create_job(args.workspace, args.date, args.subject, model)
            print(f"Created {job}\nAdd source images to {job / 'input'}")
            print(f"Add color cards to {job / 'color_cards'}")
            print(f"Then run: subject-recolor plan --workspace {args.workspace} --date {args.date}")
            return 0
        if args.action == "doctor":
            lines, ok = run_doctor(args.workspace, args.base_url, args.api_key_env)
            print("\n".join(lines))
            return 0 if ok else 2
        if args.action == "demo":
            date = args.date or "2026-01-15"
            job = create_demo_job(args.workspace, date)
            config = load_job_config(job)
            tasks = build_tasks(job, config.subject, config.model)
            execute_tasks(tasks, OfflineDemoGateway(), job)
            print(build_review(tasks, job))
            print("Offline deterministic demo complete; outputs are not AI-generated.")
            return 0

        job_dir, subject, model, crop_size = _job_arguments(args)
        tasks = build_tasks(
            job_dir,
            subject,
            model,
            selected_cards=_selection(args.cards),
            selected_inputs=_selection(args.inputs),
            limit=args.limit,
            color_crop_size=crop_size,
        )
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    summary = summarize_plan(tasks)
    if args.json:
        if args.action != "plan":
            print("ERROR: --json is currently supported only for plan", file=sys.stderr)
            return 2
        payload = {
            "job": job_dir.name,
            "job_dir": str(job_dir),
            "subject": subject,
            "model": model,
            "inputs": sorted({task.source.stem for task in tasks}),
            "color_cards": sorted({task.color_card.stem for task in tasks}),
            **summary,
            "tasks_detail": [task.to_dict(job_dir) for task in tasks],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(f"job={job_dir.name} subject={subject} model={model}")
    print(
        "tasks={tasks} complete={complete} repair_jpg={repair_jpg} "
        "new_calls={new_calls}".format(**summary)
    )
    seen_cards: set[Path] = set()
    for task in tasks:
        if task.color_card in seen_cards:
            continue
        seen_cards.add(task.color_card)
        deviation = max(task.color.stddev)
        quality = "good" if deviation < 8 else ("moderate" if deviation <= 20 else "warning")
        print(
            f"color {task.color_card.name}: {task.color.hex} RGB{task.color.rgb} "
            f"consistency={quality} stddev={task.color.stddev} {task.color.label}"
        )

    if args.action == "plan":
        return 0
    if args.action == "review":
        print(build_review(tasks, job_dir))
        return 0
    if args.action == "evaluate":
        report = evaluate_tasks(tasks, job_dir)
        path = job_dir / "output" / "evaluation.json"
        atomic_write_json(path, report)
        print(path)
        return 0 if report["results_available"] == report["evaluated"] else 1
    if args.expect_calls is not None and args.expect_calls != summary["new_calls"]:
        message = (
            f"ERROR: expected {args.expect_calls} new calls, "
            f"current plan has {summary['new_calls']}"
        )
        print(message, file=sys.stderr)
        return 2
    if args.max_paid_calls is not None:
        if args.max_paid_calls < 0:
            print("ERROR: --max-paid-calls cannot be negative", file=sys.stderr)
            return 2
        if summary["new_calls"] > args.max_paid_calls:
            print(
                f"ERROR: {summary['new_calls']} new calls exceed "
                f"--max-paid-calls {args.max_paid_calls}",
                file=sys.stderr,
            )
            return 2
    if not args.yes and not _confirm(summary, job_dir, subject, model):
        return 2
    if not args.base_url:
        print("ERROR: set IMAGE_API_BASE_URL or pass --base-url", file=sys.stderr)
        return 2
    api_key = os.getenv(args.api_key_env, "")
    if not api_key:
        print(f"ERROR: environment variable {args.api_key_env} is not set", file=sys.stderr)
        return 2

    gateway = OpenAICompatibleGateway(args.base_url, api_key, args.timeout)
    results, halted = execute_tasks(tasks, gateway, job_dir)
    print(build_review(tasks, job_dir))
    failures = sum(item.get("status") not in {"succeeded"} for item in results)
    print(f"processed={len(results)} failures={failures} halted={halted}")
    return 3 if halted else (1 if failures else 0)
