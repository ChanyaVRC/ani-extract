"""Entry point for running via ``python -m ani_extract``."""

from __future__ import annotations

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
