from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import xml.etree.ElementTree as ET


@dataclass(frozen=True)
class GutenbergWorkMetadata:
    gutenberg_id: str
    title: str
    authors: list[str] = field(default_factory=list)
    language: str | None = None
    subjects: list[str] = field(default_factory=list)
    bookshelves: list[str] = field(default_factory=list)


def load_rdf_metadata(path: Path) -> list[GutenbergWorkMetadata]:
    tree = ET.parse(path)
    root = tree.getroot()
    namespaces = {
        "pgterms": "http://www.gutenberg.org/2009/pgterms/",
        "dcterms": "http://purl.org/dc/terms/",
        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    }

    records: list[GutenbergWorkMetadata] = []
    for ebook in root.findall(".//pgterms:ebook", namespaces):
        about = ebook.attrib.get(f"{{{namespaces['rdf']}}}about", "")
        gutenberg_id = about.rsplit("/", maxsplit=1)[-1]
        title = _text(ebook.find("dcterms:title", namespaces)) or "Untitled"
        language = _text(ebook.find("dcterms:language/rdf:Description/rdf:value", namespaces))

        authors = [
            name.text.strip()
            for name in ebook.findall(".//dcterms:creator/pgterms:agent/pgterms:name", namespaces)
            if name.text
        ]
        subjects = [
            value.text.strip()
            for value in ebook.findall(".//dcterms:subject/rdf:Description/rdf:value", namespaces)
            if value.text
        ]
        bookshelves = [
            value.text.strip()
            for value in ebook.findall(".//pgterms:bookshelf/rdf:Description/rdf:value", namespaces)
            if value.text
        ]

        records.append(
            GutenbergWorkMetadata(
                gutenberg_id=gutenberg_id,
                title=title,
                authors=authors,
                language=language,
                subjects=subjects,
                bookshelves=bookshelves,
            )
        )

    return records


def infer_form(metadata: GutenbergWorkMetadata) -> str:
    searchable = " ".join(metadata.subjects + metadata.bookshelves).lower()
    if "poetry" in searchable or "poems" in searchable:
        return "poetry"
    if "drama" in searchable or "plays" in searchable:
        return "drama"
    return "prose"


def _text(node: ET.Element | None) -> str | None:
    if node is None or node.text is None:
        return None
    return node.text.strip()
