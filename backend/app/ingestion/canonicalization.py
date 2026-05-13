from __future__ import annotations

import re
import unicodedata


ROLE_MARKER_RE = re.compile(r"\s*\[[^\]]+\]")
AUTHOR_DATES_RE = re.compile(
    r"\b(?:c\.?\s*)?\d{1,4}\??\s*(?:bce|bc|ce|ad)?\s*"
    r"(?:-|–|—|to|b\.|d\.)\s*(?:c\.?\s*)?\d{0,4}\??\s*"
    r"(?:bce|bc|ce|ad)?\b|\b(?:c\.?\s*)?\d{1,4}\??\s*(?:bce|bc|ce|ad)\b",
    re.IGNORECASE,
)
BRACKETED_EDITION_RE = re.compile(
    r"\s*[\[(][^\])]*(?:edition|illustrated|vols?\.?|volume|translated|edited)[^\])]*[\])]",
    re.IGNORECASE,
)
TRAILING_EDITION_RE = re.compile(
    r"\b(?:revised|illustrated|cambridge|one volume|edition|ed\.)\b.*$",
    re.IGNORECASE,
)
GENERIC_SUBTITLE_RE = re.compile(
    r"(?i)\s*(?:[:;]\s*)?(?:or,\s*)?"
    r"(?:a|an|the)?\s*"
    r"(?:novel|romance|tale|story|comedy|tragedy|farce|play|poem|drama)"
    r"(?:\s+in\s+.*)?$"
)
PARENTHETICAL_SUBTITLE_RE = re.compile(r"\s*\([^)]{1,80}\)\s*$")
SERIAL_PREFIX_RE = re.compile(r"(?i)\b(?:tom swift|roy blakeley|rover boys|motor girls)\b")
MONONYM_AUTHOR_KEYS = {
    "aesop",
    "aristophanes",
    "euripides",
    "hesiod",
    "homer",
    "kalidasa",
    "sappho",
    "sophocles",
    "theocritus",
    "virgil",
}


def canonical_author(author: str | None) -> str:
    return normalize_key(display_author(author)) or "unknown"


def display_author(author: str | None) -> str:
    if not author:
        return "Unknown"
    without_roles = ROLE_MARKER_RE.sub("", author)
    raw_parts = [part.strip() for part in without_roles.split(",") if part.strip()]
    if "[translator]" in author.lower() and raw_parts and normalize_key(raw_parts[0]) in MONONYM_AUTHOR_KEYS:
        return clean_author_part(raw_parts[0]) or "Unknown"
    if len(raw_parts) >= 2 and not looks_like_life_dates(raw_parts[1]):
        first_author = f"{clean_author_part(raw_parts[1])} {clean_author_part(raw_parts[0])}"
    elif raw_parts:
        first_author = clean_author_part(raw_parts[0])
    else:
        first_author = without_roles
    first_author = AUTHOR_DATES_RE.sub("", first_author)
    first_author = re.sub(r"\s+", " ", first_author).strip(" ,;")
    return first_author or "Unknown"


def canonical_title(title: str | None) -> str:
    if not title:
        return "untitled"
    cleaned = title.strip()
    cleaned = BRACKETED_EDITION_RE.sub("", cleaned)
    cleaned = PARENTHETICAL_SUBTITLE_RE.sub("", cleaned)
    cleaned = TRAILING_EDITION_RE.sub("", cleaned)
    cleaned = re.sub(r"(?i)\s+with\s+(?:a\s+)?(?:proem|introduction|notes|illustrations).*$", "", cleaned)
    cleaned = re.sub(r"(?i)\s+translated\s+.*$", "", cleaned)
    cleaned = re.sub(r"(?i)\s+retold\s+.*$", "", cleaned)
    cleaned = GENERIC_SUBTITLE_RE.sub("", cleaned)
    key = normalize_key(cleaned)
    key = re.sub(r"^(?:the|a|an)\s+", "", key)
    return key or "untitled"


def looks_like_life_dates(value: str) -> bool:
    lowered = value.lower()
    return bool(re.search(r"\d{3,4}", lowered)) or "bce" in lowered or "ce" in lowered


def clean_author_part(value: str) -> str:
    cleaned = AUTHOR_DATES_RE.sub("", value)
    cleaned = ROLE_MARKER_RE.sub("", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip(" ,;")


def canonical_work_key(author: str | None, title: str | None) -> str:
    return f"{canonical_author(author)}::{canonical_title(title)}"


def edition_noise_score(title: str | None) -> int:
    if not title:
        return 10
    lowered = title.lower()
    score = 0
    for marker in (
        "illustrated",
        "edition",
        "retold",
        "adapted",
        "selections",
        "selected",
        "translated",
        "cambridge",
        "vol.",
        "volume",
        "complete works",
    ):
        if marker in lowered:
            score += 1
    if SERIAL_PREFIX_RE.search(lowered):
        score += 1
    return score


def normalize_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_value = ascii_value.replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", " ", ascii_value.lower()).strip()
