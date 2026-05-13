#!/usr/bin/env python
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings
from app.db.bootstrap import init_database
from app.db.session import engine


async def run(drop_existing: bool) -> None:
    await init_database(drop_existing=drop_existing)
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the database schema.")
    parser.add_argument(
        "--drop-existing",
        action="store_true",
        help="Drop all SQLAlchemy-owned tables before recreating them.",
    )
    args = parser.parse_args()

    asyncio.run(run(args.drop_existing))
    print(f"Initialized database schema at {settings.database_url}")


if __name__ == "__main__":
    main()
