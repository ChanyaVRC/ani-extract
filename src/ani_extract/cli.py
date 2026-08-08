"""Entry point for the ``ani-extract`` command."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .ani import AniError
from .extractor import ExtractOptions, ExtractResult, extract
from .icons import IconError
from .riff import RiffError

__all__ = ["build_parser", "main"]

_EXTRACTION_ERRORS = (AniError, IconError, RiffError, OSError, ValueError)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ani-extract",
        description="Extract CUR/ICO frames and PNGs from Windows animated cursors (.ani).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  ani-extract sample.ani\n"
            "  ani-extract sample.ani -o out --all-sizes\n"
            "  ani-extract *.ani -o out --gif --apng --webp\n"
        ),
    )

    parser.add_argument(
        "sources",
        nargs="+",
        type=Path,
        help="input .ani files (glob patterns are expanded if the shell does not)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help=(
            "output directory (default: <input name>_frames next to each input; "
            "with multiple inputs, one subdirectory per file is created under it)"
        ),
    )
    parser.add_argument(
        "--all-sizes",
        action="store_true",
        help="write every resolution in a frame as an individual PNG",
    )
    parser.add_argument(
        "--sequence",
        action="store_true",
        help="write step_XXX.png files following the playback order of the seq chunk",
    )
    parser.add_argument("--gif", action="store_true", help="write an animated GIF")
    parser.add_argument("--apng", action="store_true", help="write an animated PNG (APNG)")
    parser.add_argument("--webp", action="store_true", help="write an animated WebP")
    parser.add_argument("--no-raw", action="store_true", help="do not write the original CUR/ICO")
    parser.add_argument("--no-png", action="store_true", help="do not write representative PNGs")
    parser.add_argument("--no-metadata", action="store_true", help="do not write metadata.json")
    parser.add_argument("-q", "--quiet", action="store_true", help="suppress progress output")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    return parser


_GLOB_CHARS = frozenset("*?[")


def _expand_sources(sources: list[Path]) -> list[Path]:
    """Expand glob patterns the shell left unexpanded (e.g. cmd.exe / PowerShell)."""
    expanded: list[Path] = []
    for source in sources:
        if source.exists() or not _GLOB_CHARS.intersection(str(source)):
            expanded.append(source)
            continue
        matches = sorted(source.parent.glob(source.name))
        expanded.extend(matches if matches else [source])
    return expanded


def _resolve_output_directory(
    source: Path, output: Path | None, *, multiple: bool, used_stems: dict[str, int]
) -> Path:
    if output is None:
        return source.with_name(f"{source.stem}_frames")
    if not multiple:
        return output

    # Disambiguate inputs sharing a stem (e.g. a/cursor.ani and b/cursor.ani)
    count = used_stems.get(source.stem, 0)
    used_stems[source.stem] = count + 1
    name = source.stem if count == 0 else f"{source.stem}_{count + 1}"
    return output / name


def _report(result: ExtractResult, *, quiet: bool) -> None:
    for warning in result.warnings:
        print(f"[WARN] {result.source.name}: {warning}", file=sys.stderr)

    if quiet:
        return

    print(f"{result.source.name}: {result.frame_count} frames / {result.step_count} steps")
    print(f"  Output: {result.output_directory.resolve()}")
    print(f"  Files written: {len(result.written_files)} ({result.png_count} PNGs)")
    if result.ani.durations_ms:
        print(f"  Playback duration: {sum(result.ani.durations_ms)} ms")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    options = ExtractOptions(
        write_raw=not args.no_raw,
        write_png=not args.no_png,
        all_sizes=args.all_sizes,
        write_sequence=args.sequence,
        write_gif=args.gif,
        write_apng=args.apng,
        write_webp=args.webp,
        write_metadata=not args.no_metadata,
    )

    sources = _expand_sources(args.sources)
    multiple = len(sources) > 1
    used_stems: dict[str, int] = {}
    failures = 0

    for source in sources:
        if not source.is_file():
            print(f"Error: file not found: {source}", file=sys.stderr)
            failures += 1
            continue

        output_directory = _resolve_output_directory(
            source, args.output, multiple=multiple, used_stems=used_stems
        )

        try:
            result = extract(source, output_directory, options)
        except _EXTRACTION_ERRORS as error:
            print(f"Error: {source.name}: {error}", file=sys.stderr)
            failures += 1
            continue

        _report(result, quiet=args.quiet)

    return 1 if failures else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
