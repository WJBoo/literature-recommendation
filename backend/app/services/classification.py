from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class ClassificationLabel:
    label_type: str
    label: str
    evidence: str


GENRE_KEYWORDS = {
    "romance": {"love", "marriage", "courtship", "heart", "beloved", "affection"},
    "gothic": {"terror", "horror", "castle", "ghost", "dread", "grave", "monster", "gothic"},
    "epic": {"hero", "battle", "gods", "king", "war", "fate", "voyage"},
    "philosophy": {"truth", "virtue", "reason", "soul", "justice", "morality"},
    "satire": {"folly", "ridicule", "absurd", "vanity", "wit"},
    "nature": {"sea", "forest", "river", "mountain", "flower", "wind", "sky"},
}

MOOD_KEYWORDS = {
    "melancholic": {"sorrow", "grief", "tears", "mourning", "lonely"},
    "comic": {"laugh", "jest", "comic", "amusing", "mirth"},
    "dramatic": {"cry", "rage", "blood", "storm", "death"},
    "contemplative": {"thought", "mind", "memory", "dream", "silence"},
}


def classify_excerpt(text: str, form: str, subjects: list[str] | None = None) -> list[ClassificationLabel]:
    normalized_text = text.lower()
    subject_text = " ".join(subjects or []).lower()
    searchable = f"{normalized_text} {subject_text}"
    labels: list[ClassificationLabel] = [
        ClassificationLabel(label_type="form", label=form.lower(), evidence="work metadata")
    ]

    labels.extend(_match_keywords("genre", searchable, GENRE_KEYWORDS))
    labels.extend(_match_keywords("mood", searchable, MOOD_KEYWORDS))
    return _dedupe(labels)


def _match_keywords(
    label_type: str, searchable: str, keyword_map: dict[str, set[str]]
) -> list[ClassificationLabel]:
    labels: list[ClassificationLabel] = []
    for label, keywords in keyword_map.items():
        matches = sorted(keyword for keyword in keywords if re.search(rf"\b{re.escape(keyword)}\b", searchable))
        if matches:
            labels.append(
                ClassificationLabel(
                    label_type=label_type,
                    label=label,
                    evidence=", ".join(matches[:5]),
                )
            )
    return labels


def _dedupe(labels: list[ClassificationLabel]) -> list[ClassificationLabel]:
    seen: set[tuple[str, str]] = set()
    deduped: list[ClassificationLabel] = []
    for label in labels:
        key = (label.label_type, label.label)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(label)
    return deduped
