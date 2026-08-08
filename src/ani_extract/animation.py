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

#: Frame-duration ceilings imposed by each container format: GIF stores
#: uint16 centiseconds, APNG at best uint16 whole seconds (fcTL delay
#: fraction), and the WebP ANMF duration is a 24-bit millisecond field.
#: Larger values make Pillow raise (struct.error / ValueError) mid-write.
_GIF_MAX_DURATION_MS = 655_350
_APNG_MAX_DURATION_MS = 65_535_000
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
            normalized.append(image if image.mode == "RGBA" else image.convert("RGBA"))
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


def _prepare_frames(images: list[Image.Image], durations_ms: list[int]) -> list[Image.Image]:
    if not images:
        raise ValueError("No frames to write.")
    if len(durations_ms) != len(images):
        raise ValueError(f"Expected {len(images)} durations, got {len(durations_ms)}.")
    return normalize_canvas(images)


def _clamp_durations(durations_ms: list[int], maximum: int) -> list[int]:
    return [min(max(int(duration), 0), maximum) for duration in durations_ms]


def _save_pillow_animation(
    frames: list[Image.Image],
    durations_ms: list[int],
    path: Path,
    image_format: str,
    **options: object,
) -> None:
    frames[0].save(
        path,
        format=image_format,
        save_all=True,
        append_images=frames[1:],
        duration=durations_ms,
        loop=0,
        **options,
    )


def save_gif(images: list[Image.Image], durations_ms: list[int], path: Path) -> None:
    """Write an animated GIF."""
    frames = [_to_palette_frame(image) for image in _prepare_frames(images, durations_ms)]
    _save_pillow_animation(
        frames,
        _clamp_durations(durations_ms, _GIF_MAX_DURATION_MS),
        path,
        "GIF",
        disposal=2,
        transparency=_TRANSPARENT_INDEX,
        optimize=False,
    )


def save_apng(images: list[Image.Image], durations_ms: list[int], path: Path) -> None:
    """Write an animated PNG (APNG)."""
    frames = _prepare_frames(images, durations_ms)
    _save_pillow_animation(
        frames,
        _clamp_durations(durations_ms, _APNG_MAX_DURATION_MS),
        path,
        "PNG",
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

    frames = _prepare_frames(images, durations_ms)
    width, height = frames[0].size

    has_alpha = any(frame.getextrema()[3][0] < 255 for frame in frames)
    flags = _VP8X_HAS_ANIMATION | (_VP8X_HAS_ALPHA if has_alpha else 0)

    body = _webp_chunk(
        b"VP8X",
        struct.pack("<B3x", flags) + _uint24(width - 1) + _uint24(height - 1),
    )
    body += _webp_chunk(b"ANIM", struct.pack("<IH", 0, 0))

    durations = _clamp_durations(durations_ms, _WEBP_MAX_DURATION_MS)
    for frame, duration in zip(frames, durations, strict=True):
        header = (
            _uint24(0)  # frame X / 2
            + _uint24(0)  # frame Y / 2
            + _uint24(width - 1)
            + _uint24(height - 1)
            + _uint24(duration)
            + struct.pack("<B", _ANMF_NO_BLEND)
        )
        body += _webp_chunk(b"ANMF", header + _encode_lossless_frame(frame))

    path.write_bytes(b"RIFF" + struct.pack("<I", len(body) + 4) + b"WEBP" + body)
