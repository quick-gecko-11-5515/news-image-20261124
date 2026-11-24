#!/usr/bin/env python3
"""Entrypoint for make.fun news-image-20261124 (Tuesday 24 November 2026).

Copies the pre-rendered deterministic 1024x1024 PNG front page (`entry.png`
located alongside this script) into the target output directory specified by
`MAKEFUN_OUTPUT_DIR` (defaulting to `/output`), creating the directory if it
does not already exist. Standard library only; Python 3.13 compatible.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys


def publish_entry() -> Path:
    """Copy `entry.png` next to this module into the output directory."""
    source_image = Path(__file__).resolve().parent / "entry.png"
    if not source_image.is_file():
        raise FileNotFoundError(f"Expected rendered front page at {source_image}")

    output_root = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    destination = Path(output_root + "/entry.png")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_image, destination)
    return destination


def main() -> int:
    try:
        publish_entry()
    except OSError as exc:
        print(f"Failed to write entry image: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
