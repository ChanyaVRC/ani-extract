# ani-extract

[![CI](https://github.com/ChanyaVRC/ani-extract/actions/workflows/ci.yml/badge.svg)](https://github.com/ChanyaVRC/ani-extract/actions/workflows/ci.yml)

A command-line tool that extracts frame images from Windows animated cursors (`.ani`).

An `.ani` file is a RIFF/ACON container whose `LIST/fram` section holds multiple `.cur` / `.ico`
images. Simply renaming the extension does not produce a usable image, but extracting the
`icon` chunks makes PNG conversion possible.

## Features

- Recursively scans `icon` chunks and extracts frames
- Outputs both the original `.cur` / `.ico` files and PNGs
- Expands **every resolution** contained in a single `.cur` / `.ico` into individual PNGs (`--all-sizes`)
- Parses `anih` / `seq` / `rate` and writes **GIF / APNG / WebP files that respect playback order and frame durations**
- Records the header, resolution list, hotspots, and playback duration in `metadata.json`

## Installation

Install as a tool with [uv](https://docs.astral.sh/uv/):

```console
uv tool install .
```

Or with pip:

```console
pip install .
```

For development (with tests and lint):

```console
uv sync --extra dev
```

## Usage

```console
ani-extract sample.ani
```

Specify the output directory:

```console
ani-extract sample.ani -o extracted
```

Expand all resolutions and also write GIF, APNG, and WebP:

```console
ani-extract sample.ani -o extracted --all-sizes --gif --apng --webp
```

Process multiple files at once (creates a subdirectory per file under `-o`):

```console
ani-extract cursors/*.ani -o extracted
```

Glob patterns are expanded by the tool itself when the shell leaves them untouched, so the
command above also works in PowerShell and cmd.exe. Inputs sharing the same file name are
written to numbered subdirectories (`cursor`, `cursor_2`, …).

Run without installing:

```console
uv run ani-extract sample.ani
```

### Options

| Option | Description |
| --- | --- |
| `-o`, `--output` | Output directory (default: `<input name>_frames` next to each input; with multiple inputs, one subdirectory per file is created under it) |
| `--all-sizes` | Write every resolution in a frame as `frame_000@32x32-32bpp.png` |
| `--sequence` | Write `step_000.png` … following the playback order of the `seq` chunk |
| `--gif` | Write an animated GIF that respects playback order and durations |
| `--apng` | Likewise write an animated PNG (APNG) |
| `--webp` | Likewise write an animated WebP (lossless, full alpha) |
| `--no-raw` | Do not write the original `.cur` / `.ico` files |
| `--no-png` | Do not write the representative PNGs |
| `--no-metadata` | Do not write `metadata.json` |
| `-q`, `--quiet` | Suppress progress output (warnings still go to stderr) |

### Example output

```text
sample_frames/
├── frame_000.cur
├── frame_000.png
├── frame_000@32x32-32bpp.png
├── frame_000@48x48-32bpp.png
├── frame_001.cur
├── frame_001.png
├── animation.gif
├── animation.png
├── animation.webp
└── metadata.json
```

`frame_XXX.png` is the largest image within each frame, written as the representative.
Use `--all-sizes` if you need every resolution.

## Using as a library

```python
from pathlib import Path

from ani_extract import ExtractOptions, extract, parse_ani

ani = parse_ani(Path("sample.ani").read_bytes())
print(len(ani.frames), ani.sequence, ani.durations_ms)

result = extract(
    Path("sample.ani"),
    Path("extracted"),
    ExtractOptions(all_sizes=True, write_gif=True),
)
print(result.png_count, result.warnings)
```

## Format notes

- The time unit is the jiffy (1/60 second). When there is no `rate` chunk, the default rate
  from `anih` is used.
- With the `seq` chunk, playback order can be something like `0 → 1 → 2 → 1` even when only three
  frames are stored. GIF / APNG / WebP output and `--sequence` follow this order.
- GIF supports only a single transparent color, so semi-transparent anti-aliasing is lost.
  Use `--apng` or `--webp` when fidelity matters; both keep the full alpha channel.
- WebP output is exact lossless: even the RGB values of fully transparent pixels are
  preserved, and each playback step becomes its own frame (no frame merging).
- Files whose `anih` icon flag is not set (frames stored as raw DIBs) produce a warning.

## Development

```console
uv sync --extra dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

## License

MIT License. See [LICENSE](LICENSE) for details.
