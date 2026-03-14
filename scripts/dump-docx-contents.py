#!/usr/bin/env python3
"""Backward-compatible shim for extract-docx-contents.py."""

from pathlib import Path
import runpy
import sys


TARGET_SCRIPT = Path(__file__).with_name("extract-docx-contents.py")


def main() -> int:
    sys.argv[0] = str(TARGET_SCRIPT)
    runpy.run_path(str(TARGET_SCRIPT), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
