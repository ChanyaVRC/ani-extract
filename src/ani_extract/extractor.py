"""Extract frames from an ANI file and write them out in various formats."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .ani import AniFile, parse_ani
from .animation import normalize_canvas, save_apng, save_gif, save_webp
from .icons import IconContainer, IconError, open_entry, parse_icon_container

if TYPE_CHECKING:  # pragma: no cover
    from PIL import Image

__all__ = ["ExtractOptions", "ExtractResult", "extract"]

_METADATA_FILENAME = "metadata.json"
_GIF_FILENAME = "animation.gif"
_APNG_FILENAME = "animation.png"
_WEBP_FILENAME = "animation.webp"


@dataclass(frozen=True, kw_only=True)
class ExtractOptions:
    """Options controlling extraction behavior."""

    write_raw: bool = True
    write_png: bool = True
    all_sizes: bool = False
    write_sequence: bool = False
    write_gif: bool = False
    write_apng: bool = False
    write_webp: bool = False
    write_metadata: bool = True


@dataclass
class ExtractResult:
    """Summary of an extraction run."""

    source: Path
    output_directory: Path
    ani: AniFile
    written_files: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    png_count: int = 0

    @property
    def frame_count(self) -> int:
        return len(self.ani.frames)

    @property
    def step_count(self) -> int:
        return len(self.ani.sequence)


def _frame_metadata(index: int, container: IconContainer | None) -> dict[str, Any]:
    if container is None:
        return {"index": index, "format": None, "images": []}

    return {
        "index": index,
        "format": container.kind,
        "images": [
            {
                "width": entry.width,
                "height": entry.height,
                "bit_count": entry.bit_count,
                "hotspot": list(entry.hotspot) if entry.hotspot else None,
            }
            for entry in container.entries
        ],
    }


def _build_metadata(result: ExtractResult, frames: list[dict[str, Any]]) -> dict[str, Any]:
    ani = result.ani
    header = ani.header

    return {
        "source": result.source.name,
        "title": ani.title,
        "author": ani.author,
        "header": None
        if header is None
        else {
            "frame_count": header.frame_count,
            "step_count": header.step_count,
            "width": header.width,
            "height": header.height,
            "bit_count": header.bit_count,
            "plane_count": header.plane_count,
            "display_rate_jiffies": header.display_rate,
            "flags": header.flags,
            "contains_icons": header.contains_icons,
            "has_sequence": header.has_sequence,
        },
        "frames": frames,
        "sequence": list(ani.sequence),
        "rates_jiffies": list(ani.rates),
        "durations_ms": ani.durations_ms,
        "total_duration_ms": sum(ani.durations_ms),
        "warnings": list(result.warnings),
    }


def extract(source: Path, output_directory: Path, options: ExtractOptions) -> ExtractResult:
    """Parse the ANI file at ``source`` and write outputs to ``output_directory``.

    Args:
        source: Input ``.ani`` file.
        output_directory: Output directory; created if it does not exist.
        options: What to write.

    Returns:
        An :class:`ExtractResult` with the list of written files and warnings.
    """
    ani = parse_ani(source.read_bytes())
    output_directory.mkdir(parents=True, exist_ok=True)

    result = ExtractResult(source=source, output_directory=output_directory, ani=ani)

    if ani.header is not None and not ani.header.contains_icons:
        result.warnings.append("The anih icon flag is not set; frames may be raw DIBs.")

    frame_metadata: list[dict[str, Any]] = []
    representatives: dict[int, Image.Image] = {}

    for index, payload in enumerate(ani.frames):
        stem = f"frame_{index:03d}"

        try:
            container: IconContainer | None = parse_icon_container(payload)
        except IconError as error:
            container = None
            result.warnings.append(f"{stem}: cannot parse as ICO/CUR ({error})")

        frame_metadata.append(_frame_metadata(index, container))

        if options.write_raw:
            extension = container.extension if container else ".bin"
            raw_path = output_directory / f"{stem}{extension}"
            raw_path.write_bytes(payload)
            result.written_files.append(raw_path)

        if container is None:
            continue

        try:
            representative = open_entry(container.largest)
        except Exception as error:  # noqa: BLE001 - Pillow raises a wide variety of exceptions
            result.warnings.append(f"{stem}: could not open image ({error})")
            continue

        representatives[index] = representative

        if options.write_png:
            png_path = output_directory / f"{stem}.png"
            representative.save(png_path, "PNG")
            result.written_files.append(png_path)
            result.png_count += 1

        if options.all_sizes:
            for entry in container.entries:
                try:
                    image = open_entry(entry)
                except Exception as error:  # noqa: BLE001
                    result.warnings.append(
                        f"{stem} ({entry.label}): could not open image ({error})"
                    )
                    continue
                size_path = output_directory / f"{stem}@{entry.label}.png"
                image.save(size_path, "PNG")
                result.written_files.append(size_path)
                result.png_count += 1

    ordered = [representatives[i] for i in ani.sequence if i in representatives]
    ordered_durations = [
        step.duration_ms for step in ani.steps if step.frame_index in representatives
    ]

    if options.write_sequence:
        for step_index, frame_index in enumerate(ani.sequence):
            image = representatives.get(frame_index)
            if image is None:
                continue
            step_path = output_directory / f"step_{step_index:03d}.png"
            image.save(step_path, "PNG")
            result.written_files.append(step_path)
            result.png_count += 1

    animation_outputs = [
        (filename, saver)
        for enabled, filename, saver in (
            (options.write_gif, _GIF_FILENAME, save_gif),
            (options.write_apng, _APNG_FILENAME, save_apng),
            (options.write_webp, _WEBP_FILENAME, save_webp),
        )
        if enabled
    ]

    if animation_outputs:
        if not ordered:
            result.warnings.append("No frames usable for animation.")
        else:
            # Normalize once; the savers' own normalization pass then
            # reuses these frames instead of re-converting per format.
            frames = normalize_canvas(ordered)
            for filename, saver in animation_outputs:
                animation_path = output_directory / filename
                saver(frames, ordered_durations, animation_path)
                result.written_files.append(animation_path)

    if options.write_metadata:
        metadata_path = output_directory / _METADATA_FILENAME
        metadata_path.write_text(
            json.dumps(_build_metadata(result, frame_metadata), ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )
        result.written_files.append(metadata_path)

    return result
