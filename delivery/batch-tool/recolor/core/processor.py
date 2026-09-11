"""Plan and execute a resumable Cartesian-product recoloring batch."""

from __future__ import annotations

import csv
import html
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from ..api.image_edit_client import FatalError, ImageEditClient, SafeRetryError, UncertainError
from ..config import Settings, public_settings
from ..data.checkpoint import CheckpointStore, utc_now
from ..utils.files import (
    atomic_write_json,
    atomic_write_text,
    list_images,
    safe_name,
    sha256_file,
    stable_hash,
    validate_input_image,
    valid_output_image,
)
from .images import PreparedImage, prepare_upload, repair_jpg, save_model_outputs
from .prompt_builder import PROMPT_VERSION, build_prompt, extract_color

LOGGER = logging.getLogger("batch_recolor")


@dataclass
class BatchPlan:
    project_dir: Path
    sources: list[Path]
    cards: list[Path]
    contexts: list[dict[str, Any]]
    colors: dict[str, dict[str, Any]]
    tasks: list[dict[str, Any]]
    output_root: Path
    profile_root: Path
    records_dir: Path
    cache_dir: Path

    @property
    def manifest_path(self) -> Path:
        profile = self.tasks[0]["profile"] if self.tasks else "unknown"
        return self.records_dir / f"plan_profile_{profile}.json"


def _ensure_unique_stems(paths: list[Path], label: str) -> None:
    groups: dict[str, list[str]] = {}
    for path in paths:
        groups.setdefault(safe_name(path.stem).casefold(), []).append(path.name)
    duplicates = [names for names in groups.values() if len(names) > 1]
    if duplicates:
        detail = "; ".join(", ".join(names) for names in duplicates)
        raise ValueError(f"{label}存在重复文件主名，会覆盖输出：{detail}")


def build_plan(project_dir: Path, settings: Settings) -> BatchPlan:
    project_dir = project_dir.resolve()
    source_dir = project_dir / "待处理"
    card_dir = project_dir / "色卡"
    sources = list_images(source_dir)
    cards = list_images(card_dir)
    if not sources:
        raise ValueError(f"待处理目录没有支持的图片：{source_dir}")
    if not cards:
        raise ValueError(f"色卡目录没有支持的图片：{card_dir}")
    _ensure_unique_stems(sources, "待处理目录")
    _ensure_unique_stems(cards, "色卡目录")

    source_info: dict[str, dict[str, Any]] = {}
    for source in sources:
        size = validate_input_image(source)
        source_info[source.name] = {"sha256": sha256_file(source), "size": list(size)}
    card_info: dict[str, dict[str, Any]] = {}
    colors: dict[str, dict[str, Any]] = {}
    for card in cards:
        size = validate_input_image(card)
        digest = sha256_file(card)
        color = extract_color(card)
        card_info[card.name] = {"sha256": digest, "size": list(size)}
        colors[card.name] = color

    output_root = project_dir / "生成图"
    profile_root = output_root / settings.profile_label
    records_dir = output_root / "记录"
    cache_dir = output_root / "缓存" / "压缩输入"
    png_dir = profile_root / "png"
    jpg_dir = profile_root / "jpg"
    contexts: list[dict[str, Any]] = []
    tasks: list[dict[str, Any]] = []
    for source_index, source in enumerate(sources, 1):
        context_id = stable_hash(
            ["source-image-context", source.name, source_info[source.name]["sha256"]],
            length=16,
        )
        contexts.append(
            {
                "context_id": context_id,
                "context_index": source_index,
                "context_name": safe_name(source.stem),
                "source": str(source),
                "source_sha256": source_info[source.name]["sha256"],
                "color_variant_count": len(cards),
            }
        )
        for card in cards:
            color = colors[card.name]
            prompt = build_prompt(settings.subject, color, settings.profile)
            task_id = stable_hash(
                [
                    source_info[source.name]["sha256"],
                    source.name,
                    card_info[card.name]["sha256"],
                    card.name,
                    settings.subject,
                    settings.profile,
                    PROMPT_VERSION,
                ]
            )
            basename = f"{safe_name(source.stem)}__{safe_name(card.stem)}"
            tasks.append(
                {
                    "task_id": task_id,
                    "task_name": basename,
                    "context_id": context_id,
                    "context_index": source_index,
                    "context_name": safe_name(source.stem),
                    "source": str(source),
                    "source_sha256": source_info[source.name]["sha256"],
                    "source_size": source_info[source.name]["size"],
                    "card": str(card),
                    "card_sha256": card_info[card.name]["sha256"],
                    "card_size": card_info[card.name]["size"],
                    "color": color,
                    "subject": settings.subject,
                    "profile": settings.profile,
                    "prompt_version": PROMPT_VERSION,
                    "prompt": prompt,
                    "png": str(png_dir / f"{basename}.png"),
                    "jpg": str(jpg_dir / f"{basename}.jpg"),
                    "metadata": str(profile_root / "metadata" / f"{basename}.json"),
                }
            )
    return BatchPlan(
        project_dir=project_dir,
        sources=sources,
        cards=cards,
        contexts=contexts,
        colors=colors,
        tasks=tasks,
        output_root=output_root,
        profile_root=profile_root,
        records_dir=records_dir,
        cache_dir=cache_dir,
    )


def _strict_artifact_state(task: dict[str, Any]) -> str:
    png = Path(task["png"])
    jpg = Path(task["jpg"])
    metadata = Path(task["metadata"])
    try:
        data = json.loads(metadata.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "new_call"
    if data.get("task_id") != task["task_id"] or not valid_output_image(png):
        return "new_call"
    if data.get("png_sha256") != sha256_file(png):
        return "new_call"
    if not valid_output_image(jpg):
        return "repair_jpg"
    if data.get("jpg_sha256") != sha256_file(jpg):
        return "repair_jpg"
    return "complete"


def _write_task_metadata(task: dict[str, Any], request_id: str, response: dict[str, Any]) -> None:
    png, jpg = Path(task["png"]), Path(task["jpg"])
    atomic_write_json(
        Path(task["metadata"]),
        {
            "task_id": task["task_id"],
            "source_sha256": task["source_sha256"],
            "card_sha256": task["card_sha256"],
            "subject": task["subject"],
            "profile": task["profile"],
            "prompt_version": task["prompt_version"],
            "request_id": request_id,
            "png_sha256": sha256_file(png),
            "jpg_sha256": sha256_file(jpg),
            "response": response,
            "completed_at": utc_now(),
        },
    )


class BatchProcessor:
    def __init__(self, plan: BatchPlan, settings: Settings):
        self.plan = plan
        self.settings = settings
        self.plan.records_dir.mkdir(parents=True, exist_ok=True)
        profile = settings.profile
        self.checkpoint = CheckpointStore(
            self.plan.records_dir / f"checkpoint_profile_{profile}.json",
            self.plan.records_dir / f"events_profile_{profile}.jsonl",
        )
        run_info = {
            "project_dir": str(plan.project_dir),
            "subject": settings.subject,
            "profile": profile,
            "profile_label": settings.profile_label,
            "prompt_version": PROMPT_VERSION,
            "planned_at": utc_now(),
            "task_count": len(plan.tasks),
            "settings": public_settings(settings),
        }
        self.checkpoint.initialize(run_info, plan.tasks)
        atomic_write_json(
            plan.manifest_path,
            {
                "created_at": utc_now(),
                "run": run_info,
                "sources": [str(path) for path in plan.sources],
                "cards": [str(path) for path in plan.cards],
                "contexts": plan.contexts,
                "colors": plan.colors,
                "tasks": plan.tasks,
            },
        )

    def preview(self, retry_uncertain: bool = False, limit: int = 0) -> dict[str, Any]:
        completed = repairable = uncertain = pending = 0
        selected = self.plan.tasks[:limit] if limit > 0 else self.plan.tasks
        for task in selected:
            artifact_state = _strict_artifact_state(task)
            status = self.checkpoint.task(task["task_id"]).get("status", "pending")
            if artifact_state == "complete":
                completed += 1
            elif artifact_state == "repair_jpg":
                repairable += 1
            elif status == "uncertain" and not retry_uncertain:
                uncertain += 1
            else:
                pending += 1
        return {
            "sources": len(self.plan.sources),
            "cards": len(self.plan.cards),
            "total": len(self.plan.tasks),
            "selected": len(selected),
            "completed": completed,
            "repairable_jpg": repairable,
            "uncertain": uncertain,
            "new_api_calls": pending,
        }

    def prepare_inputs(self, task_subset: Optional[list[dict[str, Any]]] = None) -> dict[str, PreparedImage]:
        tasks = task_subset or self.plan.tasks
        unique_sources = {task["source"]: Path(task["source"]) for task in tasks}
        prepared: dict[str, PreparedImage] = {}
        LOGGER.info("开始准备上传压缩副本：%d 张原图", len(unique_sources))
        for index, (source_key, source) in enumerate(unique_sources.items(), 1):
            item = prepare_upload(source, self.plan.cache_dir, self.settings)
            prepared[source_key] = item
            LOGGER.info(
                "[%d/%d] %s: %sx%s %.2fMB -> %sx%s %.2fMB",
                index,
                len(unique_sources),
                source.name,
                item.original_size[0],
                item.original_size[1],
                item.original_bytes / 1024 / 1024,
                item.upload_size[0],
                item.upload_size[1],
                item.upload_bytes / 1024 / 1024,
            )
        atomic_write_json(
            self.plan.records_dir / f"compression_profile_{self.settings.profile}.json",
            {
                "created_at": utc_now(),
                "settings": public_settings(self.settings),
                "images": [item.to_dict() for item in prepared.values()],
            },
        )
        return prepared

    def run(
        self,
        api_key: str,
        *,
        limit: int = 0,
        retry_uncertain: bool = False,
    ) -> dict[str, int]:
        selected = self.plan.tasks[:limit] if limit > 0 else self.plan.tasks
        pending_for_upload: list[dict[str, Any]] = []

        for task in selected:
            task_id = task["task_id"]
            png, jpg = Path(task["png"]), Path(task["jpg"])
            artifact_state = _strict_artifact_state(task)
            if artifact_state == "complete":
                if self.checkpoint.task(task_id).get("status") != "succeeded":
                    self.checkpoint.mark(task_id, "succeeded", recovered_from_outputs=True)
                continue
            if artifact_state == "repair_jpg":
                size = repair_jpg(png, jpg, self.settings.jpg_quality)
                old = json.loads(Path(task["metadata"]).read_text(encoding="utf-8"))
                _write_task_metadata(task, old.get("request_id", ""), old.get("response", {}))
                self.checkpoint.mark(task_id, "succeeded", repaired_jpg=True, output_size=list(size))
                LOGGER.info("只补 JPG（不调用模型）：%s", jpg.name)
                continue
            if self.checkpoint.task(task_id).get("status") == "uncertain" and not retry_uncertain:
                LOGGER.warning("跳过 uncertain 任务，需对账后显式 --retry-uncertain：%s", task["task_name"])
                continue
            pending_for_upload.append(task)

        context_sources: dict[str, str] = {}
        for task in pending_for_upload:
            previous_source = context_sources.setdefault(task["context_id"], task["source"])
            if previous_source != task["source"]:
                raise ValueError(
                    f"上下文隔离校验失败：context {task['context_id']} 同时包含多张原图"
                )

        prepared = self.prepare_inputs(pending_for_upload) if pending_for_upload else {}
        if not pending_for_upload:
            self.write_reports()
            return self.checkpoint.counts([task["task_id"] for task in selected])
        stop_batch = False
        processed_since_report = 0
        current_context_id: Optional[str] = None
        with ImageEditClient(self.settings, api_key) as client:
            for position, task in enumerate(pending_for_upload, 1):
                if stop_batch:
                    break
                if task["context_id"] != current_context_id:
                    if current_context_id is not None:
                        client.reconnect()
                    current_context_id = task["context_id"]
                    LOGGER.info(
                        "进入独立原图上下文 [%s] %s；本上下文只允许原图 %s",
                        task["context_id"],
                        task["context_name"],
                        Path(task["source"]).name,
                    )
                task_id = task["task_id"]
                upload = Path(prepared[task["source"]].upload_path)
                png, jpg = Path(task["png"]), Path(task["jpg"])
                started = time.monotonic()
                max_attempts = self.settings.max_safe_retries + 1
                for invocation_attempt in range(1, max_attempts + 1):
                    request_id = str(uuid.uuid4())
                    attempt = self.checkpoint.add_request(task_id, request_id)
                    LOGGER.info(
                        "[%d/%d] 提交 %s，attempt=%d，request_id=%s",
                        position,
                        len(pending_for_upload),
                        task["task_name"],
                        attempt,
                        request_id,
                    )
                    try:
                        result = client.edit(upload, task["prompt"], request_id)
                        size = save_model_outputs(result.image_bytes, png, jpg, self.settings.jpg_quality)
                        _write_task_metadata(task, request_id, result.metadata)
                        elapsed = round(time.monotonic() - started, 2)
                        original_size = prepared[task["source"]].original_size
                        original_ratio = original_size[0] / original_size[1]
                        output_ratio = size[0] / size[1]
                        warnings = []
                        if abs(original_ratio - output_ratio) / original_ratio > 0.04:
                            warnings.append(f"输出比例 {size} 与原图 {original_size} 差异超过 4%")
                        self.checkpoint.mark(
                            task_id,
                            "succeeded",
                            elapsed_seconds=elapsed,
                            output_size=list(size),
                            png=str(png),
                            jpg=str(jpg),
                            response=result.metadata,
                            quality_warnings=warnings,
                        )
                        LOGGER.info("成功：%s，%.2fs，size=%s", task["task_name"], elapsed, size)
                        break
                    except SafeRetryError as exc:
                        elapsed = round(time.monotonic() - started, 2)
                        if invocation_attempt >= max_attempts:
                            self.checkpoint.mark(
                                task_id,
                                "failed_safe",
                                elapsed_seconds=elapsed,
                                http_status=exc.http_status,
                                last_error=str(exc),
                            )
                            LOGGER.error("安全重试已用完，停止整批：%s", exc)
                            stop_batch = True
                            break
                        delay = exc.retry_after if exc.retry_after is not None else self.settings.retry_delay_seconds
                        self.checkpoint.mark(
                            task_id,
                            "retry_wait",
                            http_status=exc.http_status,
                            last_error=str(exc),
                            retry_in_seconds=delay,
                        )
                        LOGGER.warning("明确拒绝/连接失败，%.0f 秒后重连一次：%s", delay, exc)
                        time.sleep(delay)
                        client.reconnect()
                    except UncertainError as exc:
                        elapsed = round(time.monotonic() - started, 2)
                        self.checkpoint.mark(
                            task_id,
                            "uncertain",
                            elapsed_seconds=elapsed,
                            http_status=exc.http_status,
                            last_error=str(exc),
                        )
                        LOGGER.error("状态 uncertain，为避免重复扣费立即停止：%s", exc)
                        stop_batch = True
                        break
                    except FatalError as exc:
                        elapsed = round(time.monotonic() - started, 2)
                        self.checkpoint.mark(
                            task_id,
                            "rejected",
                            elapsed_seconds=elapsed,
                            http_status=exc.http_status,
                            last_error=str(exc),
                        )
                        LOGGER.error("请求被拒绝，停止整批：%s", exc)
                        stop_batch = True
                        break
                    except Exception as exc:
                        elapsed = round(time.monotonic() - started, 2)
                        self.checkpoint.mark(
                            task_id,
                            "failed_safe",
                            elapsed_seconds=elapsed,
                            last_error=f"本地处理错误 {type(exc).__name__}: {exc}",
                        )
                        LOGGER.exception("本地保存/校验失败；输出若已有，下次会优先修复：%s", task["task_name"])
                        break

                processed_since_report += 1
                if processed_since_report >= self.settings.save_every:
                    self.write_reports()
                    processed_since_report = 0
                if not stop_batch and self.settings.pause_between_tasks > 0:
                    time.sleep(self.settings.pause_between_tasks)

        self.write_reports()
        return self.checkpoint.counts([task["task_id"] for task in selected])

    def write_reports(self) -> None:
        self._write_summary_csv()
        self._write_review_html()
        self.checkpoint.save()

    def _write_summary_csv(self) -> None:
        target = self.plan.records_dir / f"summary_profile_{self.settings.profile}.csv"
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(target.suffix + ".part")
        fields = [
            "task_id",
            "context_id",
            "context_name",
            "status",
            "task_name",
            "source",
            "card",
            "hex",
            "rgb",
            "attempts",
            "request_ids",
            "png",
            "jpg",
            "last_error",
        ]
        with temp.open("w", encoding="utf-8-sig", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=fields)
            writer.writeheader()
            for planned in self.plan.tasks:
                state = self.checkpoint.task(planned["task_id"])
                writer.writerow(
                    {
                        "task_id": planned["task_id"],
                        "context_id": planned["context_id"],
                        "context_name": planned["context_name"],
                        "status": state.get("status", "pending"),
                        "task_name": planned["task_name"],
                        "source": planned["source"],
                        "card": planned["card"],
                        "hex": planned["color"]["hex"],
                        "rgb": ",".join(map(str, planned["color"]["rgb"])),
                        "attempts": state.get("attempts", 0),
                        "request_ids": " | ".join(state.get("request_ids", [])),
                        "png": planned["png"],
                        "jpg": planned["jpg"],
                        "last_error": state.get("last_error", ""),
                    }
                )
        os.replace(temp, target)

    def _relative_url(self, path: Path, base: Path) -> str:
        return Path(os.path.relpath(path, base)).as_posix()

    def _write_review_html(self) -> None:
        target = self.plan.profile_root / "审阅页.html"
        cards: list[str] = []
        for task in self.plan.tasks:
            state = self.checkpoint.task(task["task_id"])
            status = state.get("status", "pending")
            source_url = html.escape(self._relative_url(Path(task["source"]), target.parent), quote=True)
            card_url = html.escape(self._relative_url(Path(task["card"]), target.parent), quote=True)
            jpg_path = Path(task["jpg"])
            result = (
                f'<img src="{html.escape(self._relative_url(jpg_path, target.parent), quote=True)}" alt="result">'
                if valid_output_image(jpg_path)
                else '<div class="empty">尚无结果</div>'
            )
            color_hex = html.escape(task["color"]["hex"])
            cards.append(
                f"""
                <article class="task">
                  <h2>{html.escape(task['task_name'])}</h2>
                  <p class="context">独立原图上下文：{html.escape(task['context_id'])} · {html.escape(task['context_name'])}</p>
                  <p><span class="status {html.escape(status)}">{html.escape(status)}</span>
                     <span class="swatch" style="background:{color_hex}"></span>{color_hex}</p>
                  <div class="images">
                    <figure><img src="{source_url}" alt="source"><figcaption>原图</figcaption></figure>
                    <figure><img src="{card_url}" alt="color card"><figcaption>色卡</figcaption></figure>
                    <figure>{result}<figcaption>{html.escape(self.settings.profile_label)}结果</figcaption></figure>
                  </div>
                </article>
                """
            )
        counts = self.checkpoint.counts([task["task_id"] for task in self.plan.tasks])
        document = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>批量换色审阅 - {html.escape(self.settings.profile_label)}</title>
<style>
body{{font-family:Segoe UI,Microsoft YaHei,sans-serif;margin:24px;background:#f3f4f6;color:#172033}}
.summary,.task{{max-width:1400px;margin:0 auto 20px;background:white;border-radius:12px;padding:18px;box-shadow:0 2px 12px #0001}}
.images{{display:grid;grid-template-columns:1fr 180px 1fr;gap:12px;align-items:start}}figure{{margin:0}}img,.empty{{width:100%;max-height:560px;object-fit:contain;background:#eee;border-radius:8px}}.empty{{height:240px;display:grid;place-items:center;color:#777}}
figcaption{{text-align:center;margin-top:6px}}.status{{padding:3px 8px;border-radius:999px;background:#e5e7eb}}.succeeded{{background:#dcfce7;color:#166534}}.uncertain{{background:#fef3c7;color:#92400e}}.rejected,.failed_safe{{background:#fee2e2;color:#991b1b}}.swatch{{display:inline-block;width:20px;height:20px;border:1px solid #999;vertical-align:middle;margin:0 6px 0 14px}}
@media(max-width:800px){{.images{{grid-template-columns:1fr}}}}
</style></head><body>
<section class="summary"><h1>{html.escape(self.settings.subject)} · {html.escape(self.settings.profile_label)}</h1>
<p>任务目录：{html.escape(str(self.plan.project_dir))}</p><p>状态：{html.escape(json.dumps(counts, ensure_ascii=False))}</p></section>
{''.join(cards)}</body></html>"""
        atomic_write_text(target, document)
