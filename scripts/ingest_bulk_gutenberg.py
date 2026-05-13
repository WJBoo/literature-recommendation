#!/usr/bin/env python
from __future__ import annotations
# ruff: noqa: E402

import argparse
import csv
from dataclasses import dataclass
from datetime import UTC, datetime
import gzip
from pathlib import Path
import re
import sys
import time
from typing import Iterable

import httpx


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings
from app.ingestion.canonicalization import canonical_author, canonical_title
from app.ingestion.chunking import chunk_text, count_words
from app.ingestion.metadata import GutenbergWorkMetadata, infer_form
from app.ingestion.quality_gate import recommendable_chunks
from app.services.classification import classify_excerpt
from app.services.embedding_jobs import ExcerptEmbeddingInput, build_excerpt_embedding_text
from app.services.processed_corpus import clear_processed_corpus_cache
from scripts.ingest_starter_gutenberg import (
    USER_AGENT,
    build_excerpt_identity,
    clean_downloaded_text,
    download_work_text,
    write_jsonl,
)


CATALOG_URL = "https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv.gz"
DEFAULT_TARGET_WORKS = 1000
DEFAULT_CANDIDATE_MULTIPLIER = 3
DEFAULT_MAX_EXCERPTS_PER_WORK = 0
DEFAULT_MAX_POETRY_EXCERPTS_PER_WORK = 200
DEFAULT_DOWNLOAD_DELAY_SECONDS = 1.0
DEFAULT_MIN_WORK_WORDS = 1200

LITERARY_TERMS = {
    "adventure",
    "children",
    "classics",
    "drama",
    "fairy tale",
    "fantasy",
    "fiction",
    "folklore",
    "gothic",
    "humor",
    "humour",
    "legends",
    "literature",
    "love",
    "mystery",
    "mythology",
    "novel",
    "plays",
    "poetry",
    "romance",
    "satire",
    "science fiction",
    "short stories",
    "tragedy",
}

EXCLUDED_TERMS = {
    "bibliography",
    "bulletin",
    "catalog",
    "dictionary",
    "directory",
    "encyclopedia",
    "gazette",
    "index",
    "manual",
    "newspaper",
    "periodical",
    "proceedings",
    "report",
    "sheet music",
    "table",
}
UNKNOWN_AUTHOR_NAMES = {"anonymous", "unknown", "various"}
TITLE_PART_NUMBER_PATTERN = (
    r"(?:[0-9ivxlcdm]+|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"(?:the\s+)?(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth))"
)
PART_OR_VOLUME_TITLE_RE = re.compile(
    fr"(?ix)"
    fr"(?:"
    fr"(?:^|[\s,;:(\[])(?:parts?|vols?\.?|volumes?)\s+{TITLE_PART_NUMBER_PATTERN}"
    fr"\b(?:\s*(?:\([^)]*\)|of\s+{TITLE_PART_NUMBER_PATTERN}))?"
    fr"|(?:,\s*)?chapters?\s+{TITLE_PART_NUMBER_PATTERN}"
    fr"(?:\s*(?:to|-|through|\u2013|\u2014)\s*{TITLE_PART_NUMBER_PATTERN})?"
    fr"|(?:^|[\s,;:(\[])(?:books?|cantos?)\s+{TITLE_PART_NUMBER_PATTERN}"
    fr"(?:\s*(?:to|-|through|\u2013|\u2014)\s*{TITLE_PART_NUMBER_PATTERN})?"
    fr"(?:\s+of\s+{TITLE_PART_NUMBER_PATTERN})?"
    fr")"
)


@dataclass(frozen=True)
class CatalogCandidate:
    gutenberg_id: str
    title: str
    authors: list[str]
    language: str
    subjects: list[str]
    bookshelves: list[str]
    locc: list[str]
    score: int

    @property
    def metadata(self) -> GutenbergWorkMetadata:
        return GutenbergWorkMetadata(
            gutenberg_id=self.gutenberg_id,
            title=self.title,
            authors=self.authors,
            language=self.language,
            subjects=self.subjects,
            bookshelves=self.bookshelves,
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Select, download, clean, chunk, and vector-manifest a larger Gutenberg corpus."
    )
    parser.add_argument("--target-works", type=int, default=DEFAULT_TARGET_WORKS)
    parser.add_argument("--candidate-limit", type=int, default=None)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--catalog-url", default=CATALOG_URL)
    parser.add_argument(
        "--catalog-path",
        type=Path,
        default=settings.gutenberg_raw_dir / "pg_catalog.csv.gz",
    )
    parser.add_argument("--refresh-catalog", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force-download", action="store_true")
    parser.add_argument("--download-delay", type=float, default=DEFAULT_DOWNLOAD_DELAY_SECONDS)
    parser.add_argument("--max-failures", type=int, default=100)
    parser.add_argument("--min-work-words", type=int, default=DEFAULT_MIN_WORK_WORDS)
    parser.add_argument(
        "--max-excerpts-per-work",
        type=int,
        default=DEFAULT_MAX_EXCERPTS_PER_WORK,
        help="Maximum prose excerpts to keep per work; use 0 to keep the complete work.",
    )
    parser.add_argument(
        "--max-poetry-excerpts-per-work",
        type=int,
        default=DEFAULT_MAX_POETRY_EXCERPTS_PER_WORK,
    )
    parser.add_argument("--include-nonliterary", action="store_true")
    parser.add_argument("--allow-unknown-authors", action="store_true")
    parser.add_argument("--allow-part-records", action="store_true")
    parser.add_argument("--allow-duplicate-titles", action="store_true")
    parser.add_argument("--selection-mode", choices=["balanced", "score"], default="balanced")
    args = parser.parse_args()

    raw_dir = settings.gutenberg_raw_dir
    processed_dir = settings.processed_data_dir
    clean_dir = processed_dir / "gutenberg_clean"
    raw_dir.mkdir(parents=True, exist_ok=True)
    clean_dir.mkdir(parents=True, exist_ok=True)

    ensure_catalog(args.catalog_path, args.catalog_url, refresh=args.refresh_catalog)
    rows = list(read_catalog_rows(args.catalog_path))
    candidate_limit = args.candidate_limit or args.target_works * DEFAULT_CANDIDATE_MULTIPLIER
    candidates = select_catalog_candidates(
        rows,
        target_count=candidate_limit,
        offset=args.offset,
        include_nonliterary=args.include_nonliterary,
        allow_unknown_authors=args.allow_unknown_authors,
        allow_part_records=args.allow_part_records,
        allow_duplicate_titles=args.allow_duplicate_titles,
        selection_mode=args.selection_mode,
    )

    print(
        f"Selected {len(candidates)} candidate works from {len(rows)} catalog rows "
        f"(target successful works={args.target_works})."
    )
    for preview in candidates[:10]:
        print(
            f"  {preview.gutenberg_id}: {preview.title} / "
            f"{', '.join(preview.authors) or 'Unknown'} score={preview.score}"
        )
    if args.dry_run:
        return

    work_records: list[dict[str, object]] = []
    excerpt_records: list[dict[str, object]] = []
    embedding_input_records: list[dict[str, object]] = []
    failure_records: list[dict[str, object]] = []

    with httpx.Client(headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=60) as client:
        for candidate in candidates:
            if len(work_records) >= args.target_works:
                break
            if len(failure_records) >= args.max_failures:
                print(f"Stopping after {len(failure_records)} failures.")
                break

            try:
                result = process_candidate(
                    candidate,
                    client=client,
                    raw_dir=raw_dir,
                    clean_dir=clean_dir,
                    force_download=args.force_download,
                    min_work_words=args.min_work_words,
                    max_excerpts_per_work=args.max_excerpts_per_work,
                    max_poetry_excerpts_per_work=args.max_poetry_excerpts_per_work,
                    existing_excerpt_count=len(excerpt_records),
                )
            except Exception as exc:  # noqa: BLE001 - operational script should keep moving.
                failure_records.append(
                    {
                        "gutenberg_id": candidate.gutenberg_id,
                        "title": candidate.title,
                        "error": str(exc),
                    }
                )
                print(f"Failed {candidate.gutenberg_id}: {candidate.title} - {exc}")
                continue

            if result is None:
                failure_records.append(
                    {
                        "gutenberg_id": candidate.gutenberg_id,
                        "title": candidate.title,
                        "error": "Skipped by work-length or excerpt-quality filters",
                    }
                )
                continue

            work_record, excerpts, embedding_inputs = result
            work_records.append(work_record)
            excerpt_records.extend(excerpts)
            embedding_input_records.extend(embedding_inputs)
            print(
                f"Processed {candidate.gutenberg_id}: {candidate.title} "
                f"({work_record['excerpt_count']} kept / {work_record['total_chunk_count']} chunks, "
                f"{work_record.get('quality_filtered_chunk_count', 0)} quality-filtered, "
                f"{len(work_records)}/{args.target_works} works)",
                flush=True,
            )
            if args.download_delay > 0 and work_record.get("source_url") != "local-cache":
                time.sleep(args.download_delay)

    write_jsonl(processed_dir / "gutenberg_works.jsonl", work_records)
    write_jsonl(processed_dir / "gutenberg_excerpts.jsonl", excerpt_records)
    write_jsonl(processed_dir / "gutenberg_embedding_inputs.jsonl", embedding_input_records)
    write_jsonl(processed_dir / "gutenberg_bulk_failures.jsonl", failure_records)
    clear_processed_corpus_cache()

    print(f"Wrote {len(work_records)} works to {processed_dir / 'gutenberg_works.jsonl'}")
    print(f"Wrote {len(excerpt_records)} excerpts to {processed_dir / 'gutenberg_excerpts.jsonl'}")
    print(f"Wrote {len(failure_records)} failures to {processed_dir / 'gutenberg_bulk_failures.jsonl'}")


def ensure_catalog(catalog_path: Path, catalog_url: str, *, refresh: bool) -> None:
    if catalog_path.exists() and not refresh:
        return
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    with httpx.Client(headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=120) as client:
        response = client.get(catalog_url)
        response.raise_for_status()
        catalog_path.write_bytes(response.content)


def read_catalog_rows(catalog_path: Path) -> Iterable[dict[str, str]]:
    with gzip.open(catalog_path, "rt", encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        for row in reader:
            yield {key: value for key, value in row.items() if key is not None}


def select_catalog_candidates(
    rows: Iterable[dict[str, str]],
    *,
    target_count: int,
    offset: int = 0,
    include_nonliterary: bool = False,
    allow_unknown_authors: bool = False,
    allow_part_records: bool = False,
    allow_duplicate_titles: bool = False,
    selection_mode: str = "balanced",
) -> list[CatalogCandidate]:
    candidates = [
        candidate
        for row in rows
        if (
            candidate := catalog_candidate_from_row(
                row,
                include_nonliterary=include_nonliterary,
                allow_unknown_authors=allow_unknown_authors,
                allow_part_records=allow_part_records,
            )
        )
    ]
    candidates.sort(key=lambda candidate: (-candidate.score, int(candidate.gutenberg_id)))
    if not allow_duplicate_titles:
        candidates = deduplicate_candidates(candidates)
    if selection_mode == "balanced":
        return balanced_candidates(candidates, target_count=target_count, offset=offset)
    return candidates[offset : offset + target_count]


def deduplicate_candidates(candidates: list[CatalogCandidate]) -> list[CatalogCandidate]:
    kept: list[CatalogCandidate] = []
    seen: set[tuple[str, str]] = set()
    for candidate in candidates:
        key = (author_key(candidate.authors), title_key(candidate.title))
        if key in seen:
            continue
        kept.append(candidate)
        seen.add(key)
    return kept


def balanced_candidates(
    candidates: list[CatalogCandidate],
    *,
    target_count: int,
    offset: int,
) -> list[CatalogCandidate]:
    grouped = {
        "prose": [candidate for candidate in candidates if infer_form(candidate.metadata) == "prose"],
        "poetry": [candidate for candidate in candidates if infer_form(candidate.metadata) == "poetry"],
        "drama": [candidate for candidate in candidates if infer_form(candidate.metadata) == "drama"],
    }
    weights = [("prose", 3), ("poetry", 1), ("drama", 1)]
    selected: list[CatalogCandidate] = []
    indexes = {form: 0 for form in grouped}
    while len(selected) < offset + target_count:
        added = False
        for form, weight in weights:
            for _ in range(weight):
                index = indexes[form]
                if index >= len(grouped[form]):
                    continue
                selected.append(grouped[form][index])
                indexes[form] += 1
                added = True
                if len(selected) >= offset + target_count:
                    break
            if len(selected) >= offset + target_count:
                break
        if not added:
            break
    if len(selected) < offset + target_count:
        seen = {candidate.gutenberg_id for candidate in selected}
        selected.extend(candidate for candidate in candidates if candidate.gutenberg_id not in seen)
    return selected[offset : offset + target_count]


def catalog_candidate_from_row(
    row: dict[str, str],
    *,
    include_nonliterary: bool = False,
    allow_unknown_authors: bool = False,
    allow_part_records: bool = False,
) -> CatalogCandidate | None:
    gutenberg_id = (row.get("Text#") or "").strip()
    if not gutenberg_id.isdigit():
        return None
    if (row.get("Type") or "").strip().lower() != "text":
        return None
    language = (row.get("Language") or "").strip().lower()
    if language != "en":
        return None

    title = clean_catalog_value(row.get("Title", ""))
    authors = split_catalog_list(row.get("Authors", ""))
    subjects = split_catalog_list(row.get("Subjects", ""))
    bookshelves = split_catalog_list(row.get("Bookshelves", ""))
    locc = split_catalog_list(row.get("LoCC", ""))
    if not title or not authors:
        return None
    if not allow_part_records and is_part_or_volume_record(title):
        return None
    if not allow_unknown_authors and all(is_unknown_author(author) for author in authors):
        return None

    searchable = " ".join([title, *subjects, *bookshelves]).lower()
    if any(term in searchable for term in EXCLUDED_TERMS):
        return None

    score = literary_score(subjects, bookshelves, locc, title)
    if score <= 0 and not include_nonliterary:
        return None

    return CatalogCandidate(
        gutenberg_id=gutenberg_id,
        title=title,
        authors=authors,
        language=language,
        subjects=subjects,
        bookshelves=bookshelves,
        locc=locc,
        score=score,
    )


def literary_score(subjects: list[str], bookshelves: list[str], locc: list[str], title: str) -> int:
    searchable = " ".join([title, *subjects, *bookshelves]).lower()
    score = 0
    if any(code.strip().upper().startswith("P") for code in locc):
        score += 6
    for term in LITERARY_TERMS:
        if term in searchable:
            score += 3
    if "category: fiction" in searchable:
        score += 5
    if "category: poetry" in searchable:
        score += 5
    if "category: plays" in searchable or "category: drama" in searchable:
        score += 5
    return score


def output_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def process_candidate(
    candidate: CatalogCandidate,
    *,
    client: httpx.Client,
    raw_dir: Path,
    clean_dir: Path,
    force_download: bool,
    min_work_words: int,
    max_excerpts_per_work: int,
    max_poetry_excerpts_per_work: int,
    existing_excerpt_count: int,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]] | None:
    raw_path, source_url = download_work_text(
        client,
        candidate.gutenberg_id,
        raw_dir,
        force_download,
    )
    clean_text = clean_downloaded_text(raw_path)
    clean_word_count = count_words(clean_text)
    if clean_word_count < min_work_words:
        return None

    metadata = candidate.metadata
    form = infer_form(metadata)
    chunks = chunk_text(clean_text, form)
    author = ", ".join(candidate.authors)
    max_excerpts = (
        max_poetry_excerpts_per_work
        if form.lower() in {"poem", "poetry"}
        else max_excerpts_per_work
    )
    quality_gate = recommendable_chunks(
        chunks,
        form=form,
        work_title=candidate.title,
        author=author,
        subjects=candidate.subjects,
        max_excerpts=max_excerpts,
    )
    kept_chunks = quality_gate.chunks
    if not kept_chunks:
        return None
    clean_path = clean_dir / f"{candidate.gutenberg_id}.txt"
    clean_path.write_text(clean_text, encoding="utf-8")

    work_id = f"gutenberg-{candidate.gutenberg_id}"
    processed_at = datetime.now(UTC).isoformat()
    work_record: dict[str, object] = {
        "id": work_id,
        "gutenberg_id": candidate.gutenberg_id,
        "title": candidate.title,
        "canonical_title": canonical_title(candidate.title),
        "canonical_author": canonical_author(author),
        "author": author,
        "language": candidate.language,
        "form": form,
        "subjects": candidate.subjects,
        "bookshelves": candidate.bookshelves,
        "source_url": source_url,
        "raw_path": output_path(raw_path),
        "clean_path": output_path(clean_path),
        "clean_word_count": clean_word_count,
        "excerpt_count": len(kept_chunks),
        "total_chunk_count": len(chunks),
        "quality_filtered_chunk_count": quality_gate.rejected_count,
        "processed_at": processed_at,
    }

    excerpt_records: list[dict[str, object]] = []
    embedding_input_records: list[dict[str, object]] = []
    for local_index, chunk in enumerate(kept_chunks, start=1):
        excerpt_id = f"{work_id}-excerpt-{local_index:04d}"
        identity = build_excerpt_identity(candidate.title, form, chunk, local_index)
        labels = [
            {
                "label_type": label.label_type,
                "label": label.label,
                "evidence": label.evidence,
            }
            for label in classify_excerpt(chunk.text, form, candidate.subjects)
        ]
        embedding_text = build_excerpt_embedding_text(
            ExcerptEmbeddingInput(
                excerpt_id=existing_excerpt_count + local_index,
                title=identity["title"] or candidate.title,
                author=author,
                form=form,
                subjects=candidate.subjects,
                text=chunk.text,
                work_title=candidate.title,
                section_title=identity["section_title"],
            )
        )
        excerpt_records.append(
            {
                "id": excerpt_id,
                "work_id": work_id,
                "gutenberg_id": candidate.gutenberg_id,
                "excerpt_index": local_index,
                "title": identity["title"] or f"Excerpt {local_index}",
                "display_title": identity["title"] or f"Excerpt {local_index}",
                "work_title": candidate.title,
                "canonical_work_title": canonical_title(candidate.title),
                "canonical_author": canonical_author(author),
                "section_title": identity["section_title"],
                "section_index": chunk.section_index,
                "section_excerpt_index": chunk.excerpt_index_in_section,
                "excerpt_label": identity["excerpt_label"],
                "author": author,
                "form": form,
                "subjects": candidate.subjects,
                "labels": labels,
                "text": chunk.text,
                "chunk_type": chunk.chunk_type,
                "word_count": chunk.word_count,
            }
        )
        embedding_input_records.append(
            {
                "excerpt_id": excerpt_id,
                "work_id": work_id,
                "embedding_model": settings.embedding_model,
                "embedding_dimensions": settings.embedding_dimensions,
                "embedding_text": embedding_text,
            }
        )

    return work_record, excerpt_records, embedding_input_records


def split_catalog_list(value: str) -> list[str]:
    return [clean_catalog_value(item) for item in value.split(";") if clean_catalog_value(item)]


def clean_catalog_value(value: str) -> str:
    return " ".join(value.strip().split())


def is_unknown_author(author: str) -> bool:
    cleaned = clean_catalog_value(author).lower()
    return cleaned in UNKNOWN_AUTHOR_NAMES


def is_part_or_volume_record(title: str) -> bool:
    return PART_OR_VOLUME_TITLE_RE.search(title) is not None


def title_key(title: str) -> str:
    base_title = PART_OR_VOLUME_TITLE_RE.sub("", title)
    return canonical_title(base_title)


def author_key(authors: list[str]) -> str:
    if not authors:
        return "unknown"
    return canonical_author(authors[0])


if __name__ == "__main__":
    main()
