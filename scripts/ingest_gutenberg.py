#!/usr/bin/env python
"""CLI placeholder for running Gutenberg ingestion.

The full implementation will:
1. Load the Gutenberg RDF catalog.
2. Filter to the selected corpus.
3. Download approved text/html files.
4. Clean and chunk works.
5. Persist works, excerpts, and embeddings.
"""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.ingestion.metadata import load_rdf_metadata


def main() -> None:
    catalog_path = Path("data/raw/gutenberg/catalog.rdf")
    if not catalog_path.exists():
        raise SystemExit(
            "Missing data/raw/gutenberg/catalog.rdf. Download Gutenberg catalog metadata first."
        )

    records = load_rdf_metadata(catalog_path)
    print(f"Loaded {len(records)} Gutenberg metadata records.")


if __name__ == "__main__":
    main()
