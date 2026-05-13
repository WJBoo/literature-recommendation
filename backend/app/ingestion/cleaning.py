import re

from bs4 import BeautifulSoup


START_MARKERS = [
    "*** START OF THE PROJECT GUTENBERG EBOOK",
    "*** START OF THIS PROJECT GUTENBERG EBOOK",
]
END_MARKERS = [
    "*** END OF THE PROJECT GUTENBERG EBOOK",
    "*** END OF THIS PROJECT GUTENBERG EBOOK",
]
ILLUSTRATION_BLOCK_RE = re.compile(r"\n?\[Illustration\b[\s\S]*?(?:\]\]|\])\s*", re.IGNORECASE)
FOOTNOTE_BODY_RE = re.compile(r"(?ms)^\s*\[\d+\]\s+.*?(?=\n\n\S|\Z)")
INLINE_FOOTNOTE_RE = re.compile(r"\[\d+\]")
PAGE_MARKER_RE = re.compile(r"(?m)^\s*\[[ivxlcdm\d]+\]\s*$")
BRACE_NOTE_RE = re.compile(r"\n?\{[^{}]{0,1500}\}\s*", re.MULTILINE)
ITALIC_MARKUP_RE = re.compile(r"(?<!\w)_([^_\n]{1,240})_(?!\w)")
FOOTNOTE_PAGE_REF_RE = re.compile(r"(?<=\w),\s+\d{1,4}(?=(?:\s|[.;:,!?])|$)")
NIND_MARKUP_RE = re.compile(r"/\*\s*NIND\s*|\s*\*/", re.IGNORECASE)

FRONT_MATTER_SCAN_LIMIT = 70000
BACK_MATTER_MIN_FRACTION = 0.55
PARAGRAPH_RE = re.compile(r"\S[\s\S]*?(?=\n\s*\n|\Z)")
WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")
SENTENCE_MARK_RE = re.compile(r"[.!?]")
BODY_START_HEADING_RE = re.compile(
    r"(?im)^\s*(?:"
    r"(?:chapter|book|part|letter|canto|act|scene)\s+"
    r"(?:[ivxlcdm]+|\d+|one|two|three|four|five|six|seven|eight|nine|ten)"
    r"(?:[.\s:;-].*)?"
    r"|fit\s+the\s+(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)"
    r"|[IVXLCDM]{1,12}\.?"
    r")\s*$"
)
BARE_BODY_HEADING_RE = re.compile(
    r"(?i)^(?:(?:chapter|book|part|letter|canto|act|scene)\s+"
    r"(?:[ivxlcdm]+|\d+|one|two|three|four|five|six|seven|eight|nine|ten)"
    r"|fit\s+the\s+(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth))\.?$"
)
FRONT_MATTER_HEADING_RE = re.compile(
    r"(?im)^\s*(?:"
    r"preface|introduction|introductory|contents?|table of contents|"
    r"list of illustrations|illustrations?|frontispiece|title-?page|dedication|"
    r"advertisement|publisher'?s note|editor'?s note|translator'?s note|"
    r"transcriber'?s note|memoir|biographical notice"
    r")\.?\s*$"
)
FRONT_MATTER_TERM_RE = re.compile(
    r"\b(?:preface|introduction|contents|table of contents|list of illustrations|"
    r"frontispiece|title-page|dedication|publisher|published by|printed by|"
    r"copyright|all rights reserved|press|transcriber|proofreader)\b",
    re.IGNORECASE,
)
TITLE_PAGE_PUBLICATION_RE = re.compile(
    r"(?im)^\s*(?:"
    r"by\b|with\s+(?:a\s+)?preface\b|with\s+illustrations\b|illustrated\s+by\b|"
    r"translated\s+by\b|edited\s+by\b|london\b|new york\b|boston\b|"
    r"copyright\b|published\b|printed\b|press\b|publisher\b"
    r")"
)
CONTENTS_HEADING_RE = re.compile(
    r"(?im)^\s*(?:contents?|table of contents|list of illustrations|page)\.?\s*$"
)
APPARATUS_CONTEXT_TERMS = {
    "addison",
    "author",
    "authors",
    "chapter headings",
    "character-creation",
    "characters",
    "composition",
    "critic",
    "critics",
    "edition",
    "editor",
    "fielding",
    "genius",
    "hero",
    "heroine",
    "heroines",
    "illustrations",
    "introduction",
    "literary",
    "line",
    "miss austen",
    "novel",
    "novelist",
    "novels",
    "poem",
    "preface",
    "pronounce",
    "reader",
    "readers",
    "translator",
    "writing",
    "writings",
}
CATALOG_HEADING_RE = re.compile(
    r"(?im)^\s*(?:"
    r"(?:a\s+)?(?:catalogue|catalog|list)\s+of\b.*(?:books|publications)|"
    r"(?:publisher'?s\s+)?(?:catalogue|catalog)|"
    r"(?:new|recent)\s+publications|"
    r"books\s+by\b|by\s+the\s+same\s+author|"
    r"advertisements?|"
    r"[A-Z][A-Z .,&'-]{4,80}\s+PUBLICATIONS"
    r")\.?\s*$"
)
CATALOG_TERM_RE = re.compile(
    r"\b(?:crown|demy|fcap|post|royal|cloth|boards|sewed|price|vols?\.?|"
    r"edition|illustrated|frontispiece|published|publishers?|shilling|"
    r"catalogue|catalog|series)\b|(?:\d+\s*_s\._|\d+\s*_d\._|\d+s\.|\d+d\.)",
    re.IGNORECASE,
)
PRICE_LINE_RE = re.compile(
    r"\b(?:price\s+)?(?:\d+\s*_s\._|\d+\s*_d\._|\d+s\.|\d+d\.|L\d+)\b",
    re.IGNORECASE,
)
TERMINAL_IMPRINT_RE = re.compile(
    r"(?im)^\s*(?:"
    r"[A-Z][A-Z .&'\-]{2,}\s+PRESS:.*|"
    r".*\b(?:CHISWICK PRESS|TOOKS COURT|CHANCERY LANE|PRINTED BY)\b.*"
    r")$"
)


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style", "nav"]):
        node.decompose()
    return clean_plain_text(soup.get_text("\n"))


def clean_plain_text(text: str) -> str:
    stripped = strip_gutenberg_boilerplate(text)
    stripped = remove_gutenberg_artifacts(stripped)
    stripped = normalize_text(remove_inline_markup(stripped))
    stripped = trim_front_matter(stripped)
    stripped = trim_leading_section_list(stripped)
    stripped = trim_back_matter(stripped)
    return normalize_text(remove_inline_markup(stripped))


def strip_gutenberg_boilerplate(text: str) -> str:
    start = 0
    end = len(text)
    upper_text = text.upper()

    for marker in START_MARKERS:
        index = upper_text.find(marker)
        if index >= 0:
            marker_end = text.find("***", index + 3)
            line_end = text.find("\n", marker_end + 3 if marker_end >= 0 else index)
            start = line_end + 1 if line_end >= 0 else index + len(marker)
            break

    for marker in END_MARKERS:
        index = upper_text.find(marker)
        if index >= 0:
            end = index
            break

    return text[start:end]


def remove_gutenberg_artifacts(text: str) -> str:
    text = ILLUSTRATION_BLOCK_RE.sub("\n", text)
    text = FOOTNOTE_BODY_RE.sub("", text)
    text = INLINE_FOOTNOTE_RE.sub("", text)
    text = PAGE_MARKER_RE.sub("", text)
    return BRACE_NOTE_RE.sub("\n", text)


def remove_inline_markup(text: str) -> str:
    text = NIND_MARKUP_RE.sub("", text)
    text = ITALIC_MARKUP_RE.sub(r"\1", text)
    text = text.replace("_", "")
    text = FOOTNOTE_PAGE_REF_RE.sub("", text)
    return text


def trim_front_matter(text: str) -> str:
    start = find_front_matter_body_start(text)
    if start <= 0:
        return text
    return text[start:].lstrip()


def trim_leading_section_list(text: str) -> str:
    paragraphs = list(PARAGRAPH_RE.finditer(text[:FRONT_MATTER_SCAN_LIMIT]))
    if len(paragraphs) < 2:
        return text

    first_paragraph = paragraphs[0].group(0).strip()
    first_lines = meaningful_lines(first_paragraph)
    if len(first_lines) < 4:
        return text
    if not all(looks_like_body_section_heading(line) for line in first_lines):
        return text

    next_paragraph = paragraphs[1].group(0).strip()
    next_first_line = next((line for line in meaningful_lines(next_paragraph)), "")
    if not looks_like_body_section_heading(next_first_line):
        return text

    return text[paragraphs[1].start() :].lstrip()


def looks_like_body_section_heading(line: str) -> bool:
    normalized = " ".join(line.strip().split())
    if not normalized:
        return False
    return bool(BARE_BODY_HEADING_RE.fullmatch(normalized) or BODY_START_HEADING_RE.fullmatch(normalized))


def trim_back_matter(text: str) -> str:
    start = find_back_matter_start(text)
    if start is None or start <= 0:
        return text
    return text[:start].rstrip()


def find_front_matter_body_start(text: str) -> int:
    scan = text[:FRONT_MATTER_SCAN_LIMIT]
    list_start = first_literary_paragraph_after_front_matter_list(scan)
    heading_start = first_body_heading_after_front_matter(scan)

    if list_start is not None:
        if (
            heading_start is not None
            and heading_start > list_start
            and (
                looks_like_front_matter_apparatus(scan[list_start:heading_start])
                or apparatus_context_score(scan[list_start:heading_start]) >= 5
            )
        ):
            return heading_start
        return list_start

    if heading_start is not None:
        return heading_start

    return 0


def first_body_heading_after_front_matter(scan: str) -> int | None:
    for match in BODY_START_HEADING_RE.finditer(scan):
        prefix = scan[: match.start()]
        if match.start() <= 12:
            return 0
        if looks_like_removable_front_prefix(prefix):
            return match.start()
    return None


def looks_like_removable_front_prefix(prefix: str) -> bool:
    if not prefix.strip():
        return False
    words = WORD_RE.findall(prefix)
    if len(words) <= 280 and looks_like_title_page_prefix(prefix):
        return True
    if FRONT_MATTER_TERM_RE.search(prefix):
        return True
    if looks_like_front_matter_list(prefix):
        return True
    return looks_like_front_matter_apparatus(prefix)


def looks_like_title_page_prefix(prefix: str) -> bool:
    if not TITLE_PAGE_PUBLICATION_RE.search(prefix):
        return False
    words = WORD_RE.findall(prefix)
    if len(words) > 320:
        return False
    meaningful = meaningful_lines(prefix)
    if not meaningful:
        return False
    short_lines = sum(1 for line in meaningful if len(line) <= 80)
    return short_lines / len(meaningful) >= 0.75


def first_literary_paragraph_after_front_matter_list(scan: str) -> int | None:
    contents_match = CONTENTS_HEADING_RE.search(scan)
    if not contents_match:
        return None

    paragraphs = list(PARAGRAPH_RE.finditer(scan[contents_match.end() :]))
    previous_match: re.Match[str] | None = None
    for paragraph_match in paragraphs:
        paragraph = paragraph_match.group(0).strip()
        absolute_start = contents_match.end() + paragraph_match.start()
        if looks_like_front_matter_heading(paragraph):
            previous_match = paragraph_match
            continue
        if looks_like_page_reference_block(paragraph):
            previous_match = paragraph_match
            continue
        if looks_like_publisher_catalog(paragraph):
            previous_match = paragraph_match
            continue
        if looks_like_literary_paragraph(paragraph):
            if previous_match and BODY_START_HEADING_RE.fullmatch(previous_match.group(0).strip()):
                return contents_match.end() + previous_match.start()
            return absolute_start
        previous_match = paragraph_match
    return None


def find_back_matter_start(text: str) -> int | None:
    if len(text) < 1000 and not CATALOG_HEADING_RE.search(text):
        return None

    minimum_start = int(len(text) * BACK_MATTER_MIN_FRACTION)
    terminal_imprint_start = find_terminal_imprint_start(text, minimum_start)
    if terminal_imprint_start is not None:
        return terminal_imprint_start

    for match in CATALOG_HEADING_RE.finditer(text):
        if match.start() < minimum_start:
            continue
        following = text[match.start() : match.start() + 5000]
        if looks_like_publisher_catalog(following):
            return match.start()

    end_match = list(re.finditer(r"(?im)^\s*(?:the end|finis)\.?\s*$", text))
    for match in end_match:
        following = text[match.end() : match.end() + 5000]
        catalog = CATALOG_HEADING_RE.search(following)
        if catalog and looks_like_publisher_catalog(following[catalog.start() :]):
            return match.end()
    return None


def find_terminal_imprint_start(text: str, minimum_start: int) -> int | None:
    paragraphs = list(PARAGRAPH_RE.finditer(text))
    for match in reversed(paragraphs[-10:]):
        if match.start() < minimum_start:
            continue
        paragraph = match.group(0).strip()
        if TERMINAL_IMPRINT_RE.search(paragraph):
            return match.start()
    return None


def looks_like_front_matter_heading(text: str) -> bool:
    normalized = " ".join(text.strip().split())
    if not normalized:
        return False
    if FRONT_MATTER_HEADING_RE.fullmatch(normalized):
        return True
    first_line = next((line for line in meaningful_lines(text)[:1]), "")
    return bool(first_line and FRONT_MATTER_HEADING_RE.fullmatch(first_line))


def looks_like_front_matter_list(text: str) -> bool:
    lines = meaningful_lines(text[:6000])
    if len(lines) < 6:
        return False

    page_ref_lines = sum(1 for line in lines if looks_like_page_reference_line(line))
    front_matter_hits = sum(1 for line in lines if FRONT_MATTER_TERM_RE.search(line))
    short_lines = sum(1 for line in lines if len(line) <= 95)
    has_contents = bool(CONTENTS_HEADING_RE.search(text[:1600]))
    return (
        page_ref_lines >= 6
        or front_matter_hits >= 4
        or (has_contents and page_ref_lines >= 3)
        or (has_contents and short_lines / max(len(lines), 1) >= 0.74 and len(lines) >= 12)
    )


def looks_like_front_matter_apparatus(text: str) -> bool:
    first_block = text[:5000]
    if looks_like_front_matter_list(first_block):
        return True
    if FRONT_MATTER_HEADING_RE.search(first_block[:1200]) and apparatus_context_score(first_block) >= 3:
        return True
    return apparatus_context_score(first_block) >= 7 and sentence_count(first_block) >= 3


def looks_like_publisher_catalog(text: str) -> bool:
    sample = text[:6000]
    lines = meaningful_lines(sample)
    if len(lines) < 3:
        return False
    catalog_terms = len(CATALOG_TERM_RE.findall(sample))
    price_lines = sum(1 for line in lines if PRICE_LINE_RE.search(line))
    heading = bool(CATALOG_HEADING_RE.search(sample[:1400]))
    compact_lines = sum(1 for line in lines if len(line) <= 110)
    return (
        heading
        and catalog_terms >= 5
        or price_lines >= 4
        or (catalog_terms >= 12 and compact_lines / max(len(lines), 1) >= 0.55)
    )


def looks_like_page_reference_block(text: str) -> bool:
    lines = meaningful_lines(text)
    if len(lines) < 3:
        return False
    page_ref_lines = sum(1 for line in lines if looks_like_page_reference_line(line))
    return page_ref_lines >= 3 or page_ref_lines / len(lines) >= 0.5


def looks_like_page_reference_line(line: str) -> bool:
    normalized = " ".join(line.strip().split())
    if not normalized:
        return False
    if BARE_BODY_HEADING_RE.fullmatch(normalized):
        return False
    if re.fullmatch(r"[IVXLCDM]{1,12}\.?", normalized):
        return False
    return bool(
        re.match(
            r"^(?:[0-9]+\.?\s+)?[A-Za-z][A-Za-z0-9'\".,;:() \-]{1,110}"
            r"\s+(?:_?to face_?\s+)?(?:[ivxlcdm]+|\d{1,4})\.?$",
            normalized,
            flags=re.IGNORECASE,
        )
    )


def looks_like_literary_paragraph(text: str) -> bool:
    words = WORD_RE.findall(text)
    if len(words) < 12:
        return False
    if looks_like_page_reference_block(text):
        return False
    if looks_like_publisher_catalog(text):
        return False
    if uppercase_word_share(words[:80]) > 0.72 and len(words) < 140:
        return False
    if FRONT_MATTER_TERM_RE.search(text[:500]) and apparatus_context_score(text[:1500]) >= 3:
        return False
    return sentence_count(text) >= 1 or len(meaningful_lines(text)) >= 6


def apparatus_context_score(text: str) -> int:
    lowered = text.lower()
    return sum(1 for term in APPARATUS_CONTEXT_TERMS if term in lowered)


def sentence_count(text: str) -> int:
    return len(SENTENCE_MARK_RE.findall(text))


def uppercase_word_share(words: list[str]) -> float:
    if not words:
        return 0.0
    uppercase_words = sum(1 for word in words if word.isupper() and len(word) > 1)
    return uppercase_words / len(words)


def meaningful_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
