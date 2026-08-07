"""Synthetic ANI / ICO / CUR builders for tests."""

from __future__ import annotations

import struct
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

ANIH_FLAG_ICON = 0x1
ANIH_FLAG_SEQUENCE = 0x2

DEFAULT_SIZES = [(16, 16), (32, 32)]
DEFAULT_COLORS = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255)]


def make_ico(color: tuple[int, int, int, int], sizes: list[tuple[int, int]] | None = None) -> bytes:
    """Build a solid-color, multi-resolution ICO."""
    sizes = sizes or DEFAULT_SIZES
    largest = max(sizes)
    image = Image.new("RGBA", largest, color)
    buffer = BytesIO()
    image.save(buffer, format="ICO", sizes=sizes)
    return buffer.getvalue()


def make_cur(
    color: tuple[int, int, int, int],
    hotspot: tuple[int, int] = (0, 0),
    sizes: list[tuple[int, int]] | None = None,
) -> bytes:
    """Rewrite an ICO as a CUR (type=2, hotspot in the entry's planes/bpp fields)."""
    data = bytearray(make_ico(color, sizes))
    struct.pack_into("<H", data, 2, 2)

    (count,) = struct.unpack_from("<H", data, 4)
    for index in range(count):
        offset = 6 + index * 16
        struct.pack_into("<HH", data, offset + 4, hotspot[0], hotspot[1])

    return bytes(data)


def chunk(identifier: bytes, payload: bytes) -> bytes:
    """Build a RIFF chunk, padding to a 2-byte boundary if needed."""
    data = identifier + struct.pack("<I", len(payload)) + payload
    if len(payload) % 2:
        data += b"\x00"
    return data


def list_chunk(list_type: bytes, payload: bytes) -> bytes:
    return chunk(b"LIST", list_type + payload)


def build_ani(
    frames: list[bytes],
    *,
    sequence: list[int] | None = None,
    rates: list[int] | None = None,
    display_rate: int = 6,
    title: str | None = None,
    author: str | None = None,
    include_anih: bool = True,
    contains_icons: bool = True,
) -> bytes:
    """Assemble a synthetic ANI (RIFF/ACON) file."""
    body = b"ACON"

    if include_anih:
        flags = ANIH_FLAG_ICON if contains_icons else 0
        if sequence is not None:
            flags |= ANIH_FLAG_SEQUENCE

        body += chunk(
            b"anih",
            struct.pack(
                "<9I",
                36,
                len(frames),
                len(sequence) if sequence is not None else len(frames),
                0,
                0,
                0,
                0,
                display_rate,
                flags,
            ),
        )

    if title is not None or author is not None:
        info = b""
        if title is not None:
            info += chunk(b"INAM", title.encode("cp1252") + b"\x00")
        if author is not None:
            info += chunk(b"IART", author.encode("cp1252") + b"\x00")
        body += list_chunk(b"INFO", info)

    if sequence is not None:
        body += chunk(b"seq ", struct.pack(f"<{len(sequence)}I", *sequence))

    if rates is not None:
        body += chunk(b"rate", struct.pack(f"<{len(rates)}I", *rates))

    body += list_chunk(b"fram", b"".join(chunk(b"icon", frame) for frame in frames))

    return b"RIFF" + struct.pack("<I", len(body)) + body


@pytest.fixture
def cur_frames() -> list[bytes]:
    return [make_cur(color, hotspot=(index, index)) for index, color in enumerate(DEFAULT_COLORS)]


@pytest.fixture
def ani_bytes(cur_frames: list[bytes]) -> bytes:
    return build_ani(
        cur_frames,
        sequence=[0, 1, 2, 1],
        rates=[6, 3, 12, 3],
        title="Test Cursor",
        author="Chanya",
    )


@pytest.fixture
def ani_path(tmp_path: Path, ani_bytes: bytes) -> Path:
    path = tmp_path / "sample.ani"
    path.write_bytes(ani_bytes)
    return path
