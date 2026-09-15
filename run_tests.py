#!/usr/bin/env python3
"""Run every pytest and unittest regression. Extra arguments go to pytest."""
import sys
from pathlib import Path

import pytest


def main() -> int:
    arguments = sys.argv[1:] or [str(Path(__file__).resolve().parent / 'tests')]
    return pytest.main(arguments)


if __name__ == '__main__':
    raise SystemExit(main())
