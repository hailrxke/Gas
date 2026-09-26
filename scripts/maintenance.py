#!/usr/bin/env python3
"""Back up, prune expired data, and rotate only this script's backups (default 7 days)."""

import argparse
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--backups", required=True)
    parser.add_argument("--keep-days", type=int, default=7)
    args = parser.parse_args()
    if args.keep_days < 1:
        parser.error("Keep at least one day of backups")
    database = Path(args.database).resolve()
    if not database.is_file():
        parser.error("Database does not exist; refusing to back up an empty database")
    directory = Path(args.backups).resolve()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    name = (
        "gas-backup-"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        + ".sqlite3"
    )
    destination = directory / name
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "server/manage.py"),
            "--database",
            str(database),
            "prune",
            "--backup",
            str(destination),
        ],
        check=True,
    )
    cutoff = time.time() - args.keep_days * 86400
    removed = 0
    for candidate in directory.glob("gas-backup-*.sqlite3"):
        if (
            candidate == destination
            or candidate.is_symlink()
            or not candidate.is_file()
        ):
            continue
        # Rotation is based on the generated timestamp, not filesystem timestamps.
        try:
            created = (
                datetime.strptime(candidate.name, "gas-backup-%Y%m%dT%H%M%S%fZ.sqlite3")
                .replace(tzinfo=timezone.utc)
                .timestamp()
            )
        except ValueError:
            continue
        if created < cutoff:
            candidate.unlink()
            removed += 1
    print(f"Backup verified; maintenance complete; {removed} expired backups removed.")


if __name__ == "__main__":
    main()
