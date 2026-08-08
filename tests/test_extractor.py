from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from ani_extract.extractor import ExtractOptions, extract


def test_default_extraction_writes_cur_and_png(ani_path: Path, tmp_path: Path) -> None:
    output = tmp_path / "out"
    result = extract(ani_path, output, ExtractOptions())

    assert result.frame_count == 3
    assert result.step_count == 4
    assert result.png_count == 3
    assert not result.warnings

    for index in range(3):
        assert (output / f"frame_{index:03d}.cur").is_file()
        assert (output / f"frame_{index:03d}.png").is_file()

    assert (output / "metadata.json").is_file()


def test_representative_png_uses_largest_size(ani_path: Path, tmp_path: Path) -> None:
    output = tmp_path / "out"
    extract(ani_path, output, ExtractOptions())

    with Image.open(output / "frame_000.png") as image:
        assert image.size == (32, 32)


def test_all_sizes_writes_every_resolution(ani_path: Path, tmp_path: Path) -> None:
    output = tmp_path / "out"
    extract(ani_path, output, ExtractOptions(all_sizes=True))

    assert (output / "frame_000@16x16-32bpp.png").is_file()
    assert (output / "frame_000@32x32-32bpp.png").is_file()

    with Image.open(output / "frame_000@16x16-32bpp.png") as image:
        assert image.size == (16, 16)


def test_sequence_output_follows_seq_chunk(ani_path: Path, tmp_path: Path) -> None:
    output = tmp_path / "out"
    extract(ani_path, output, ExtractOptions(write_sequence=True))

    steps = sorted(output.glob("step_*.png"))
    assert len(steps) == 4

    # Playback order is 0 -> 1 -> 2 -> 1, so step_001 and step_003 are the same frame
    assert (output / "step_001.png").read_bytes() == (output / "step_003.png").read_bytes()


def test_gif_uses_sequence_and_durations(ani_path: Path, tmp_path: Path) -> None:
    output = tmp_path / "out"
    extract(ani_path, output, ExtractOptions(write_gif=True))

    gif_path = output / "animation.gif"
    assert gif_path.is_file()

    with Image.open(gif_path) as image:
        assert image.n_frames == 4
        assert image.info["duration"] == 100


def test_apng_is_written(ani_path: Path, tmp_path: Path) -> None:
    output = tmp_path / "out"
    extract(ani_path, output, ExtractOptions(write_apng=True))

    apng_path = output / "animation.png"
    assert apng_path.is_file()

    with Image.open(apng_path) as image:
        assert image.n_frames == 4


def test_webp_is_written(ani_path: Path, tmp_path: Path) -> None:
    output = tmp_path / "out"
    extract(ani_path, output, ExtractOptions(write_webp=True))

    webp_path = output / "animation.webp"
    assert webp_path.is_file()

    with Image.open(webp_path) as image:
        assert image.n_frames == 4


def test_metadata_contents(ani_path: Path, tmp_path: Path) -> None:
    output = tmp_path / "out"
    extract(ani_path, output, ExtractOptions())

    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))

    assert metadata["title"] == "Test Cursor"
    assert metadata["author"] == "Chanya"
    assert metadata["sequence"] == [0, 1, 2, 1]
    assert metadata["durations_ms"] == [100, 50, 200, 50]
    assert metadata["total_duration_ms"] == 400
    assert metadata["header"]["contains_icons"] is True
    assert len(metadata["frames"]) == 3
    assert metadata["frames"][0]["format"] == "cur"
    assert len(metadata["frames"][0]["images"]) == 2


def test_disable_outputs(ani_path: Path, tmp_path: Path) -> None:
    output = tmp_path / "out"
    extract(
        ani_path,
        output,
        ExtractOptions(write_raw=False, write_png=False, write_metadata=False),
    )

    assert list(output.iterdir()) == []


def test_extract_options_is_keyword_only() -> None:
    with pytest.raises(TypeError):
        ExtractOptions(False)


def test_broken_frame_produces_warning(tmp_path: Path) -> None:
    from conftest import build_ani, make_cur

    source = tmp_path / "broken.ani"
    source.write_bytes(build_ani([make_cur((255, 0, 0, 255)), b"\x00" * 32]))

    result = extract(source, tmp_path / "out", ExtractOptions())

    assert result.png_count == 1
    assert any("frame_001" in warning for warning in result.warnings)
    assert (tmp_path / "out" / "frame_001.bin").is_file()
