from app.ingestion.cleaning import clean_plain_text, remove_gutenberg_artifacts


def test_clean_plain_text_handles_wrapped_start_marker():
    raw = """Header
*** START OF THE PROJECT GUTENBERG EBOOK THE ADVENTURES OF SHERLOCK
HOLMES ***

The Adventures of Sherlock Holmes

*** END OF THE PROJECT GUTENBERG EBOOK THE ADVENTURES OF SHERLOCK HOLMES ***
License
"""

    clean = clean_plain_text(raw)

    assert clean == "The Adventures of Sherlock Holmes"


def test_remove_gutenberg_artifacts_strips_illustrations_and_notes():
    text = """Opening paragraph.

[Illustration:

"A caption"

[_Copyright 1894 by Someone._]]

{An editor's note that should not be embedded.}

[vii]

Next paragraph."""

    clean = remove_gutenberg_artifacts(text)

    assert "Illustration" not in clean
    assert "Copyright" not in clean
    assert "editor's note" not in clean
    assert "[vii]" not in clean
    assert "Opening paragraph." in clean
    assert "Next paragraph." in clean


def test_remove_gutenberg_artifacts_strips_footnote_bodies_and_markers():
    text = """    [2] B. would render: a translator note.
    continued translator note.

    A second translator-note paragraph.

Then I heard that at need of the king
 [1]He his head did not guard,
 fire[2]

Later to lessen."""

    clean = remove_gutenberg_artifacts(text)

    assert "translator note" not in clean
    assert "second translator" not in clean
    assert "[1]" not in clean
    assert "[2]" not in clean
    assert "Then I heard" in clean
    assert "Later to lessen." in clean


def test_clean_plain_text_removes_underscore_italics_and_page_references():
    raw = "She said _nay_, 730 and then chose Elizabeth._"

    clean = clean_plain_text(raw)

    assert clean == "She said nay and then chose Elizabeth."


def test_clean_plain_text_trims_preface_and_illustration_list_before_body():
    raw = """*** START OF THE PROJECT GUTENBERG EBOOK PRIDE AND PREJUDICE ***

PRIDE.
and
PREJUDICE

by
Jane Austen,

with a Preface by
George Saintsbury
and
Illustrations by
Hugh Thomson

London
George Allen.

PREFACE.

Walt Whitman has somewhere a fine and just distinction between loving
by allowance and loving with personal love. This is editorial front matter.

PAGE

Frontispiece iv

Title-page v

Heading to Chapter I. 1

"He came down to see the place" 2

The End 476

It is a truth universally acknowledged, that a single man in possession
of a good fortune must be in want of a wife.

However little known the feelings or views of such a man may be on his
first entering a neighbourhood, this truth is so well fixed in the minds
of the surrounding families.

*** END OF THE PROJECT GUTENBERG EBOOK PRIDE AND PREJUDICE ***"""

    clean = clean_plain_text(raw)

    assert clean.startswith("It is a truth universally acknowledged")
    assert "PREFACE" not in clean
    assert "Frontispiece" not in clean


def test_clean_plain_text_trims_to_first_body_chapter_after_front_matter():
    raw = """Title Page

PREFACE

This introduction discusses the history of the book before the story.

CHAPTER I

The road curved below the orchard, and every branch trembled with the
after-rain. Julia walked beside the stranger without speaking."""

    clean = clean_plain_text(raw)

    assert clean.startswith("CHAPTER I")
    assert "PREFACE" not in clean
