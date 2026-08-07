from __future__ import annotations

import pytest

from ani_extract.icons import IconError, open_entry, parse_icon_container
from conftest import make_cur, make_ico


def test_ico_container_lists_every_size() -> None:
    container = parse_icon_container(make_ico((255, 0, 0, 255)))

    assert container.kind == "ico"
    assert container.extension == ".ico"
    assert sorted((entry.width, entry.height) for entry in container.entries) == [
        (16, 16),
        (32, 32),
    ]


def test_cur_container_reports_hotspot() -> None:
    container = parse_icon_container(make_cur((0, 255, 0, 255), hotspot=(4, 5)))

    assert container.kind == "cur"
    assert container.extension == ".cur"
    assert all(entry.hotspot == (4, 5) for entry in container.entries)


def test_largest_entry_is_selected() -> None:
    container = parse_icon_container(make_cur((0, 0, 255, 255)))

    assert (container.largest.width, container.largest.height) == (32, 32)


def test_open_entry_returns_rgba_image_of_expected_size() -> None:
    container = parse_icon_container(make_cur((255, 0, 0, 255)))

    for entry in container.entries:
        image = open_entry(entry)
        assert image.mode == "RGBA"
        assert image.size == (entry.width, entry.height)


def test_open_entry_preserves_color() -> None:
    container = parse_icon_container(make_cur((255, 0, 0, 255)))
    image = open_entry(container.largest)

    assert image.getpixel((0, 0)) == (255, 0, 0, 255)


def test_entry_label() -> None:
    container = parse_icon_container(make_ico((255, 0, 0, 255)))

    assert container.largest.label == "32x32-32bpp"


@pytest.mark.parametrize("data", [b"", b"\x00" * 6, b"\x01\x00\x01\x00\x01\x00"])
def test_invalid_container_raises(data: bytes) -> None:
    with pytest.raises(IconError):
        parse_icon_container(data)
