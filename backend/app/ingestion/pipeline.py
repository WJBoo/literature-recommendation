from dataclasses import dataclass
from pathlib import Path

from app.ingestion.chunking import TextChunk, chunk_text
from app.ingestion.cleaning import clean_plain_text, html_to_text
from app.ingestion.metadata import GutenbergWorkMetadata, infer_form


@dataclass(frozen=True)
class ProcessedWork:
    metadata: GutenbergWorkMetadata
    form: str
    clean_text: str
    chunks: list[TextChunk]


def process_local_file(metadata: GutenbergWorkMetadata, path: Path) -> ProcessedWork:
    raw = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() in {".html", ".htm"}:
        clean_text = html_to_text(raw)
    else:
        clean_text = clean_plain_text(raw)

    form = infer_form(metadata)
    chunks = chunk_text(clean_text, form)

    return ProcessedWork(metadata=metadata, form=form, clean_text=clean_text, chunks=chunks)

