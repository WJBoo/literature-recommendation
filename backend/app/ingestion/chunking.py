from __future__ import annotations

from dataclasses import dataclass, replace
import re


PROSE_MIN_WORDS = 300
PROSE_TARGET_WORDS = 700
PROSE_MAX_WORDS = 900
POEM_MAX_INTACT_WORDS = 1500
POEM_HEADING_RE = re.compile(r"^(?:[IVXLCDM]{1,12}|[0-9]{1,4})\.?$")
PROSE_SECTION_HEADING_RE = re.compile(
    r"^(?:"
    r"CHAPTER\s+[IVXLCDM0-9]+\.?(?:\s+.*)?|"
    r"Chapter\s+[IVXLCDM0-9]+\.?(?:\s+.*)?|"
    r"Letter\s+[IVXLCDM0-9]+\.?(?:\s+.*)?|"
    r"BOOK\s+(?:THE\s+)?[A-ZIVXLCDM0-9]+.*|"
    r"Book\s+the\s+.+"
    r")$"
)


@dataclass(frozen=True)
class TextChunk:
    text: str
    chunk_type: str
    word_count: int
    start_offset: int | None = None
    end_offset: int | None = None
    section_title: str | None = None
    section_index: int | None = None
    excerpt_index_in_section: int | None = None


@dataclass(frozen=True)
class ProseSection:
    text: str
    title: str | None
    index: int | None = None


def count_words(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text))


def chunk_text(text: str, form: str) -> list[TextChunk]:
    normalized_form = form.lower().strip()
    if normalized_form in {"poem", "poetry"}:
        return chunk_poem(text)
    return chunk_prose(text)


def chunk_poem(text: str) -> list[TextChunk]:
    poem_units = _split_poem_collection(text)
    if len(poem_units) > 1:
        chunks: list[TextChunk] = []
        for index, unit in enumerate(poem_units, start=1):
            section_title = _poem_unit_title(unit, index)
            unit_word_count = count_words(unit)
            if unit_word_count <= POEM_MAX_INTACT_WORDS:
                chunks.append(
                    TextChunk(
                        text=unit.strip(),
                        chunk_type="full_poem",
                        word_count=unit_word_count,
                        section_title=section_title,
                        section_index=index,
                        excerpt_index_in_section=1,
                    )
                )
            else:
                chunks.extend(_with_section_metadata(_chunk_long_poem(unit), section_title, index))
        return chunks

    word_count = count_words(text)
    if word_count <= POEM_MAX_INTACT_WORDS:
        section_title = _poem_unit_title(text, 1)
        return [
            TextChunk(
                text=text.strip(),
                chunk_type="full_poem",
                word_count=word_count,
                start_offset=0,
                end_offset=len(text),
                section_title=section_title,
                section_index=1 if section_title else None,
                excerpt_index_in_section=1,
            )
        ]

    return _with_section_metadata(_chunk_long_poem(text), None, None)


def _split_poem_collection(text: str) -> list[str]:
    stanzas = [stanza.strip() for stanza in re.split(r"\n\s*\n", text) if stanza.strip()]
    heading_indices = [index for index, stanza in enumerate(stanzas) if _is_poem_heading(stanza)]
    if len(heading_indices) < 2:
        return []

    starts = heading_indices if heading_indices[0] == 0 else [0, *heading_indices]
    units: list[str] = []
    for start_index, start in enumerate(starts):
        end = starts[start_index + 1] if start_index + 1 < len(starts) else len(stanzas)
        unit = "\n\n".join(stanzas[start:end]).strip()
        if count_words(unit) > 0:
            units.append(unit)
    return units


def _is_poem_heading(stanza: str) -> bool:
    return "\n" not in stanza and POEM_HEADING_RE.fullmatch(stanza.strip()) is not None


def _poem_unit_title(unit: str, fallback_index: int) -> str | None:
    first_line = next((line.strip() for line in unit.splitlines() if line.strip()), "")
    if not first_line:
        return None
    if POEM_HEADING_RE.fullmatch(first_line):
        number = _heading_number(first_line) or fallback_index
        return f"Poem {number}"
    return None


def _heading_number(value: str) -> int | None:
    normalized = value.strip().strip(".")
    if normalized.isdigit():
        return int(normalized)
    return roman_to_int(normalized)


def roman_to_int(value: str) -> int | None:
    numerals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total = 0
    previous = 0
    for character in reversed(value.upper()):
        current = numerals.get(character)
        if current is None:
            return None
        if current < previous:
            total -= current
        else:
            total += current
            previous = current
    return total or None


def _with_section_metadata(
    chunks: list[TextChunk],
    section_title: str | None,
    section_index: int | None,
) -> list[TextChunk]:
    return [
        replace(
            chunk,
            section_title=section_title,
            section_index=section_index,
            excerpt_index_in_section=index,
        )
        for index, chunk in enumerate(chunks, start=1)
    ]


def _chunk_long_poem(text: str) -> list[TextChunk]:
    stanzas = [stanza.strip() for stanza in re.split(r"\n\s*\n", text) if stanza.strip()]
    chunks: list[TextChunk] = []
    current: list[str] = []
    current_words = 0

    for stanza in stanzas:
        stanza_words = count_words(stanza)
        if stanza_words > POEM_MAX_INTACT_WORDS:
            if current:
                chunk_body = "\n\n".join(current)
                chunks.append(
                    TextChunk(
                        text=chunk_body,
                        chunk_type="poem_section",
                        word_count=count_words(chunk_body),
                    )
                )
                current = []
                current_words = 0
            chunks.extend(_split_long_poem_block(stanza))
            continue

        if current and current_words + stanza_words > POEM_MAX_INTACT_WORDS:
            chunk_body = "\n\n".join(current)
            chunks.append(
                TextChunk(
                    text=chunk_body,
                    chunk_type="poem_section",
                    word_count=count_words(chunk_body),
                )
            )
            current = []
            current_words = 0

        current.append(stanza)
        current_words += stanza_words

    if current:
        chunk_body = "\n\n".join(current)
        chunks.append(
            TextChunk(text=chunk_body, chunk_type="poem_section", word_count=count_words(chunk_body))
        )

    return chunks


def _split_long_poem_block(block: str) -> list[TextChunk]:
    lines = [line for line in block.splitlines() if line.strip()]
    chunks: list[TextChunk] = []
    current: list[str] = []
    current_words = 0

    for line in lines:
        line_words = count_words(line)
        if line_words > POEM_MAX_INTACT_WORDS:
            if current:
                chunk_body = "\n".join(current)
                chunks.append(
                    TextChunk(
                        text=chunk_body,
                        chunk_type="poem_section",
                        word_count=count_words(chunk_body),
                    )
                )
                current = []
                current_words = 0
            chunks.extend(_split_words(line, "poem_section", POEM_MAX_INTACT_WORDS))
            continue

        if current and current_words + line_words > POEM_MAX_INTACT_WORDS:
            chunk_body = "\n".join(current)
            chunks.append(
                TextChunk(text=chunk_body, chunk_type="poem_section", word_count=count_words(chunk_body))
            )
            current = []
            current_words = 0

        current.append(line)
        current_words += line_words

    if current:
        chunk_body = "\n".join(current)
        chunks.append(
            TextChunk(text=chunk_body, chunk_type="poem_section", word_count=count_words(chunk_body))
        )

    return chunks


def chunk_prose(text: str) -> list[TextChunk]:
    sections = _split_prose_sections(text)
    if len(sections) > 1 or sections[0].title:
        chunks: list[TextChunk] = []
        for section in sections:
            section_chunks = _chunk_prose_block(section.text)
            chunks.extend(_with_section_metadata(section_chunks, section.title, section.index))
        return chunks

    return _chunk_prose_block(text)


def _chunk_prose_block(text: str) -> list[TextChunk]:
    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", text) if paragraph.strip()]
    chunks: list[TextChunk] = []
    current: list[str] = []
    current_words = 0

    for paragraph in paragraphs:
        paragraph_words = count_words(paragraph)
        should_flush = current and current_words >= PROSE_MIN_WORDS
        would_exceed = current_words + paragraph_words > PROSE_MAX_WORDS

        if should_flush and would_exceed:
            chunk_body = "\n\n".join(current)
            chunks.append(
                TextChunk(
                    text=chunk_body,
                    chunk_type="prose_excerpt",
                    word_count=count_words(chunk_body),
                )
            )
            current = []
            current_words = 0

        if paragraph_words > PROSE_MAX_WORDS:
            if current:
                chunk_body = "\n\n".join(current)
                chunks.append(
                    TextChunk(
                        text=chunk_body,
                        chunk_type="prose_excerpt",
                        word_count=count_words(chunk_body),
                    )
                )
                current = []
                current_words = 0
            chunks.extend(_split_long_paragraph(paragraph))
            continue

        current.append(paragraph)
        current_words += paragraph_words

        if current_words >= PROSE_TARGET_WORDS:
            chunk_body = "\n\n".join(current)
            chunks.append(
                TextChunk(
                    text=chunk_body,
                    chunk_type="prose_excerpt",
                    word_count=count_words(chunk_body),
                )
            )
            current = []
            current_words = 0

    if current:
        chunk_body = "\n\n".join(current)
        chunks.append(
            TextChunk(text=chunk_body, chunk_type="prose_excerpt", word_count=count_words(chunk_body))
        )

    return chunks


def _split_prose_sections(text: str) -> list[ProseSection]:
    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", text) if paragraph.strip()]
    if not paragraphs:
        return [ProseSection(text=text.strip(), title=None, index=None)]

    sections: list[ProseSection] = []
    current_title: str | None = None
    current_paragraphs: list[str] = []
    current_index = 1

    for paragraph in paragraphs:
        if _is_prose_section_heading(paragraph):
            if current_paragraphs:
                title = current_title or _infer_previous_section_title(paragraph)
                sections.append(
                    ProseSection(
                        text="\n\n".join(current_paragraphs),
                        title=title,
                        index=current_index if title else None,
                    )
                )
                current_index += 1
            current_title = _normalize_prose_section_heading(paragraph)
            current_paragraphs = [paragraph]
            continue

        current_paragraphs.append(paragraph)

    if current_paragraphs:
        sections.append(
            ProseSection(
                text="\n\n".join(current_paragraphs),
                title=current_title,
                index=current_index if current_title else None,
            )
        )

    if len(sections) <= 1 and sections[0].title is None:
        return [ProseSection(text=text.strip(), title=None, index=None)]
    return sections


def _is_prose_section_heading(paragraph: str) -> bool:
    normalized = " ".join(paragraph.split())
    return "\n" not in paragraph and len(normalized) <= 100 and bool(PROSE_SECTION_HEADING_RE.match(normalized))


def _normalize_prose_section_heading(paragraph: str) -> str:
    normalized = " ".join(paragraph.split()).strip().rstrip(".")
    if normalized.lower().startswith("chapter "):
        return f"Chapter {normalized.split(' ', 1)[1]}"
    if normalized.lower().startswith("letter "):
        return f"Letter {normalized.split(' ', 1)[1]}"
    if normalized.lower().startswith("book "):
        return normalized[:1].upper() + normalized[1:]
    return normalized


def _infer_previous_section_title(next_heading: str) -> str | None:
    normalized = _normalize_prose_section_heading(next_heading)
    match = re.match(r"^(Chapter|Letter)\s+([IVXLCDM0-9]+)", normalized, flags=re.IGNORECASE)
    if not match:
        return None

    prefix, raw_number = match.groups()
    number = _heading_number(raw_number)
    if number != 2:
        return None

    if raw_number.isdigit():
        previous = "1"
    else:
        previous = "I"
    return f"{prefix[:1].upper() + prefix[1:].lower()} {previous}"


def _split_long_paragraph(paragraph: str) -> list[TextChunk]:
    sentences = re.split(r"(?<=[.!?])\s+", paragraph)
    chunks: list[TextChunk] = []
    current: list[str] = []
    current_words = 0

    for sentence in sentences:
        sentence_words = count_words(sentence)
        if current and current_words + sentence_words > PROSE_MAX_WORDS:
            chunk_body = " ".join(current)
            chunks.append(
                TextChunk(
                    text=chunk_body,
                    chunk_type="prose_excerpt",
                    word_count=count_words(chunk_body),
                )
            )
            current = []
            current_words = 0

        current.append(sentence)
        current_words += sentence_words

    if current:
        chunk_body = " ".join(current)
        chunks.append(
            TextChunk(text=chunk_body, chunk_type="prose_excerpt", word_count=count_words(chunk_body))
        )

    return chunks


def _split_words(text: str, chunk_type: str, max_words: int) -> list[TextChunk]:
    words = text.split()
    chunks = []
    for start in range(0, len(words), max_words):
        chunk_words = words[start : start + max_words]
        chunk_body = " ".join(chunk_words)
        chunks.append(
            TextChunk(text=chunk_body, chunk_type=chunk_type, word_count=count_words(chunk_body))
        )
    return chunks
