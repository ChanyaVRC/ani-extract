"""Write animations (GIF / APNG) from extracted frames."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from PIL import Image

__all__ = ["normalize_canvas", "save_apng", "save_gif"]

_TRANSPARENT_INDEX = 255


def normalize_canvas(images: list[Image.Image]) -> list[Image.Image]:
    """Align all frames onto same-sized transparent canvases, anchored top-left."""
    from PIL import Image as PillowImage

    if not images:
        return []

    width = max(image.width for image in images)
    height = max(image.height for image in images)

    normalized: list[Image.Image] = []
    for image in images:
        if image.size == (width, height):
            normalized.append(image.convert("RGBA"))
            continue
        canvas = PillowImage.new("RGBA", (width, height), (0, 0, 0, 0))
        canvas.paste(image.convert("RGBA"), (0, 0))
        normalized.append(canvas)

    return normalized


def _to_palette_frame(image: Image.Image) -> Image.Image:
    """Convert to a palette image for GIF, reserving one color for transparency."""
    from PIL import Image as PillowImage

    alpha = image.getchannel("A")
    palette_image = image.convert("RGB").convert(
        "P", palette=PillowImage.Palette.ADAPTIVE, colors=_TRANSPARENT_INDEX
    )
    transparency_mask = alpha.point(lambda value: 255 if value < 128 else 0)
    palette_image.paste(_TRANSPARENT_INDEX, transparency_mask)
    return palette_image


def save_gif(images: list[Image.Image], durations_ms: list[int], path: Path) -> None:
    """Write an animated GIF."""
    if not images:
        raise ValueError("No frames to write.")

    frames = [_to_palette_frame(image) for image in normalize_canvas(images)]

    frames[0].save(
        path,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=list(durations_ms),
        loop=0,
        disposal=2,
        transparency=_TRANSPARENT_INDEX,
        optimize=False,
    )


def save_apng(images: list[Image.Image], durations_ms: list[int], path: Path) -> None:
    """Write an animated PNG (APNG)."""
    if not images:
        raise ValueError("No frames to write.")

    frames = normalize_canvas(images)

    frames[0].save(
        path,
        format="PNG",
        save_all=True,
        append_images=frames[1:],
        duration=list(durations_ms),
        loop=0,
        disposal=1,
    )
