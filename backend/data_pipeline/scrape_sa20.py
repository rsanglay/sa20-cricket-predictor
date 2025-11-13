"""Backward-compatible wrapper for ingesting SA20 data."""
from __future__ import annotations

import argparse

from backend.data_pipeline.ingest_cricsheet import ingest_competitions


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download & parse SA20 Cricsheet data")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Force re-download and re-extraction of archives",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ingest_competitions(["sa20"], overwrite=args.overwrite)


if __name__ == "__main__":
    main()
