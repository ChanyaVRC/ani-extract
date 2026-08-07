"""Parser for Windows animated cursors (.ani / RIFF-ACON)."""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

from .riff import RiffError, walk

__all__ = [
    "JIFFY_MS",
    "AniError",
    "AniFile",
    "AniHeader",
    "Step",
    "parse_ani",
]

#: The ANI time unit (jiffy) is one video frame, 1/60 second.
JIFFY_MS = 1000.0 / 60.0

_FLAG_ICON = 0x1
_FLAG_SEQUENCE = 0x2

_ANIH_STRUCT = struct.Struct("<9I")


class AniError(ValueError):
    """Raised when the data cannot be interpreted as an ANI file."""


@dataclass(frozen=True)
class AniHeader:
    """Contents of the ``anih`` chunk."""

    frame_count: int
    step_count: int
    width: int
    height: int
    bit_count: int
    plane_count: int
    display_rate: int
    flags: int

    @property
    def contains_icons(self) -> bool:
        """Whether frames are stored as ICO/CUR (as opposed to raw DIBs)."""
        return bool(self.flags & _FLAG_ICON)

    @property
    def has_sequence(self) -> bool:
        return bool(self.flags & _FLAG_SEQUENCE)


@dataclass(frozen=True)
class Step:
    """Information for a single playback step."""

    frame_index: int
    jiffies: int

    @property
    def duration_ms(self) -> int:
        return max(10, round(self.jiffies * JIFFY_MS))


@dataclass(frozen=True)
class AniFile:
    """A parsed ANI file."""

    frames: list[bytes]
    header: AniHeader | None = None
    sequence: list[int] = field(default_factory=list)
    rates: list[int] = field(default_factory=list)
    title: str | None = None
    author: str | None = None

    @property
    def steps(self) -> list[Step]:
        return [
            Step(frame_index, jiffies)
            for frame_index, jiffies in zip(self.sequence, self.rates, strict=False)
        ]

    @property
    def durations_ms(self) -> list[int]:
        return [step.duration_ms for step in self.steps]


def _parse_anih(payload: bytes) -> AniHeader:
    if len(payload) < _ANIH_STRUCT.size:
        raise AniError(f"anih chunk is too short: {len(payload)} bytes")

    (
        _cb_size,
        frame_count,
        step_count,
        width,
        height,
        bit_count,
        plane_count,
        display_rate,
        flags,
    ) = _ANIH_STRUCT.unpack_from(payload, 0)

    return AniHeader(
        frame_count=frame_count,
        step_count=step_count,
        width=width,
        height=height,
        bit_count=bit_count,
        plane_count=plane_count,
        display_rate=display_rate,
        flags=flags,
    )


def _parse_uint32_array(payload: bytes) -> list[int]:
    count = len(payload) // 4
    return list(struct.unpack_from(f"<{count}I", payload, 0)) if count else []


def _decode_text(payload: bytes) -> str:
    return payload.split(b"\x00", 1)[0].decode("cp1252", errors="replace").strip()


def parse_ani(data: bytes) -> AniFile:
    """Parse the bytes of an ANI file.

    Args:
        data: The full contents of a ``.ani`` file.

    Returns:
        The parsed :class:`AniFile`.

    Raises:
        AniError: If the data is not RIFF/ACON or contains no icon frames.
    """
    if len(data) < 12:
        raise AniError("File is too small to be an ANI file.")

    if data[0:4] != b"RIFF":
        raise AniError("Not a RIFF file.")

    if data[8:12] != b"ACON":
        raise AniError("Not a Windows ANI (ACON) file.")

    (riff_size,) = struct.unpack_from("<I", data, 4)
    riff_end = min(8 + riff_size, len(data))

    frames: list[bytes] = []
    header: AniHeader | None = None
    sequence: list[int] | None = None
    rates: list[int] | None = None
    title: str | None = None
    author: str | None = None

    try:
        chunks = list(walk(data, 12, riff_end))
    except RiffError as error:
        raise AniError(str(error)) from error

    for chunk in chunks:
        identifier = chunk.identifier
        if identifier == b"icon":
            frames.append(chunk.payload(data))
        elif identifier == b"anih":
            header = _parse_anih(chunk.payload(data))
        elif identifier == b"seq ":
            sequence = _parse_uint32_array(chunk.payload(data))
        elif identifier == b"rate":
            rates = _parse_uint32_array(chunk.payload(data))
        elif identifier == b"INAM":
            title = _decode_text(chunk.payload(data))
        elif identifier == b"IART":
            author = _decode_text(chunk.payload(data))

    if not frames:
        raise AniError("No icon frames found in the ANI file.")

    default_rate = header.display_rate if header and header.display_rate > 0 else 6
    step_count = header.step_count if header and header.step_count > 0 else len(frames)

    if not sequence:
        sequence = list(range(min(step_count, len(frames))))

    # Drop out-of-range frame indices; they indicate corrupt data
    sequence = [index for index in sequence if 0 <= index < len(frames)]
    if not sequence:
        sequence = list(range(len(frames)))

    if not rates:
        rates = [default_rate] * len(sequence)
    elif len(rates) < len(sequence):
        rates = rates + [default_rate] * (len(sequence) - len(rates))
    else:
        rates = rates[: len(sequence)]

    rates = [rate if rate > 0 else default_rate for rate in rates]

    return AniFile(
        frames=frames,
        header=header,
        sequence=sequence,
        rates=rates,
        title=title or None,
        author=author or None,
    )
