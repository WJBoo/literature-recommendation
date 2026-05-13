#!/usr/bin/env python
from __future__ import annotations
# ruff: noqa: E402

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import re
import sys
import time

import httpx


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings
from app.ingestion.chunking import TextChunk, chunk_text, count_words
from app.ingestion.cleaning import clean_plain_text, html_to_text
from app.ingestion.quality_gate import recommendable_chunks
from app.ingestion.starter_corpus import STARTER_CORPUS, gutenberg_text_url_candidates
from app.services.classification import classify_excerpt
from app.services.embedding_jobs import ExcerptEmbeddingInput, build_excerpt_embedding_text
from app.services.processed_corpus import clear_processed_corpus_cache


USER_AGENT = "LiteratureRecommendationEngine/0.1 educational starter import"
DEFAULT_MAX_EXCERPTS_PER_WORK = 0
DEFAULT_MAX_POETRY_EXCERPTS_PER_WORK = 200


def main() -> None:
    parser = argparse.ArgumentParser(description="Download and process a small Gutenberg corpus.")
    parser.add_argument("--limit", type=int, default=len(STARTER_CORPUS))
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
    parser.add_argument("--force-download", action="store_true")
    args = parser.parse_args()

    raw_dir = settings.gutenberg_raw_dir
    processed_dir = settings.processed_data_dir
    clean_dir = processed_dir / "gutenberg_clean"
    raw_dir.mkdir(parents=True, exist_ok=True)
    clean_dir.mkdir(parents=True, exist_ok=True)

    works_path = processed_dir / "gutenberg_works.jsonl"
    excerpts_path = processed_dir / "gutenberg_excerpts.jsonl"
    embeddings_manifest_path = processed_dir / "gutenberg_embedding_inputs.jsonl"

    selected_works = STARTER_CORPUS[: args.limit]
    work_records: list[dict[str, object]] = []
    excerpt_records: list[dict[str, object]] = []
    embedding_input_records: list[dict[str, object]] = []

    with httpx.Client(headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=60) as client:
        for work in selected_works:
            raw_path, source_url = download_work_text(client, work.gutenberg_id, raw_dir, args.force_download)
            clean_text = clean_downloaded_text(raw_path)
            clean_text = trim_to_start_patterns(clean_text, work.start_patterns)
            chunks = chunk_text(clean_text, work.form)
            clean_path = clean_dir / f"{work.gutenberg_id}.txt"
            clean_path.write_text(clean_text, encoding="utf-8")

            author = ", ".join(work.authors) if work.authors else "Unknown"
            max_excerpts = (
                args.max_poetry_excerpts_per_work
                if work.form.lower() in {"poem", "poetry"}
                else args.max_excerpts_per_work
            )
            quality_gate = recommendable_chunks(
                chunks,
                form=work.form,
                work_title=work.title,
                author=author,
                subjects=work.subjects,
                max_excerpts=max_excerpts,
            )
            kept_chunks = quality_gate.chunks
            if not kept_chunks:
                print(
                    f"Skipped {work.gutenberg_id}: {work.title} "
                    f"(0 recommendable chunks, {quality_gate.rejected_count} quality-filtered)"
                )
                continue
            work_records.append(
                {
                    "id": work.work_id,
                    "gutenberg_id": work.gutenberg_id,
                    "title": work.title,
                    "author": author,
                    "language": work.language,
                    "form": work.form,
                    "subjects": work.subjects,
                    "bookshelves": work.bookshelves,
                    "source_url": source_url,
                    "raw_path": str(raw_path.relative_to(ROOT)),
                    "clean_path": str(clean_path.relative_to(ROOT)),
                    "clean_word_count": count_words(clean_text),
                    "excerpt_count": len(kept_chunks),
                    "total_chunk_count": len(chunks),
                    "quality_filtered_chunk_count": quality_gate.rejected_count,
                    "processed_at": datetime.now(UTC).isoformat(),
                }
            )

            for index, chunk in enumerate(kept_chunks, start=1):
                excerpt_id = f"{work.work_id}-excerpt-{index:04d}"
                identity = build_excerpt_identity(work.title, work.form, chunk, index)
                labels = [
                    {
                        "label_type": label.label_type,
                        "label": label.label,
                        "evidence": label.evidence,
                    }
                    for label in classify_excerpt(chunk.text, work.form, work.subjects)
                ]
                embedding_text = build_excerpt_embedding_text(
                    ExcerptEmbeddingInput(
                        excerpt_id=index,
                        title=identity["title"],
                        author=author,
                        form=work.form,
                        subjects=work.subjects,
                        text=chunk.text,
                        work_title=work.title,
                        section_title=identity["section_title"],
                    )
                )
                excerpt_records.append(
                    {
                        "id": excerpt_id,
                        "work_id": work.work_id,
                        "gutenberg_id": work.gutenberg_id,
                        "excerpt_index": index,
                        "title": identity["title"],
                        "display_title": identity["title"],
                        "work_title": work.title,
                        "section_title": identity["section_title"],
                        "section_index": chunk.section_index,
                        "section_excerpt_index": chunk.excerpt_index_in_section,
                        "excerpt_label": identity["excerpt_label"],
                        "author": author,
                        "form": work.form,
                        "subjects": work.subjects,
                        "labels": labels,
                        "text": chunk.text,
                        "chunk_type": chunk.chunk_type,
                        "word_count": chunk.word_count,
                    }
                )
                embedding_input_records.append(
                    {
                        "excerpt_id": excerpt_id,
                        "work_id": work.work_id,
                        "embedding_model": settings.embedding_model,
                        "embedding_dimensions": settings.embedding_dimensions,
                        "embedding_text": embedding_text,
                    }
                )

            print(
                f"Processed {work.gutenberg_id}: {work.title} "
                f"({len(kept_chunks)} kept / {len(chunks)} chunks, "
                f"{quality_gate.rejected_count} quality-filtered)"
            )
            time.sleep(0.4)

    write_jsonl(works_path, work_records)
    write_jsonl(excerpts_path, excerpt_records)
    write_jsonl(embeddings_manifest_path, embedding_input_records)
    clear_processed_corpus_cache()
    print(f"Wrote {len(work_records)} works to {works_path}")
    print(f"Wrote {len(excerpt_records)} excerpts to {excerpts_path}")


def download_work_text(
    client: httpx.Client, gutenberg_id: str, raw_dir: Path, force_download: bool
) -> tuple[Path, str]:
    raw_path = raw_dir / f"{gutenberg_id}.txt"
    if raw_path.exists() and not force_download:
        return raw_path, "local-cache"

    errors: list[str] = []
    for attempt in range(1, 4):
        for url in gutenberg_text_url_candidates(gutenberg_id):
            try:
                response = client.get(url)
                if response.status_code == 200 and response.text.strip():
                    raw_path.write_text(
                        response.text,
                        encoding=response.encoding or "utf-8",
                        errors="replace",
                    )
                    return raw_path, url
                errors.append(f"attempt {attempt} {url}: HTTP {response.status_code}")
            except httpx.HTTPError as exc:
                errors.append(f"attempt {attempt} {url}: {exc}")
        time.sleep(0.8 * attempt)

    joined_errors = "\n".join(errors)
    raise RuntimeError(f"Unable to download Gutenberg text for {gutenberg_id}:\n{joined_errors}")


def clean_downloaded_text(path: Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() in {".html", ".htm"}:
        return html_to_text(raw)
    return clean_plain_text(raw)


def trim_to_start_patterns(text: str, start_patterns: list[str]) -> str:
    for pattern in start_patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            return text[match.start() :].strip()
    return text


def build_excerpt_identity(
    work_title: str,
    form: str,
    chunk: TextChunk,
    excerpt_index: int,
) -> dict[str, str | None]:
    if form.lower() in {"poem", "poetry"}:
        section_title = normalize_poem_section_title(work_title, chunk, excerpt_index)
        if chunk.chunk_type == "full_poem":
            title = section_title or f"Poem {excerpt_index}"
        elif section_title:
            title = f"{section_title}, Section {chunk.excerpt_index_in_section or 1}"
        else:
            title = f"Section {excerpt_index}"
        return {
            "title": title,
            "section_title": section_title,
            "excerpt_label": title,
        }

    section_title = chunk.section_title
    if section_title:
        local_index = chunk.excerpt_index_in_section or 1
        title = f"{section_title}, Excerpt {local_index}"
    else:
        title = f"Excerpt {excerpt_index}"

    return {
        "title": title,
        "section_title": section_title,
        "excerpt_label": title,
    }


def normalize_poem_section_title(
    work_title: str,
    chunk: TextChunk,
    excerpt_index: int,
) -> str | None:
    section_title = chunk.section_title
    work_title_lower = work_title.lower()
    if section_title and "sonnet" in work_title.lower():
        return section_title.replace("Poem ", "Sonnet ", 1)
    if section_title and ("beowulf" in work_title_lower or "epic" in work_title_lower):
        number = section_title.removeprefix("Poem ")
        subtitle = poem_section_subtitle(chunk.text)
        if subtitle:
            return f"Section {number}: {subtitle}"
        return f"Section {number}"
    if section_title:
        return section_title
    if "beowulf" in work_title_lower or "epic" in work_title_lower:
        return f"Section {excerpt_index}"
    if chunk.chunk_type == "full_poem":
        return f"Poem {excerpt_index}"
    return None


def poem_section_subtitle(text: str) -> str | None:
    lines = [line.strip().strip(".") for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return None
    subtitle = lines[1].strip("- ")
    if not subtitle or len(subtitle) > 80:
        return None
    return subtitle.title().replace("'S", "'s")


def write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output:
        for record in records:
            output.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
