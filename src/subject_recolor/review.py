from __future__ import annotations

from html import escape
from pathlib import Path
from urllib.parse import quote

from .artifacts import valid_image
from .models import RecolorTask
from .provenance import source_record
from .utils import atomic_write


def _href(path: Path, output: Path) -> str:
    return quote(path.relative_to(output).as_posix())


def _image(path: Path, output: Path, label: str) -> str:
    if not valid_image(path):
        return f'<div class="placeholder">{escape(label)}不可用</div>'
    href = _href(path, output)
    return f'<a href="{href}"><img src="{href}" alt="{escape(label)}"></a>'


def color_consistency(task: RecolorTask) -> tuple[str, str]:
    deviation = max(task.color.stddev)
    if deviation < 8:
        return "good", "色卡一致性：良好"
    if deviation <= 20:
        return "moderate", "色卡一致性：一般，请检查取色区域"
    return "warning", "色卡一致性：较差，建议换用更均匀的色卡"


def build_review(tasks: list[RecolorTask], job_dir: Path) -> Path:
    output = job_dir / "output"
    cards: list[str] = []
    for task in tasks:
        complete = valid_image(task.jpg_path) and valid_image(task.png_path)
        status = "完成" if complete else "待生成"
        level, consistency = color_consistency(task)
        result = _image(task.jpg_path, output, "换色结果")
        source_rel = "../" + task.source.relative_to(job_dir).as_posix()
        card_rel = "../" + task.color_card.relative_to(job_dir).as_posix()
        source = f'<a href="{quote(source_rel)}"><img src="{quote(source_rel)}" alt="原图"></a>'
        color_card = (
            f'<a href="{quote(card_rel)}"><img src="{quote(card_rel)}" alt="色卡"></a>'
        )
        png_link = (
            f'<a href="{_href(task.png_path, output)}">PNG 母版</a>'
            if valid_image(task.png_path)
            else ""
        )
        provenance = source_record(task, job_dir)
        attribution_html = ""
        if provenance:
            title = escape(str(provenance.get("title", task.source.name)))
            creator = escape(str(provenance.get("creator", "unknown")))
            license_name = escape(str(provenance.get("license", "license not recorded")))
            source_page = escape(str(provenance.get("source_page", "")), quote=True)
            license_url = escape(str(provenance.get("license_url", "")), quote=True)
            attribution_html = (
                '<div class="attribution"><strong>来源与许可：</strong>'
                f'<a href="{source_page}">{title}</a> by {creator} · '
                f'<a href="{license_url}">{license_name}</a> · 本图结果为修改版本。'
                "</div>"
            )
        cards.append(
            '<article class="card">'
            f'<div class="swatch" style="background:{escape(task.color.hex)}"></div>'
            f'<h2>{escape(task.source.name)} × {escape(task.color_card.name)}</h2>'
            f'<p><span class="badge">{status}</span> 主体：{escape(task.subject)} · '
            f'{escape(task.color.label)} {escape(task.color.hex)} · RGB {task.color.rgb}</p>'
            f'<p class="{level}">{escape(consistency)} · 标准差 {task.color.stddev}</p>'
            '<div class="triptych">'
            f'<figure>{source}<figcaption>原图</figcaption></figure>'
            f'<figure>{color_card}<figcaption>色卡</figcaption></figure>'
            f'<figure>{result}<figcaption>换色结果</figcaption></figure>'
            "</div>"
            f'<p>Task ID: <code>{task.task_id}</code> · '
            f'Model: {escape(task.model)} · {png_link}</p>'
            '<div class="checklist">人工验收：□ 通过　□ 漏换　□ 背景变化　□ 颜色偏差　'
            "□ 边缘污染　□ 材质/结构丢失</div>"
            f"{attribution_html}"
            "</article>"
        )
    html = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>{escape(job_dir.name)} 主体换色审阅</title><style>
:root{{--bg:#f5f7fb;--card:#fff;--text:#1f2937;--muted:#64748b;--accent:#2563eb}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font-family:system-ui,sans-serif}}
header,main{{max-width:1600px;margin:auto;padding:24px}}header p{{color:var(--muted)}}
.card{{background:var(--card);padding:18px;margin-bottom:20px;border-radius:16px;
box-shadow:0 4px 20px #0f172a12}}
.triptych{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}}
figure{{margin:0}}figcaption{{text-align:center;color:var(--muted);padding:6px}}
img,.placeholder{{width:100%;aspect-ratio:1;object-fit:contain;background:#eef2f7;border-radius:10px}}
.placeholder{{display:grid;place-items:center;color:var(--muted)}}h2{{font-size:17px;word-break:break-all}}
.swatch{{height:12px;border-radius:999px;border:1px solid #0002}}
.badge{{background:#e2e8f0;padding:3px 8px;border-radius:999px}}a{{color:var(--accent)}}
.good{{color:#15803d}}.moderate{{color:#a16207}}.warning{{color:#b91c1c;font-weight:600}}
.checklist,.attribution{{background:#f8fafc;border:1px solid #e2e8f0;padding:12px;
border-radius:10px;margin-top:10px}}
@media(max-width:800px){{.triptych{{grid-template-columns:1fr}}}}
</style></head><body><header><h1>{escape(job_dir.name)} 指定主体换色审阅</h1>
<p>对照原图、色卡和结果，人工检查完整覆盖、颜色、材质/结构、边界污染与背景保持。</p></header>
<main>{''.join(cards)}</main></body></html>"""
    path = output / "review.html"
    atomic_write(path, html.encode("utf-8"))
    return path
