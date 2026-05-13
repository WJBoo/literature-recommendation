from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.ingest_bulk_gutenberg import (
    catalog_candidate_from_row,
    is_part_or_volume_record,
    select_catalog_candidates,
    split_catalog_list,
    title_key,
)


def test_split_catalog_list_normalizes_semicolon_values():
    assert split_catalog_list(" Fiction ; Poetry;  ") == ["Fiction", "Poetry"]


def test_catalog_candidate_filters_to_english_literary_text():
    literary = catalog_candidate_from_row(
        {
            "Text#": "1342",
            "Type": "Text",
            "Title": "Pride and Prejudice",
            "Language": "en",
            "Authors": "Austen, Jane, 1775-1817",
            "Subjects": "Courtship -- Fiction; England -- Fiction",
            "LoCC": "PR",
            "Bookshelves": "Best Books Ever Listings; Category: Fiction",
        }
    )
    assert literary is not None
    assert literary.gutenberg_id == "1342"
    assert literary.score > 0

    non_english = catalog_candidate_from_row(
        {
            "Text#": "1",
            "Type": "Text",
            "Title": "A French Novel",
            "Language": "fr",
            "Authors": "Auteur",
            "Subjects": "Fiction",
            "LoCC": "PQ",
            "Bookshelves": "Category: Fiction",
        }
    )
    assert non_english is None

    non_literary = catalog_candidate_from_row(
        {
            "Text#": "2",
            "Type": "Text",
            "Title": "A Dictionary of Useful Things",
            "Language": "en",
            "Authors": "Compiler",
            "Subjects": "Dictionaries",
            "LoCC": "AG",
            "Bookshelves": "Reference",
        }
    )
    assert non_literary is None

    unknown_author = catalog_candidate_from_row(
        {
            "Text#": "3",
            "Type": "Text",
            "Title": "A Literary Tale",
            "Language": "en",
            "Authors": "Unknown",
            "Subjects": "Fiction",
            "LoCC": "PR",
            "Bookshelves": "Category: Fiction",
        }
    )
    assert unknown_author is None

    part_record = catalog_candidate_from_row(
        {
            "Text#": "4",
            "Type": "Text",
            "Title": "A Connecticut Yankee in King Arthur's Court, Part 4.",
            "Language": "en",
            "Authors": "Twain, Mark, 1835-1910",
            "Subjects": "Fiction",
            "LoCC": "PS",
            "Bookshelves": "Category: Fiction",
        }
    )
    assert part_record is None

    chapter_record = catalog_candidate_from_row(
        {
            "Text#": "5",
            "Type": "Text",
            "Title": "Adventures of Huckleberry Finn, Chapters 01 to 05",
            "Language": "en",
            "Authors": "Twain, Mark, 1835-1910",
            "Subjects": "Fiction",
            "LoCC": "PS",
            "Bookshelves": "Category: Fiction",
        }
    )
    assert chapter_record is None


def test_select_catalog_candidates_orders_by_literary_score_then_id():
    rows = [
        {
            "Text#": "200",
            "Type": "Text",
            "Title": "Plain Literary Work",
            "Language": "en",
            "Authors": "Writer",
            "Subjects": "English literature",
            "LoCC": "PR",
            "Bookshelves": "",
        },
        {
            "Text#": "100",
            "Type": "Text",
            "Title": "A Short Story Collection",
            "Language": "en",
            "Authors": "Writer",
            "Subjects": "Short stories; Fiction",
            "LoCC": "PS",
            "Bookshelves": "Category: Fiction",
        },
    ]

    candidates = select_catalog_candidates(rows, target_count=2, selection_mode="score")

    assert [candidate.gutenberg_id for candidate in candidates] == ["100", "200"]


def test_part_and_volume_title_helpers_normalize_duplicates():
    assert is_part_or_volume_record("A Connecticut Yankee in King Arthur's Court, Part 4.")
    assert is_part_or_volume_record("The Three Perils of Man; or, War, Vol. 2 (of 3)")
    assert is_part_or_volume_record(
        "The Collected Works in Verse and Prose of William Butler Yeats, Vol. 3 (of 8) "
        "The Countess Cathleen"
    )
    assert is_part_or_volume_record("Parzival: A Knightly Epic (vol. 2 of 2)")
    assert is_part_or_volume_record("The Works of William Shakespeare [Cambridge Edition] [Vol. 5 of 9]")
    assert is_part_or_volume_record("Kalevala, The Land of the Heroes, Volume Two")
    assert is_part_or_volume_record("Plays, written by Sir John Vanbrugh, volume the second")
    assert is_part_or_volume_record("Adventures of Huckleberry Finn, Chapters 01 to 05")
    assert is_part_or_volume_record("The Faerie Queene, Book III")
    assert is_part_or_volume_record("The Metamorphoses of Ovid, Books I-VII")
    assert title_key("A Connecticut Yankee in King Arthur's Court, Part 4.") == (
        "connecticut yankee in king arthur s court"
    )
    assert title_key("Adventures of Huckleberry Finn, Chapters 01 to 05") == (
        "adventures of huckleberry finn"
    )
