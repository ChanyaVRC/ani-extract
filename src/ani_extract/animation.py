"""Write animations (GIF / APNG / WebP) from extracted frames."""

from __future__ import annotations

import io
import struct
from pathlib import Path
from typing import TYPE_CHECKING

from .riff import iter_chunks

if TYPE_CHECKING:  # pragma: no cover
    from PIL import Image

__all__ = ["normalize_canvas", "save_apng", "save_gif", "save_webp"]

_TRANSPARENT_INDEX = 255

#: ANMF frame duration is a 24-bit field (WebP container specification).
_WEBP_MAX_DURATION_MS = 0xFFFFFF

_VP8X_HAS_ANIMATION = 0x02
_VP8X_HAS_ALPHA = 0x10
_ANMF_NO_BLEND = 0x02

_WEBP_BITSTREAM_CHUNKS = (b"ALPH", b"VP8 ", b"VP8L")


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


def _webp_chunk(fourcc: bytes, payload: bytes) -> bytes:
    data = fourcc + struct.pack("<I", len(payload)) + payload
    if len(payload) % 2:
        data += b"\x00"
    return data


def _uint24(value: int) -> bytes:
    return struct.pack("<I", value)[:3]


def _encode_lossless_frame(image: Image.Image) -> bytes:
    """Encode one frame as a still lossless WebP and return its bitstream chunks."""
    buffer = io.BytesIO()
    image.save(buffer, format="WEBP", lossless=True, exact=True, method=4)
    data = buffer.getvalue()

    return b"".join(
        _webp_chunk(chunk.identifier, chunk.payload(data))
        for chunk in iter_chunks(data, 12, len(data))
        if chunk.identifier in _WEBP_BITSTREAM_CHUNKS
    )


def save_webp(images: list[Image.Image], durations_ms: list[int], path: Path) -> None:
    """Write an animated WebP (exact lossless, one frame per playback step).

    Pillow's animated WebP encoder does not expose libwebp's ``exact`` flag,
    so it discards the RGB values of fully transparent pixels and merges
    consecutive identical frames. To keep the output truly lossless, each
    frame is encoded through the still-image path (which does support
    ``exact``) and the animation container (VP8X + ANIM + ANMF) is assembled
    here, following the WebP container specification.
    """
    from PIL import features

    if not features.check("webp"):
        raise ValueError("Pillow was built without WebP support.")

    if not images:
        raise ValueError("No frames to write.")

    if len(durations_ms) != len(images):
        raise ValueError(f"Expected {len(images)} durations, got {len(durations_ms)}.")

    frames = normalize_canvas(images)
    width, height = frames[0].size

    has_alpha = any(frame.getextrema()[3][0] < 255 for frame in frames)
    flags = _VP8X_HAS_ANIMATION | (_VP8X_HAS_ALPHA if has_alpha else 0)

    body = _webp_chunk(
        b"VP8X",
        struct.pack("<B3x", flags) + _uint24(width - 1) + _uint24(height - 1),
    )
    body += _webp_chunk(b"ANIM", struct.pack("<IH", 0, 0))

    for frame, duration in zip(frames, durations_ms, strict=True):
        clamped = min(max(int(duration), 0), _WEBP_MAX_DURATION_MS)
        header = (
            _uint24(0)  # frame X / 2
            + _uint24(0)  # frame Y / 2
            + _uint24(width - 1)
            + _uint24(height - 1)
            + _uint24(clamped)
            + struct.pack("<B", _ANMF_NO_BLEND)
        )
        body += _webp_chunk(b"ANMF", header + _encode_lossless_frame(frame))

    path.write_bytes(b"RIFF" + struct.pack("<I", len(body) + 4) + b"WEBP" + body)
