from __future__ import annotations

from dataclasses import dataclass
import re

from app.ingestion.cleaning import (
    looks_like_front_matter_apparatus,
    looks_like_front_matter_list,
)
from app.services.processed_corpus import ProcessedExcerpt


WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]{1,}")
HEADER_ONLY_RE = re.compile(
    r"^\W*(?:(?:chapter|book|act|scene|section|poem|letter|canto)\s+)?"
    r"(?:[ivxlcdm]+|\d+)\.?\W*$|^\W*(?:the\s+end|finis)\W*$|^[\W_]+$",
    re.IGNORECASE,
)
TOC_ITEM_RE = re.compile(
    r"\b(?:chapter|letter|scene|act|book|canto|poem)\s+(?:[ivxlcdm]+|\d+)\b",
    re.IGNORECASE,
)
BOILERPLATE_START_RE = re.compile(
    r"^\W*(?:"
    r"produced by|"
    r"e-?text prepared by|"
    r"this ebook was produced by|"
    r"transcriber's note|"
    r"transcriber’s note|"
    r"note:\s*project gutenberg|"
    r"project gutenberg"
    r")",
    re.IGNORECASE,
)
TITLE_PAGE_RE = re.compile(
    r"\b(?:copyright|all rights reserved|published by|publisher|printed by|"
    r"macmillan|harper\s*&|new york|london:|new edition|illustrations|edited by|"
    r"author of|introduction by|with introduction|retold in modern prose|"
    r"unrepresented in)\b",
    re.IGNORECASE,
)
ADVERTISING_RE = re.compile(
    r"(?:\$\d|by mail|net\.|thousand sold|popular books|fifth impression|"
    r"new york times|boston transcript|press says|not since the famous|"
    r"outstanding (?:story|novel|book)|do not fail to read|well-known author|"
    r"will be discussed)",
    re.IGNORECASE,
)
APPARATUS_START_RE = re.compile(
    r"^[\W_]*(?:notes?|preface|foreword|introduction|bibliography|appendix|"
    r"glossary|index|frontispiece|editorial note|expanded version|"
    r"fac-?simile|modernised version|modernized version|"
    r"medi[æe]val black-letter|black-letter)\b",
    re.IGNORECASE,
)
CRITICAL_APPARATUS_RE = re.compile(
    r"(?:history and criticism|literary inquiry|critical study|study and teaching|"
    r"bibliograph|modern language association|the macmillan company|"
    r"early english text society|publication[s]? of the modern language|"
    r"critics? (?:have|never|would)|scholars have|has been edited by|translated from|"
    r"for critical studies|for information regarding|readers of .+ will recall|"
    r"source was for .* romances|deep interest to the student)",
    re.IGNORECASE,
)
INDEX_PAGE_REF_RE = re.compile(r"^[\s\"“”']*[A-Za-z][A-Za-z .'\-()]{0,80},\s*\d{1,4}(?:[-,]\s*\d{1,4})*", re.MULTILINE)
PUBLISHER_LINE_RE = re.compile(
    r"^\s*(?:new york|london|boston|chicago|philadelphia|paris)\s*:|"
    r"^\s*(?:new york|london|boston|chicago|philadelphia|paris)\s*$|"
    r"\b(?:published by|printed by|for private circulation|the .* press|"
    r"copyright,?\s+\d{4}|all rights reserved)\b",
    re.IGNORECASE | re.MULTILINE,
)

BOILERPLATE_MARKERS = (
    "produced by",
    "e-text prepared",
    "etext prepared",
    "online distributed proofreading",
    "project gutenberg",
    "pgdp.net",
    "transcriber's note",
    "transcriber’s note",
    "html version",
    "this ebook",
    "gutenberg volunteers",
)
APPARATUS_CONTEXT_TERMS = (
    "author",
    "authors",
    "addison",
    "art",
    "character-creation",
    "characters",
    "composition",
    "critic",
    "critics",
    "description",
    "edition",
    "editor",
    "fielding",
    "genius",
    "hero",
    "heroine",
    "heroines",
    "humour",
    "introduction",
    "literary",
    "miss austen",
    "novel",
    "novelist",
    "novels",
    "preface",
    "reader",
    "readers",
    "swift",
    "thackeray",
    "translator",
    "volume",
)


@dataclass(frozen=True)
class ExcerptQuality:
    score: float
    recommendable: bool
    reasons: tuple[str, ...]


def assess_excerpt_quality(excerpt: ProcessedExcerpt) -> ExcerptQuality:
    text = " ".join(excerpt.text.split())
    lowered = text.lower()
    first_300 = lowered[:300]
    first_800 = lowered[:800]
    first_1200 = lowered[:1200]
    metadata_text = " ".join(
        [
            excerpt.title,
            excerpt.work_title,
            excerpt.section_title or "",
            " ".join(excerpt.subjects),
        ]
    ).lower()
    words = WORD_RE.findall(text)
    word_count = len(words)
    reasons: list[str] = []

    if word_count < 35:
        reasons.append("too_short")
    if HEADER_ONLY_RE.match(text):
        reasons.append("header_only")

    boilerplate_hits = sum(marker in first_800 for marker in BOILERPLATE_MARKERS)
    if (
        BOILERPLATE_START_RE.search(text)
        or boilerplate_hits >= 2
        or "transcriber's note" in first_1200
        or "transcriber’s note" in first_1200
    ):
        reasons.append("gutenberg_boilerplate")

    toc_items = len(TOC_ITEM_RE.findall(text[:900]))
    has_contents = "contents" in first_300 or "table of contents" in first_800
    if has_contents and toc_items >= 4:
        reasons.append("table_of_contents")
    if looks_like_front_matter_list(excerpt.text):
        reasons.append("table_of_contents")
    if looks_like_index_or_catalog(text, first_800=first_800):
        reasons.append("index_or_catalog")

    if TITLE_PAGE_RE.search(first_800) and (
        sentence_count(text) < 3 or uppercase_word_share(words[:60]) > 0.34
    ):
        reasons.append("title_or_copyright_page")
    raw_first_1200 = excerpt.text[:1200]
    raw_first_1200_lower = raw_first_1200.lower()
    if PUBLISHER_LINE_RE.search(raw_first_1200) and (
        "for private circulation" in raw_first_1200_lower
        or re.search(r"\n\s*by\s*\n", raw_first_1200_lower)
        or sentence_count(text[:1200]) < 4
    ):
        reasons.append("title_or_copyright_page")
    if looks_like_front_matter_title_page(text, excerpt):
        reasons.append("title_or_copyright_page")
    if ADVERTISING_RE.search(first_800):
        reasons.append("advertising_or_review")
    if looks_like_critical_apparatus(
        text,
        lowered=lowered,
        first_800=first_800,
        metadata_text=metadata_text,
        form=excerpt.form,
    ):
        reasons.append("critical_apparatus")
    if looks_like_front_matter_apparatus(excerpt.text):
        reasons.append("critical_apparatus")
    if excerpt.form.lower() in {"prose", "drama"} and sentence_count(text) == 0 and word_count < 180:
        reasons.append("fragment_like")
    if excerpt.form.lower() == "poetry" and sentence_count(text) >= 2 and poetic_line_count(excerpt.text) < 3:
        reasons.append("editorial_poetry_metadata")
    if excerpt.form.lower() == "poetry" and looks_like_prose_commentary(excerpt.text):
        reasons.append("poetry_prose_commentary")

    hard_reasons = {
        "too_short",
        "header_only",
        "gutenberg_boilerplate",
        "table_of_contents",
        "index_or_catalog",
        "title_or_copyright_page",
        "advertising_or_review",
        "critical_apparatus",
        "fragment_like",
        "editorial_poetry_metadata",
        "poetry_prose_commentary",
    }
    score = 0.82
    if word_count >= 120:
        score += 0.12
    elif word_count < 80:
        score -= 0.10

    if sentence_count(text) >= 3:
        score += 0.08
    elif excerpt.form.lower() != "poetry":
        score -= 0.16

    if excerpt.form.lower() == "poetry" and poetic_line_count(excerpt.text) >= 4:
        score += 0.08

    if boilerplate_hits:
        score -= min(0.55, boilerplate_hits * 0.22)
    if has_contents:
        score -= 0.25
    if TITLE_PAGE_RE.search(first_800):
        score -= 0.25
    if ADVERTISING_RE.search(first_800):
        score -= 0.45
    if CRITICAL_APPARATUS_RE.search(first_1200):
        score -= 0.38
    if separator_ratio(text) > 0.08:
        score -= 0.18
    if uppercase_word_share(words[:60]) > 0.6:
        score -= 0.12

    score = max(0.0, min(1.0, score))
    return ExcerptQuality(
        score=score,
        recommendable=not hard_reasons.intersection(reasons),
        reasons=tuple(reasons),
    )


def quality_score_adjustment(excerpt: ProcessedExcerpt) -> float:
    return quality_score_adjustment_from_assessment(assess_excerpt_quality(excerpt))


def quality_score_adjustment_from_assessment(quality: ExcerptQuality) -> float:
    if not quality.recommendable:
        return -10.0
    return (quality.score - 0.72) * 0.85


def is_recommendable_excerpt(excerpt: ProcessedExcerpt) -> bool:
    return assess_excerpt_quality(excerpt).recommendable


def looks_like_critical_apparatus(
    text: str,
    *,
    lowered: str,
    first_800: str,
    metadata_text: str,
    form: str,
) -> bool:
    if APPARATUS_START_RE.search(text) and sentence_count(text) >= 2:
        return True
    if "history and criticism" in metadata_text:
        return True
    if "literary inquiry" in metadata_text:
        return True
    if CRITICAL_APPARATUS_RE.search(first_800):
        return True
    if apparatus_context_score(lowered[:3500]) >= 7 and sentence_count(text[:3500]) >= 3:
        return True
    if form.lower() == "poetry" and CRITICAL_APPARATUS_RE.search(lowered[:1500]):
        return True
    return False


def apparatus_context_score(text: str) -> int:
    return sum(1 for term in APPARATUS_CONTEXT_TERMS if term in text)


def looks_like_prose_commentary(text: str) -> bool:
    lines = [line for line in text.splitlines() if WORD_RE.findall(line)]
    if len(lines) < 4 or sentence_count(text) < 3:
        return False
    line_word_counts = [len(WORD_RE.findall(line)) for line in lines[:12]]
    average_line_words = sum(line_word_counts) / len(line_word_counts)
    long_line_share = len([count for count in line_word_counts if count >= 9]) / len(line_word_counts)
    return average_line_words >= 9 and long_line_share >= 0.55


def looks_like_index_or_catalog(text: str, *, first_800: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(INDEX_PAGE_REF_RE.findall("\n".join(lines[:40]))) >= 4:
        return True
    page_ref_lines = [
        line
        for line in lines[:50]
        if re.search(r",\s*\d{2,4}\b", line) and len(WORD_RE.findall(line)) <= 12
    ]
    if len(page_ref_lines) >= 5:
        return True
    if ("index" in first_800 or "glossary" in first_800) and len(page_ref_lines) >= 2:
        return True
    return False


def looks_like_front_matter_title_page(text: str, excerpt: ProcessedExcerpt) -> bool:
    if not excerpt.work_title:
        return False
    start = normalize_title_probe(text[:500])
    title = normalize_title_probe(excerpt.work_title)
    if len(title) < 10:
        return False
    title_prefix = title[: min(len(title), 80)].strip()
    if start.startswith(title_prefix) and sentence_count(text[:700]) < 4:
        return True
    return False


def normalize_title_probe(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def sentence_count(text: str) -> int:
    return len(re.findall(r"[.!?](?:\s|$)", text))


def poetic_line_count(text: str) -> int:
    return len([line for line in text.splitlines() if len(WORD_RE.findall(line)) >= 2])


def separator_ratio(text: str) -> float:
    if not text:
        return 1.0
    separators = sum(1 for char in text if not char.isalnum() and not char.isspace())
    return separators / max(len(text), 1)


def uppercase_word_share(words: list[str]) -> float:
    if not words:
        return 0.0
    uppercase_words = [word for word in words if len(word) > 2 and word.isupper()]
    return len(uppercase_words) / len(words)
