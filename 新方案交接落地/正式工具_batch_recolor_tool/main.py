"""批量识别“待处理 × 色卡”，压缩上传副本并断点续跑主体换色任务。

可直接在 IDE 中运行：不传参数时会要求粘贴/选择包含“待处理”和“色卡”的任务文件夹。
正式调用前默认只展示计划并等待确认；API Key 从环境读取，仅在调用期间写入权限受限的短期临时 curl header 文件，并在每次调用后尽力删除，不写入持久配置、应用日志、输出产物或 curl argv。
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from recolor.config import load_settings
from recolor.core.processor import BatchProcessor, build_plan
from recolor.utils.files import clean_dragged_path

HERE = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="主体换色批量工具：输入任务文件夹，自动处理待处理图片 × 色卡全组合。"
    )
    parser.add_argument("project_dir", nargs="?", type=Path, help="包含 待处理/ 和 色卡/ 的任务文件夹")
    parser.add_argument("--config", type=Path, default=HERE / "config.json", help="可选本地配置 JSON")
    parser.add_argument("--subject", help="需要换色的主体，默认示例：户外窗帘（可为任意主体）")
    parser.add_argument(
        "--profile",
        choices=["A", "B", "a", "b"],
        help="默认B增强方案；A仅用于用户明确选择的复检任务",
    )
    parser.add_argument("--base-url", help="覆盖 Sub2API Base URL")
    parser.add_argument("--model", help="覆盖图片编辑模型")
    parser.add_argument("--workers", type=int, choices=[1], help="稳定版仅支持单线程，固定为1")
    parser.add_argument("--dry-run", action="store_true", help="只扫描、取色和输出计划，不压缩、不调用 API")
    parser.add_argument("--prepare-only", action="store_true", help="扫描并生成上传压缩缓存，不调用 API")
    parser.add_argument("--yes", action="store_true", help="跳过正式付费调用前的交互确认")
    parser.add_argument("--limit", type=int, default=0, help="本次最多执行前 N 个计划任务，0 表示全部")
    parser.add_argument(
        "--retry-uncertain",
        action="store_true",
        help="对账确认未扣费后，显式允许重提 uncertain 任务",
    )
    return parser.parse_args()


def choose_project_dir() -> Path:
    try:
        value = input("请输入任务文件夹（里面应有“待处理”和“色卡”；直接回车可打开选择框）：\n> ").strip()
    except EOFError:
        value = ""
    if value:
        return clean_dragged_path(value)

    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        selected = filedialog.askdirectory(title="选择换色任务文件夹")
        root.destroy()
        if selected:
            return Path(selected).resolve()
    except Exception as exc:
        print(f"无法打开文件夹选择框：{exc}", file=sys.stderr)
    raise SystemExit("没有选择任务文件夹。")


def setup_logging(records_dir: Path) -> None:
    records_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("batch_recolor")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    logfile = RotatingFileHandler(
        records_dir / "batch_recolor.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    logfile.setFormatter(formatter)
    logger.addHandler(console)
    logger.addHandler(logfile)


def print_plan(processor: BatchProcessor, retry_uncertain: bool, limit: int) -> dict:
    plan = processor.plan
    preview = processor.preview(retry_uncertain=retry_uncertain, limit=limit)
    executable = preview["new_api_calls"]
    print("\n========== 批量换色执行计划 ==========")
    print(f"任务目录     : {plan.project_dir}")
    print(f"换色主体     : {processor.settings.subject}")
    print(f"Prompt 方案  : {processor.settings.profile_label}")
    print(f"待处理图片   : {preview['sources']}")
    print(f"独立上下文   : {preview['sources']}（每张原图一个）")
    print(f"执行线程数   : {processor.settings.context_workers}（稳定版固定单线程）")
    print(f"色卡图片     : {preview['cards']}")
    print(f"全组合数量   : {preview['total']}")
    if limit > 0:
        print(f"本次选择任务 : {preview['selected']}（--limit {limit}）")
    print(f"已完成可跳过 : {preview['completed']}")
    print(f"只需补 JPG   : {preview['repairable_jpg']}")
    print(f"uncertain    : {preview['uncertain']}")
    print(f"预计新增调用 : {executable}")
    print(f"输出目录     : {plan.profile_root}")
    print("色卡取色：")
    for card in plan.cards:
        color = plan.colors[card.name]
        print(f"  - {card.name}: {color['hex']} RGB{tuple(color['rgb'])} {color['description']}")
    print("======================================\n")
    return {**preview, "executable": executable}


def confirm_paid_run(call_count: int, retry_uncertain: bool) -> bool:
    print("提醒：图片编辑接口没有已验证幂等键；如使用 HTTP，凭据和图片将明文传输。")
    if retry_uncertain:
        print("警告：已开启 uncertain 重提，请确保已按 request ID/usage 对账且确认未扣费。")
    answer = input(f"确认开始最多 {call_count} 次付费图片调用？输入 YES 继续：").strip()
    return answer == "YES"


def main() -> int:
    args = parse_args()
    if args.limit < 0:
        raise SystemExit("--limit 不能小于 0")
    project_dir = args.project_dir.resolve() if args.project_dir else choose_project_dir()
    config_path = args.config if args.config.exists() else None
    settings = load_settings(
        config_path,
        {
            "subject": args.subject,
            "profile": args.profile,
            "base_url": args.base_url,
            "model": args.model,
            "context_workers": args.workers,
        },
    )

    plan = build_plan(project_dir, settings)
    setup_logging(plan.records_dir)
    processor = BatchProcessor(plan, settings)
    preview = print_plan(processor, args.retry_uncertain, args.limit)

    if args.dry_run:
        print(f"DRY RUN 完成。任务清单：{plan.manifest_path}")
        return 0
    if args.prepare_only:
        processor.prepare_inputs()
        processor.write_reports()
        print(f"上传压缩缓存已准备：{plan.cache_dir}")
        return 0
    if preview["executable"] == 0 and preview["repairable_jpg"] == 0:
        processor.write_reports()
        print("没有需要调用或修复的任务。")
        return 0

    if preview["executable"] > 0 and not settings.endpoint:
        print("缺少网关地址：请设置 SUB2API_BASE_URL 或传入 --base-url。", file=sys.stderr)
        return 2
    if preview["executable"] > 0 and not args.yes and not confirm_paid_run(preview["executable"], args.retry_uncertain):
        print("已取消，没有调用 API。")
        return 0

    api_key = os.environ.get("SUB2API_API_KEY") or os.environ.get("SUB2API_KEY") or ""
    if preview["executable"] > 0 and not api_key:
        print("缺少 API Key：请设置环境变量 SUB2API_API_KEY。", file=sys.stderr)
        return 2

    counts = processor.run(
        api_key,
        limit=args.limit,
        retry_uncertain=args.retry_uncertain,
    )
    print(f"运行结束：{counts}")
    print(f"审阅页：{plan.profile_root / '审阅页.html'}")
    if counts.get("uncertain", 0):
        return 3
    if counts.get("rejected", 0) or counts.get("failed_safe", 0):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
