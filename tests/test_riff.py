from __future__ import annotations

import struct

import pytest

from ani_extract.riff import RiffError, iter_chunks, walk
from conftest import build_ani, chunk, make_cur


def test_walk_finds_nested_icon_chunks() -> None:
    data = build_ani([make_cur((255, 0, 0, 255))])
    identifiers = [c.identifier for c in walk(data, 12, len(data))]

    assert b"anih" in identifiers
    assert identifiers.count(b"icon") == 1
    assert b"LIST" in identifiers


def test_list_type_is_exposed() -> None:
    data = build_ani([make_cur((0, 0, 255, 255))])
    list_types = [c.list_type for c in walk(data, 12, len(data)) if c.list_type]

    assert b"fram" in list_types


def test_odd_sized_chunks_are_padded() -> None:
    data = chunk(b"aaaa", b"xyz") + chunk(b"bbbb", b"1234")
    chunks = list(iter_chunks(data, 0, len(data)))

    assert [c.identifier for c in chunks] == [b"aaaa", b"bbbb"]
    assert chunks[0].payload(data) == b"xyz"
    assert chunks[1].payload(data) == b"1234"


def test_oversized_chunk_raises() -> None:
    data = b"aaaa" + struct.pack("<I", 999) + b"xy"

    with pytest.raises(RiffError):
        list(iter_chunks(data, 0, len(data)))


def test_short_list_chunk_raises() -> None:
    data = b"LIST" + struct.pack("<I", 2) + b"ab"

    with pytest.raises(RiffError):
        list(iter_chunks(data, 0, len(data)))
