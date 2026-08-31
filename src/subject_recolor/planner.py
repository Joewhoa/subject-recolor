from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .color import sample_center_mean
from .models import RecolorTask
from .prompt import PROMPT_VERSION, build_prompt
from .utils import list_images, safe_name, sha256_file

DATE_PATTERN = re.compile(r"(?:\d{4}|\d{8}|\d{4}-\d{2}-\d{2})$")


def discover_jobs(workspace: Path) -> list[Path]:
    if not workspace.is_dir():
        return []
    return sorted(
        (
            path
            for path in workspace.iterdir()
            if path.is_dir()
            and not path.name.startswith(".")
            and DATE_PATTERN.fullmatch(path.name)
            and (path / "input").is_dir()
            and (path / "color_cards").is_dir()
        ),
        key=lambda path: path.name,
    )


def resolve_job(workspace: Path, date: str | None, latest: bool) -> Path:
    jobs = discover_jobs(workspace)
    if date:
        candidate = workspace / date
        if candidate not in jobs:
            raise ValueError(f"not a valid job directory: {candidate}")
        return candidate
    if latest and jobs:
        return jobs[-1]
    raise ValueError("choose --date or --latest; no matching job was found")


def _ensure_unique_stems(paths: list[Path], label: str) -> None:
    by_stem: dict[str, list[Path]] = {}
    for path in paths:
        by_stem.setdefault(path.stem.casefold(), []).append(path)
    duplicates = [items for items in by_stem.values() if len(items) > 1]
    if duplicates:
        details = "; ".join(", ".join(path.name for path in items) for items in duplicates)
        raise ValueError(f"duplicate {label} stems would overwrite outputs: {details}")


def build_tasks(
    job_dir: Path,
    subject: str,
    model: str,
    selected_cards: set[str] | None = None,
    selected_inputs: set[str] | None = None,
    limit: int = 0,
    color_crop_size: int = 200,
) -> list[RecolorTask]:
    sources = list_images(job_dir / "input")
    cards = list_images(job_dir / "color_cards")
    _ensure_unique_stems(sources, "input")
    _ensure_unique_stems(cards, "color-card")
    if selected_inputs is not None:
        sources = [source for source in sources if source.stem in selected_inputs]
        missing = selected_inputs - {source.stem for source in sources}
        if missing:
            raise ValueError(f"inputs not found: {', '.join(sorted(missing))}")
    if selected_cards is not None:
        cards = [card for card in cards if card.stem in selected_cards]
        missing = selected_cards - {card.stem for card in cards}
        if missing:
            raise ValueError(f"color cards not found: {', '.join(sorted(missing))}")
    if not sources or not cards:
        raise ValueError(f"job requires images: input={len(sources)}, color_cards={len(cards)}")

    output = job_dir / "output"
    tasks: list[RecolorTask] = []
    source_hashes = {path: sha256_file(path) for path in sources}
    card_hashes = {path: sha256_file(path) for path in cards}
    colors = {path: sample_center_mean(path, color_crop_size) for path in cards}
    for source in sources:
        for card in cards:
            color = colors[card]
            prompt = build_prompt(subject, color)
            identity = "\n".join(
                [source_hashes[source], card_hashes[card], subject, model, PROMPT_VERSION, prompt]
            )
            task_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]
            basename = f"{safe_name(source.stem)}__{safe_name(card.stem)}"
            tasks.append(
                RecolorTask(
                    task_id=task_id,
                    source=source,
                    color_card=card,
                    source_sha256=source_hashes[source],
                    color_card_sha256=card_hashes[card],
                    color=color,
                    subject=subject,
                    profile=PROMPT_VERSION,
                    prompt=prompt,
                    model=model,
                    png_path=output / "png" / f"{basename}.png",
                    jpg_path=output / "jpg" / f"{basename}.jpg",
                    metadata_path=output / "metadata" / f"{basename}.json",
                )
            )
    return tasks[:limit] if limit > 0 else tasks
