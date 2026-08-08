from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from ani_extract.animation import save_apng, save_gif, save_webp


def _frame(color: tuple[int, int, int, int], size: tuple[int, int] = (8, 8)) -> Image.Image:
    return Image.new("RGBA", size, color)


def test_webp_preserves_rgb_of_fully_transparent_pixels(tmp_path: Path) -> None:
    first = _frame((10, 20, 30, 255))
    first.putpixel((0, 0), (11, 22, 33, 0))
    path = tmp_path / "animation.webp"

    save_webp([first, _frame((40, 50, 60, 255))], [100, 100], path)

    with Image.open(path) as image:
        image.seek(0)
        assert image.convert("RGBA").getpixel((0, 0)) == (11, 22, 33, 0)


def test_webp_keeps_consecutive_duplicate_frames(tmp_path: Path) -> None:
    red = _frame((255, 0, 0, 255))
    path = tmp_path / "animation.webp"

    save_webp([red, red.copy(), _frame((0, 0, 255, 255))], [100, 150, 200], path)

    with Image.open(path) as image:
        assert image.n_frames == 3


def test_webp_durations_round_trip(tmp_path: Path) -> None:
    colors = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255)]
    path = tmp_path / "animation.webp"

    save_webp([_frame(color) for color in colors], [100, 150, 200], path)

    with Image.open(path) as image:
        durations = []
        for index in range(image.n_frames):
            image.seek(index)
            image.load()
            durations.append(image.info["duration"])

    assert durations == [100, 150, 200]


def test_webp_clamps_oversized_durations(tmp_path: Path) -> None:
    path = tmp_path / "animation.webp"

    save_webp([_frame((255, 0, 0, 255)), _frame((0, 0, 255, 255))], [2**32, 100], path)

    with Image.open(path) as image:
        image.seek(0)
        image.load()
        assert image.info["duration"] == 0xFFFFFF


def test_webp_single_frame_keeps_pixels(tmp_path: Path) -> None:
    path = tmp_path / "animation.webp"

    save_webp([_frame((1, 2, 3, 255))], [500], path)

    with Image.open(path) as image:
        assert image.size == (8, 8)
        assert image.convert("RGBA").getpixel((0, 0)) == (1, 2, 3, 255)


def test_gif_clamps_oversized_durations(tmp_path: Path) -> None:
    path = tmp_path / "animation.gif"

    save_gif([_frame((255, 0, 0, 255)), _frame((0, 0, 255, 255))], [10**7, 100], path)

    with Image.open(path) as image:
        image.seek(0)
        image.load()
        assert image.info["duration"] == 655_350


def test_apng_clamps_oversized_durations(tmp_path: Path) -> None:
    path = tmp_path / "animation.png"

    save_apng([_frame((255, 0, 0, 255)), _frame((0, 0, 255, 255))], [10**11, 100], path)

    with Image.open(path) as image:
        image.seek(0)
        image.load()
        assert image.info["duration"] == 65_535_000


@pytest.mark.parametrize("saver", [save_gif, save_apng, save_webp])
def test_mismatched_durations_raise(saver, tmp_path: Path) -> None:
    frames = [_frame((255, 0, 0, 255)), _frame((0, 0, 255, 255))]

    with pytest.raises(ValueError):
        saver(frames, [100], tmp_path / "animation.out")


@pytest.mark.parametrize("saver", [save_gif, save_apng, save_webp])
def test_empty_frames_raise(saver, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        saver([], [], tmp_path / "animation.out")
