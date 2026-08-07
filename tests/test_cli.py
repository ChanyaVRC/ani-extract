from __future__ import annotations

from pathlib import Path

import pytest

from ani_extract.cli import main
from conftest import build_ani, make_cur


def test_default_output_directory(ani_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main([str(ani_path)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert (ani_path.parent / "sample_frames" / "frame_000.png").is_file()
    assert "sample.ani" in captured.out


def test_output_option(ani_path: Path, tmp_path: Path) -> None:
    output = tmp_path / "custom"
    exit_code = main([str(ani_path), "-o", str(output), "--all-sizes", "--gif", "--apng"])

    assert exit_code == 0
    assert (output / "frame_000@16x16-32bpp.png").is_file()
    assert (output / "animation.gif").is_file()
    assert (output / "animation.png").is_file()


def test_multiple_sources_use_subdirectories(tmp_path: Path) -> None:
    output = tmp_path / "out"
    sources = []
    for name in ("first", "second"):
        path = tmp_path / f"{name}.ani"
        path.write_bytes(build_ani([make_cur((255, 0, 0, 255))]))
        sources.append(str(path))

    exit_code = main([*sources, "-o", str(output)])

    assert exit_code == 0
    assert (output / "first" / "frame_000.png").is_file()
    assert (output / "second" / "frame_000.png").is_file()


def test_glob_pattern_is_expanded(tmp_path: Path) -> None:
    output = tmp_path / "out"
    for name in ("alpha", "beta"):
        (tmp_path / f"{name}.ani").write_bytes(build_ani([make_cur((255, 0, 0, 255))]))

    exit_code = main([str(tmp_path / "*.ani"), "-o", str(output)])

    assert exit_code == 0
    assert (output / "alpha" / "frame_000.png").is_file()
    assert (output / "beta" / "frame_000.png").is_file()


def test_unmatched_glob_reports_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main([str(tmp_path / "*.ani")])

    assert exit_code == 1
    assert "file not found" in capsys.readouterr().err


def test_duplicate_stems_get_unique_output_directories(tmp_path: Path) -> None:
    output = tmp_path / "out"
    sources = []
    for parent in ("one", "two"):
        directory = tmp_path / parent
        directory.mkdir()
        path = directory / "cursor.ani"
        path.write_bytes(build_ani([make_cur((255, 0, 0, 255))]))
        sources.append(str(path))

    exit_code = main([*sources, "-o", str(output)])

    assert exit_code == 0
    assert (output / "cursor" / "frame_000.png").is_file()
    assert (output / "cursor_2" / "frame_000.png").is_file()


def test_quiet_suppresses_stdout(ani_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main([str(ani_path), "--quiet"])

    assert capsys.readouterr().out == ""


def test_missing_file_returns_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main([str(tmp_path / "nope.ani")])

    assert exit_code == 1
    assert "file not found" in capsys.readouterr().err


def test_invalid_file_returns_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "bad.ani"
    path.write_bytes(b"not an ani file at all")

    exit_code = main([str(path), "-o", str(tmp_path / "out")])

    assert exit_code == 1
    assert "Error" in capsys.readouterr().err


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])

    assert excinfo.value.code == 0
    assert "ani-extract" in capsys.readouterr().out
