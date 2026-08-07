"""Minimal RIFF container parser.

ANI files use the RIFF/ACON format, so this module only handles generic
RIFF chunk traversal.
"""

from __future__ import annotations

import struct
from collections.abc import Iterator
from dataclasses import dataclass

__all__ = ["Chunk", "RiffError", "iter_chunks", "walk"]

_LIST_LIKE = (b"RIFF", b"LIST")


class RiffError(ValueError):
    """Raised when the RIFF structure is corrupt."""


@dataclass(frozen=True)
class Chunk:
    """Location of a single RIFF chunk.

    Attributes:
        identifier: 4-byte chunk ID (e.g. ``b"icon"``).
        start: Payload start offset.
        end: Payload end offset (exclusive).
        list_type: Form type for LIST/RIFF chunks (e.g. ``b"ACON"``), otherwise None.
    """

    identifier: bytes
    start: int
    end: int
    list_type: bytes | None = None

    @property
    def size(self) -> int:
        return self.end - self.start

    def payload(self, data: bytes) -> bytes:
        return data[self.start : self.end]


def iter_chunks(data: bytes, start: int, end: int) -> Iterator[Chunk]:
    """Iterate over the chunks in ``[start, end)`` at a single nesting level."""
    position = start

    while position + 8 <= end:
        identifier = data[position : position + 4]
        (size,) = struct.unpack_from("<I", data, position + 4)

        payload_start = position + 8
        payload_end = payload_start + size

        if payload_end > end or payload_end > len(data):
            raise RiffError(
                f"Invalid RIFF chunk: id={identifier!r}, offset={position}, size={size}"
            )

        list_type: bytes | None = None
        if identifier in _LIST_LIKE:
            if size < 4:
                raise RiffError(f"LIST/RIFF chunk is too short: offset={position}, size={size}")
            list_type = data[payload_start : payload_start + 4]

        yield Chunk(identifier, payload_start, payload_end, list_type)

        # RIFF chunks are padded to 2-byte boundaries
        position = payload_end + (size & 1)


def walk(data: bytes, start: int, end: int) -> Iterator[Chunk]:
    """Recursively walk ``[start, end)``, yielding nested chunks as well."""
    for chunk in iter_chunks(data, start, end):
        yield chunk
        if chunk.list_type is not None:
            yield from walk(data, chunk.start + 4, chunk.end)
