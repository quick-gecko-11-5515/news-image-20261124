#!/usr/bin/env python3
"""Entry point that publishes the pre-rendered front page PNG."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def publish_entry() -> Path:
    source_image = Path(__file__).resolve().parent / "entry.png"
    if not source_image.is_file():
        raise FileNotFoundError(f"Expected pre-rendered image at {source_image}")

    output_dir_value = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    if not output_dir_value:
        output_dir_value = "/output"

    destination_dir = Path(output_dir_value)
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination_file = destination_dir / "entry.png"

    shutil.copyfile(source_image, destination_file)
    return destination_file


def main() -> int:
    publish_entry()
    return 0


if __name__ == "__main__":
    sys.exit(main())
