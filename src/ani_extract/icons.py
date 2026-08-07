"""Parsing ICO / CUR containers and converting them into a form Pillow can open.

Some versions of Pillow's CUR plugin cannot handle multiple resolutions,
so we read the directory entries ourselves and repack each one as a
single-entry ICO before handing it to Pillow.
"""

from __future__ import annotations

import io
import struct
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from PIL import Image

__all__ = ["IconContainer", "IconEntry", "IconError", "open_entry", "parse_icon_container"]

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

_ICONDIR = struct.Struct("<HHH")
_ICONDIRENTRY = struct.Struct("<BBBBHHII")

_TYPE_NAMES = {1: "ico", 2: "cur"}


class IconError(ValueError):
    """Raised when the data cannot be interpreted as an ICO/CUR file."""


@dataclass(frozen=True)
class IconEntry:
    """A single image inside an ICO/CUR file."""

    width: int
    height: int
    bit_count: int
    hotspot: tuple[int, int] | None
    payload: bytes

    @property
    def label(self) -> str:
        return f"{self.width}x{self.height}-{self.bit_count or 0}bpp"

    def to_ico_bytes(self) -> bytes:
        """Build a single-image ICO containing only this entry."""
        planes, bit_count = _planes_and_bit_count(self.payload)
        header = _ICONDIR.pack(0, 1, 1)
        entry = _ICONDIRENTRY.pack(
            self.width if self.width < 256 else 0,
            self.height if self.height < 256 else 0,
            0,
            0,
            planes,
            bit_count,
            len(self.payload),
            _ICONDIR.size + _ICONDIRENTRY.size,
        )
        return header + entry + self.payload


@dataclass(frozen=True)
class IconContainer:
    """A single ICO/CUR file."""

    kind: str
    entries: list[IconEntry]

    @property
    def extension(self) -> str:
        return f".{self.kind}" if self.kind in _TYPE_NAMES.values() else ".bin"

    @property
    def largest(self) -> IconEntry:
        return max(self.entries, key=lambda entry: (entry.width * entry.height, entry.bit_count))


def _dimensions_from_payload(payload: bytes) -> tuple[int, int] | None:
    if payload[:8] == _PNG_SIGNATURE and len(payload) >= 24:
        width, height = struct.unpack_from(">II", payload, 16)
        return int(width), int(height)

    if len(payload) >= 16:
        (header_size,) = struct.unpack_from("<I", payload, 0)
        if header_size >= 40:
            width, height = struct.unpack_from("<ii", payload, 4)
            # Icon DIBs store double the height to account for the XOR/AND masks
            return int(width), int(abs(height) // 2)

    return None


def _planes_and_bit_count(payload: bytes) -> tuple[int, int]:
    if payload[:8] == _PNG_SIGNATURE:
        return 1, 32

    if len(payload) >= 16:
        (header_size,) = struct.unpack_from("<I", payload, 0)
        if header_size >= 40:
            planes, bit_count = struct.unpack_from("<HH", payload, 12)
            return int(planes), int(bit_count)

    return 0, 0


def parse_icon_container(data: bytes) -> IconContainer:
    """Extract the directory entries from ICO/CUR bytes.

    Raises:
        IconError: If the header is invalid or there are no entries.
    """
    if len(data) < _ICONDIR.size:
        raise IconError("Cannot read the ICO/CUR header.")

    reserved, image_type, count = _ICONDIR.unpack_from(data, 0)

    if reserved != 0 or image_type not in _TYPE_NAMES or count == 0:
        raise IconError(
            f"Invalid ICO/CUR header: reserved={reserved}, type={image_type}, count={count}"
        )

    entries: list[IconEntry] = []

    for index in range(count):
        offset = _ICONDIR.size + index * _ICONDIRENTRY.size
        if offset + _ICONDIRENTRY.size > len(data):
            break

        (
            raw_width,
            raw_height,
            _color_count,
            _reserved,
            field_a,
            field_b,
            size,
            payload_offset,
        ) = _ICONDIRENTRY.unpack_from(data, offset)

        payload_end = payload_offset + size
        if size == 0 or payload_end > len(data):
            continue

        payload = data[payload_offset:payload_end]

        # In CUR files, the entry's planes/bitCount fields hold the hotspot coordinates
        hotspot = (field_a, field_b) if image_type == 2 else None
        _, bit_count = _planes_and_bit_count(payload)

        dimensions = _dimensions_from_payload(payload)
        width = dimensions[0] if dimensions else (raw_width or 256)
        height = dimensions[1] if dimensions else (raw_height or 256)

        entries.append(
            IconEntry(
                width=width,
                height=height,
                bit_count=bit_count,
                hotspot=hotspot,
                payload=payload,
            )
        )

    if not entries:
        raise IconError("No valid image entries in the ICO/CUR file.")

    return IconContainer(kind=_TYPE_NAMES[image_type], entries=entries)


def open_entry(entry: IconEntry) -> Image.Image:
    """Open the entry as an RGBA Pillow image."""
    from PIL import Image

    with Image.open(io.BytesIO(entry.to_ico_bytes())) as image:
        image.load()
        return image.convert("RGBA")
