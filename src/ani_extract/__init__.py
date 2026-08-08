"""Library for extracting frame images from Windows animated cursors (.ani)."""

from __future__ import annotations

__version__ = "0.1.0"

from .ani import AniError, AniFile, AniHeader, Step, parse_ani
from .animation import save_apng, save_gif, save_webp
from .extractor import ExtractOptions, ExtractResult, extract
from .icons import IconContainer, IconEntry, IconError, open_entry, parse_icon_container
from .riff import Chunk, RiffError

__all__ = [
    "AniError",
    "AniFile",
    "AniHeader",
    "Chunk",
    "ExtractOptions",
    "ExtractResult",
    "IconContainer",
    "IconEntry",
    "IconError",
    "RiffError",
    "Step",
    "__version__",
    "extract",
    "open_entry",
    "parse_ani",
    "parse_icon_container",
    "save_apng",
    "save_gif",
    "save_webp",
]
