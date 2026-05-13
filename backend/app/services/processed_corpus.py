from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
import json
from pathlib import Path
import re
from typing import Any

from app.core.config import settings
from app.ingestion.canonicalization import display_author
from app.ingestion.cleaning import trim_front_matter

ITALIC_MARKUP_RE = re.compile(r"_([^_\n]{1,120})_")
FOOTNOTE_RETURN_RE = re.compile(r"^\s*\d{2,5}\s*\(return\)\s*", re.IGNORECASE)
FOOTNOTE_PAGE_REF_RE = re.compile(r"(?<=\w),\s+\d{2,4}(?=(?:\s|[.;:,!?])|$)")


@dataclass(frozen=True)
class ProcessedExcerpt:
    id: str
    work_id: str
    gutenberg_id: str
    title: str
    author: str
    form: str
    subjects: list[str]
    labels: list[dict[str, str]]
    text: str
    chunk_type: str
    word_count: int
    work_title: str = ""
    display_title: str = ""
    section_title: str | None = None
    section_index: int | None = None
    section_excerpt_index: int | None = None
    excerpt_label: str | None = None
    media: list[dict[str, str | None]] = field(default_factory=list)

    @property
    def tags(self) -> set[str]:
        label_values = {label["label"] for label in self.labels if "label" in label}
        subject_values = {subject.lower() for subject in self.subjects}
        subject_tags = {
            tag
            for subject in self.subjects
            for tag in expand_subject_tags(subject)
        }
        return {self.form.lower(), *label_values, *subject_values, *subject_tags}

    @property
    def preview(self) -> str:
        single_line = " ".join(clean_display_text(self.text).split())
        if len(single_line) <= 260:
            return single_line
        return f"{single_line[:257].rstrip()}..."


class ProcessedCorpusService:
    def __init__(self, excerpts_path: Path | None = None) -> None:
        self.excerpts_path = excerpts_path or settings.processed_data_dir / "gutenberg_excerpts.jsonl"

    def list_excerpts(self) -> list[ProcessedExcerpt]:
        file_excerpts = _load_excerpts(str(self.excerpts_path))
        corpus_excerpts = file_excerpts or _load_database_excerpts(settings.database_url)
        return [
            *corpus_excerpts,
            *self.list_user_post_excerpts(),
        ]

    def list_user_post_excerpts(self) -> list[ProcessedExcerpt]:
        return _load_user_post_excerpts(str(self.excerpts_path.parent / "accounts.json"))

    def find_reader_item(self, item_id: str) -> ProcessedExcerpt | None:
        normalized_id = item_id.removeprefix("work-")
        for excerpt in self.list_excerpts():
            if excerpt.id == normalized_id or excerpt.work_id == normalized_id:
                return excerpt
        return None

    def author_id(self, author: str) -> str:
        return slugify(display_author(author))

    def find_author_name(self, author_id: str) -> str | None:
        for excerpt in self.list_excerpts():
            if self.author_id(excerpt.author) == author_id:
                return excerpt.author
        return None

    def excerpts_by_author(self, author_id: str) -> list[ProcessedExcerpt]:
        return [
            excerpt
            for excerpt in self.list_excerpts()
            if self.author_id(excerpt.author) == author_id
        ]

    def search_excerpts(self, query: str, limit: int = 24) -> list[ProcessedExcerpt]:
        raw_query = " ".join(query.lower().split())
        tokens = tokenize_query(query)
        if not tokens:
            return []
        if len(tokens) > 1:
            tokens = [token for token in tokens if len(token) > 2]
        if not tokens:
            tokens = tokenize_query(query)

        scored: list[tuple[int, ProcessedExcerpt]] = []
        for excerpt in self.list_excerpts():
            title_haystack = " ".join([excerpt.title, excerpt.work_title]).lower()
            author_haystack = excerpt.author.lower()
            metadata_haystack = " ".join(
                [
                    excerpt.form,
                    " ".join(excerpt.subjects),
                    " ".join(label.get("label", "") for label in excerpt.labels),
                ]
            ).lower()
            preview_haystack = excerpt.preview.lower()
            score = 0
            if raw_query and raw_query in title_haystack:
                score += 120
            if raw_query and raw_query in author_haystack:
                score += 90
            for token in tokens:
                score += title_haystack.count(token) * 18
                score += author_haystack.count(token) * 12
                score += metadata_haystack.count(token) * 6
                score += preview_haystack.count(token)
            if score:
                scored.append((score, excerpt))
        scored.sort(key=lambda item: (item[0], -item[1].word_count), reverse=True)
        return [excerpt for _, excerpt in scored[:limit]]


@lru_cache(maxsize=8)
def _load_excerpts(path: str) -> list[ProcessedExcerpt]:
    excerpts_path = Path(path)
    if not excerpts_path.exists():
        return []

    excerpts: list[ProcessedExcerpt] = []
    try:
        with excerpts_path.open("r", encoding="utf-8") as records:
            for line in records:
                if not line.strip():
                    continue
                record = json.loads(line)
                excerpts.append(
                    ProcessedExcerpt(
                        id=record["id"],
                        work_id=record["work_id"],
                        gutenberg_id=record["gutenberg_id"],
                        title=record.get("display_title") or record["title"],
                        author=display_author(record["author"]),
                        form=record["form"],
                        subjects=record.get("subjects", []),
                        labels=record.get("labels", []),
                        text=clean_display_text(record["text"]),
                        chunk_type=record["chunk_type"],
                        word_count=record["word_count"],
                        work_title=record.get("work_title", record.get("title", "")),
                        display_title=record.get("display_title", record.get("title", "")),
                        section_title=record.get("section_title"),
                        section_index=record.get("section_index"),
                        section_excerpt_index=record.get("section_excerpt_index"),
                        excerpt_label=record.get("excerpt_label"),
                        media=record.get("media", []),
                    )
                )
    except OSError:
        return []
    return excerpts


@lru_cache(maxsize=4)
def _load_database_excerpts(database_url: str) -> list[ProcessedExcerpt]:
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError:
        return []

    try:
        with psycopg.connect(psycopg_dsn(database_url), row_factory=dict_row) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        e.id AS database_excerpt_id,
                        e.external_id AS excerpt_external_id,
                        e.title AS excerpt_title,
                        e.text AS excerpt_text,
                        e.chunk_type,
                        e.word_count,
                        e.source_metadata AS excerpt_metadata,
                        w.external_id AS work_external_id,
                        w.gutenberg_id,
                        w.title AS work_title,
                        w.author,
                        w.form,
                        w.subjects
                    FROM excerpts e
                    JOIN works w ON w.id = e.work_id
                    WHERE w.source = 'gutenberg'
                    ORDER BY w.external_id, e.excerpt_index
                    """
                )
                rows = cursor.fetchall()
                labels_by_excerpt = load_database_labels(cursor)
    except Exception:
        return []

    excerpts: list[ProcessedExcerpt] = []
    for row in rows:
        metadata = ensure_dict(row.get("excerpt_metadata"))
        labels = labels_by_excerpt.get(int(row["database_excerpt_id"]), [])
        work_title = optional_str(metadata.get("work_title")) or optional_str(row.get("work_title")) or ""
        display_title = optional_str(metadata.get("display_title")) or optional_str(
            row.get("excerpt_title")
        ) or work_title
        form = optional_str(metadata.get("form")) or optional_str(row.get("form")) or "unknown"
        subjects = ensure_list(metadata.get("subjects")) or ensure_list(row.get("subjects"))
        text = clean_display_text(str(row.get("excerpt_text") or ""))
        if not text:
            continue
        excerpts.append(
            ProcessedExcerpt(
                id=str(row["excerpt_external_id"]),
                work_id=str(row["work_external_id"]),
                gutenberg_id=str(row.get("gutenberg_id") or metadata.get("gutenberg_id") or ""),
                title=display_title,
                author=display_author(optional_str(row.get("author"))),
                form=form,
                subjects=subjects,
                labels=labels,
                text=text,
                chunk_type=str(row.get("chunk_type") or "excerpt"),
                word_count=optional_int(row.get("word_count")) or len(text.split()),
                work_title=work_title,
                display_title=display_title,
                section_title=optional_str(metadata.get("section_title")),
                section_index=optional_int(metadata.get("section_index")),
                section_excerpt_index=optional_int(metadata.get("section_excerpt_index")),
                excerpt_label=optional_str(metadata.get("excerpt_label")),
            )
        )
    return excerpts


def load_database_labels(cursor: Any) -> dict[int, list[dict[str, str]]]:
    cursor.execute(
        """
        SELECT excerpt_id, label_type, label, evidence
        FROM excerpt_classifications
        ORDER BY excerpt_id, label_type, label
        """
    )
    labels_by_excerpt: dict[int, list[dict[str, str]]] = {}
    for row in cursor.fetchall():
        label = {
            "label_type": str(row.get("label_type") or ""),
            "label": str(row.get("label") or ""),
        }
        evidence = optional_str(row.get("evidence"))
        if evidence:
            label["evidence"] = evidence
        if label["label_type"] and label["label"]:
            labels_by_excerpt.setdefault(int(row["excerpt_id"]), []).append(label)
    return labels_by_excerpt


def psycopg_dsn(database_url: str) -> str:
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return database_url


def ensure_dict(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def ensure_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return [value]
        if isinstance(parsed, list):
            return [str(item) for item in parsed if str(item).strip()]
    return []


def optional_str(value: object) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def clear_processed_corpus_cache() -> None:
    _load_excerpts.cache_clear()
    _load_database_excerpts.cache_clear()
    _load_user_post_excerpts.cache_clear()


def clean_display_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = ITALIC_MARKUP_RE.sub(r"\1", text)
    text = text.replace("_", "")
    text = FOOTNOTE_PAGE_REF_RE.sub("", text)
    cleaned_lines: list[str] = []
    for line in text.splitlines():
        line = FOOTNOTE_RETURN_RE.sub("", line)
        line = re.sub(r"[ \t]+", " ", line).strip()
        cleaned_lines.append(line)
    cleaned = "\n".join(cleaned_lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return trim_front_matter(cleaned).strip()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "unknown"


def tokenize_query(query: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9]+", query.lower())
        if len(token) > 1
    ]


def expand_subject_tags(subject: str) -> set[str]:
    lowered = subject.lower()
    tags = set(tokenize_query(lowered))
    if "love stories" in lowered:
        tags.update({"love", "romance"})
    if "gothic" in lowered:
        tags.add("gothic")
    if "adventure" in lowered:
        tags.add("adventure")
    if "detective" in lowered or "mystery" in lowered:
        tags.add("mystery")
    if "science fiction" in lowered:
        tags.update({"science fiction", "science"})
    if "poetry" in lowered:
        tags.add("poetry")
    return tags


@lru_cache(maxsize=8)
def _load_user_post_excerpts(accounts_path: str) -> list[ProcessedExcerpt]:
    path = Path(accounts_path)
    if not path.exists():
        return []
    try:
        store = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    users = store.get("users", {})
    excerpts: list[ProcessedExcerpt] = []
    for post in store.get("posts", {}).values():
        if post.get("visibility") != "public":
            continue
        author_record = users.get(post.get("author_user_id"))
        if not author_record:
            continue
        if author_record.get("profile_metadata", {}).get("account_visibility") == "private":
            continue
        title = " ".join(str(post.get("title", "Untitled post")).split()) or "Untitled post"
        body = clean_display_text(str(post.get("body", ""))).strip()
        if not body:
            continue
        form = str(post.get("form") or "prose").strip().lower() or "prose"
        word_count = int(post.get("word_count") or len(body.split()))
        excerpts.append(
            ProcessedExcerpt(
                id=str(post.get("id")),
                work_id=str(post.get("id")),
                gutenberg_id="user",
                title=title,
                author=display_author(str(author_record.get("display_name") or "Reader")),
                form=form,
                subjects=["user post", "contemporary writing"],
                labels=[
                    {"label_type": "form", "label": form},
                    {"label_type": "source", "label": "user_post"},
                ],
                text=body,
                chunk_type="user_post",
                word_count=word_count,
                work_title=title,
                display_title=title,
                excerpt_label="Post",
                media=clean_user_post_media(post.get("media")),
            )
        )
    return sorted(excerpts, key=lambda excerpt: excerpt.id, reverse=True)


def clean_user_post_media(value: object) -> list[dict[str, str | None]]:
    if not isinstance(value, list):
        return []
    media: list[dict[str, str | None]] = []
    for item in value[:4]:
        if not isinstance(item, dict):
            continue
        media_type = str(item.get("media_type") or "")
        data_url = str(item.get("data_url") or "")
        if media_type not in {"image", "video"}:
            continue
        if not is_renderable_media_reference(data_url, media_type):
            continue
        media.append(
            {
                "id": str(item.get("id") or f"media-{len(media) + 1}")[:128],
                "media_type": media_type,
                "data_url": data_url,
                "alt_text": clean_optional_media_text(item.get("alt_text"), 180),
                "caption": clean_optional_media_text(item.get("caption"), 240),
            }
        )
    return media


def is_renderable_media_reference(value: str, media_type: str) -> bool:
    if value.startswith(f"data:{media_type}/"):
        return True
    return value.startswith(("http://", "https://", "/media/"))


def clean_optional_media_text(value: object, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())
    return cleaned[:limit] or None
