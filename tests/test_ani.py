from __future__ import annotations

import pytest

from ani_extract.ani import AniError, parse_ani
from conftest import build_ani, make_cur


def test_parses_frames_sequence_and_rates(ani_bytes: bytes) -> None:
    ani = parse_ani(ani_bytes)

    assert len(ani.frames) == 3
    assert ani.sequence == [0, 1, 2, 1]
    assert ani.rates == [6, 3, 12, 3]
    assert ani.title == "Test Cursor"
    assert ani.author == "Chanya"


def test_header_flags(ani_bytes: bytes) -> None:
    header = parse_ani(ani_bytes).header

    assert header is not None
    assert header.frame_count == 3
    assert header.step_count == 4
    assert header.contains_icons is True
    assert header.has_sequence is True


def test_durations_use_jiffies(ani_bytes: bytes) -> None:
    ani = parse_ani(ani_bytes)

    # 6 jiffies == 100ms, 3 jiffies == 50ms, 12 jiffies == 200ms
    assert ani.durations_ms == [100, 50, 200, 50]
    assert [step.frame_index for step in ani.steps] == [0, 1, 2, 1]


def test_sequence_defaults_to_frame_order() -> None:
    data = build_ani([make_cur((255, 0, 0, 255)), make_cur((0, 255, 0, 255))])
    ani = parse_ani(data)

    assert ani.sequence == [0, 1]
    assert ani.rates == [6, 6]


def test_out_of_range_sequence_entries_are_dropped() -> None:
    data = build_ani([make_cur((255, 0, 0, 255))], sequence=[0, 7])
    ani = parse_ani(data)

    assert ani.sequence == [0]
    assert len(ani.rates) == 1


def test_short_rate_list_is_padded_with_default() -> None:
    data = build_ani(
        [make_cur((255, 0, 0, 255)), make_cur((0, 255, 0, 255))],
        sequence=[0, 1, 0],
        rates=[3],
        display_rate=12,
    )
    ani = parse_ani(data)

    assert ani.rates == [3, 12, 12]


def test_zero_rates_fall_back_to_default() -> None:
    data = build_ani(
        [make_cur((255, 0, 0, 255)), make_cur((0, 255, 0, 255))],
        sequence=[0, 1],
        rates=[0, 3],
        display_rate=12,
    )
    ani = parse_ani(data)

    assert ani.rates == [12, 3]


def test_missing_anih_still_parses() -> None:
    data = build_ani([make_cur((255, 0, 0, 255))], include_anih=False)
    ani = parse_ani(data)

    assert ani.header is None
    assert ani.sequence == [0]


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"NOTRIFF" + b"\x00" * 32,
        b"RIFF" + b"\x00\x00\x00\x00" + b"WAVE",
    ],
)
def test_invalid_input_raises(data: bytes) -> None:
    with pytest.raises(AniError):
        parse_ani(data)


def test_ani_without_icon_frames_raises() -> None:
    data = build_ani([])

    with pytest.raises(AniError):
        parse_ani(data)
