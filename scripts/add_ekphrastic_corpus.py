#!/usr/bin/env python
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings
from app.ingestion.canonicalization import canonical_author, canonical_title
from app.services.embedding_jobs import ExcerptEmbeddingInput, build_excerpt_embedding_text
from app.services.processed_corpus import clear_processed_corpus_cache
from app.services.processed_embeddings import clear_processed_embedding_cache
from app.services.processed_latent_factors import clear_processed_latent_factor_cache

CURATED_DIR = settings.processed_data_dir / "curated_ekphrasis"
WORKS_PATH = settings.processed_data_dir / "gutenberg_works.jsonl"
EXCERPTS_PATH = settings.processed_data_dir / "gutenberg_excerpts.jsonl"
EMBEDDING_INPUTS_PATH = settings.processed_data_dir / "gutenberg_embedding_inputs.jsonl"


def labels(form: str, moods: list[str], themes: list[str]) -> list[dict[str, str]]:
    records = [
        {"label_type": "form", "label": form, "evidence": "curated ekphrastic corpus"},
        {"label_type": "genre", "label": "ekphrasis", "evidence": "curated ekphrastic corpus"},
        {"label_type": "genre", "label": "art writing", "evidence": "curated ekphrastic corpus"},
    ]
    records.extend(
        {"label_type": "mood", "label": mood, "evidence": "curated ekphrastic corpus"}
        for mood in moods
    )
    records.extend(
        {"label_type": "theme", "label": theme, "evidence": "curated ekphrastic corpus"}
        for theme in themes
    )
    return records


PIECES: list[dict[str, Any]] = [
    {
        "id": "ekphrasis-keats-grecian-urn",
        "gutenberg_id": "curated-ekphrasis-keats-urn",
        "title": "Ode on a Grecian Urn",
        "author": "Keats, John, 1795-1821",
        "form": "poetry",
        "source_url": "https://en.wikisource.org/wiki/Ode_on_a_Grecian_Urn",
        "subjects": [
            "Ekphrasis",
            "English poetry",
            "Greek vases in literature",
            "Art and literature",
        ],
        "labels": labels(
            "poetry",
            moods=["contemplative", "lyrical"],
            themes=["art", "beauty", "time", "classical antiquity", "imagination"],
        ),
        "media": [
            {
                "id": "art-keats-urn",
                "media_type": "image",
                "data_url": "https://commons.wikimedia.org/wiki/Special:FilePath/Keats_urn.jpg",
                "alt_text": "John Keats's drawing after an engraving of the Sosibios Vase.",
                "caption": "Artwork: John Keats, drawing after the Sosibios Vase, circa 1819. Wikimedia Commons, public domain.",
            }
        ],
        "text": """I

Thou still unravish'd bride of quietness,
Thou foster-child of silence and slow time,
Sylvan historian, who canst thus express
A flowery tale more sweetly than our rhyme:
What leaf-fring'd legend haunts about thy shape
Of deities or mortals, or of both,
In Tempe or the dales of Arcady?
What men or gods are these? What maidens loth?
What mad pursuit? What struggle to escape?
What pipes and timbrels? What wild ecstasy?

II

Heard melodies are sweet, but those unheard
Are sweeter; therefore, ye soft pipes, play on;
Not to the sensual ear, but, more endear'd,
Pipe to the spirit ditties of no tone:
Fair youth, beneath the trees, thou canst not leave
Thy song, nor ever can those trees be bare;
Bold Lover, never, never canst thou kiss,
Though winning near the goal yet, do not grieve;
She cannot fade, though thou hast not thy bliss,
For ever wilt thou love, and she be fair!

III

Ah, happy, happy boughs! that cannot shed
Your leaves, nor ever bid the Spring adieu;
And, happy melodist, unwearied,
For ever piping songs for ever new;
More happy love! more happy, happy love!
For ever warm and still to be enjoy'd,
For ever panting, and for ever young;
All breathing human passion far above,
That leaves a heart high-sorrowful and cloy'd,
A burning forehead, and a parching tongue.

IV

Who are these coming to the sacrifice?
To what green altar, O mysterious priest,
Lead'st thou that heifer lowing at the skies,
And all her silken flanks with garlands drest?
What little town by river or sea shore,
Or mountain-built with peaceful citadel,
Is emptied of this folk, this pious morn?
And, little town, thy streets for evermore
Will silent be; and not a soul to tell
Why thou art desolate, can e'er return.

V

O Attic shape! Fair attitude! with brede
Of marble men and maidens overwrought,
With forest branches and the trodden weed;
Thou, silent form, dost tease us out of thought
As doth eternity: Cold Pastoral!
When old age shall this generation waste,
Thou shalt remain, in midst of other woe
Than ours, a friend to man, to whom thou say'st,
"Beauty is truth, truth beauty,"--that is all
Ye know on earth, and all ye need to know.""",
    },
    {
        "id": "ekphrasis-shelley-medusa",
        "gutenberg_id": "curated-ekphrasis-shelley-medusa",
        "title": "On the Medusa of Leonardo Da Vinci in the Florentine Gallery",
        "author": "Shelley, Percy Bysshe, 1792-1822",
        "form": "poetry",
        "source_url": "https://en.wikisource.org/wiki/The_Complete_Poetical_Works_of_Percy_Bysshe_Shelley_(ed._Hutchinson,_1914)/On_the_Medusa_of_Leonardo_Da_Vinci_in_the_Florentine_Gallery",
        "subjects": [
            "Ekphrasis",
            "English poetry",
            "Medusa in literature",
            "Mythology in art",
            "Art and literature",
        ],
        "labels": labels(
            "poetry",
            moods=["sublime", "dark", "intense"],
            themes=["art", "beauty", "terror", "myth", "death"],
        ),
        "media": [
            {
                "id": "art-medusa-uffizi",
                "media_type": "image",
                "data_url": "https://commons.wikimedia.org/wiki/Special:FilePath/Medusa_uffizi.jpg?width=1000",
                "alt_text": "Head of Medusa, a painting formerly attributed to Leonardo da Vinci.",
                "caption": "Artwork: Head of Medusa, Uffizi Gallery, formerly attributed to Leonardo da Vinci. Wikimedia Commons, public domain.",
            }
        ],
        "text": """I

It lieth, gazing on the midnight sky,
Upon the cloudy mountain-peak supine;
Below, far lands are seen tremblingly;
Its horror and its beauty are divine.
Upon its lips and eyelids seems to lie
Loveliness like a shadow, from which shine,
Fiery and lurid, struggling underneath,
The agonies of anguish and of death.

II

Yet it is less the horror than the grace
Which turns the gazer's spirit into stone,
Whereon the lineaments of that dead face
Are graven, till the characters be grown
Into itself, and thought no more can trace;
'Tis the melodious hue of beauty thrown
Athwart the darkness and the glare of pain,
Which humanize and harmonize the strain.

III

And from its head as from one body grow,
As grass out of a watery rock,
Hairs which are vipers, and they curl and flow
And their long tangles in each other lock,
And with unending involutions show
Their mailed radiance, as it were to mock
The torture and the death within, and saw
The solid air with many a ragged jaw.

IV

And, from a stone beside, a poisonous eft
Peeps idly into those Gorgonian eyes;
Whilst in the air a ghastly bat, bereft
Of sense, has flitted with a mad surprise
Out of the cave this hideous light had cleft,
And he comes hastening like a moth that hies
After a taper; and the midnight sky
Flares, a light more dread than obscurity.

V

'Tis the tempestuous loveliness of terror;
For from the serpents gleams a brazen glare
Kindled by that inextricable error,
Which makes a thrilling vapour of the air
Become a and ever-shifting mirror
Of all the beauty and the terror there--
A woman's countenance, with serpent-locks,
Gazing in death on Heaven from those wet rocks.""",
    },
    {
        "id": "ekphrasis-swinburne-before-the-mirror",
        "gutenberg_id": "curated-ekphrasis-swinburne-mirror",
        "title": "Before the Mirror",
        "author": "Swinburne, Algernon Charles, 1837-1909",
        "form": "poetry",
        "source_url": "https://www.gutenberg.org/files/35402/35402-h/35402-h.htm#BEFORE_THE_MIRROR",
        "subjects": [
            "Ekphrasis",
            "English poetry",
            "Whistler, James McNeill, 1834-1903",
            "Art and literature",
        ],
        "labels": labels(
            "poetry",
            moods=["elegiac", "dreamlike", "contemplative"],
            themes=["art", "beauty", "reflection", "memory", "desire"],
        ),
        "media": [
            {
                "id": "art-whistler-symphony-white-2",
                "media_type": "image",
                "data_url": "https://commons.wikimedia.org/wiki/Special:FilePath/Whistler%20James%20Symphony%20in%20White%20no%202%20(The%20Little%20White%20Girl)%201864.jpg?width=900",
                "alt_text": "James McNeill Whistler's Symphony in White, No. 2: The Little White Girl.",
                "caption": "Artwork: James McNeill Whistler, Symphony in White, No. 2: The Little White Girl, 1864. Wikimedia Commons, public domain.",
            }
        ],
        "text": """I

White rose in red rose-garden
Is not so white;
Snowdrops that plead for pardon
And pine for fright
Because the hard East blows
Over their maiden rows
Grow not as this face grows from pale to bright.

Behind the veil, forbidden,
Shut up from sight,
Love, is there sorrow hidden,
Is there delight?
Is joy thy dower or grief,
White rose of weary leaf,
Late rose whose life is brief, whose loves are light?
Soft snows that hard winds harden
Till each flake bite
Fill all the flowerless garden
Whose flowers took flight
Long since when summer ceased,
And men rose up from feast,
And warm west wind grew east, and warm day night.

II

"Come snow, come wind or thunder
High up in air,
I watch my face, and wonder
At my bright hair;
Nought else exalts or grieves
The rose at heart, that heaves
With love of her own leaves and lips that pair.

"She knows not loves that kissed her
She knows not where.
Art thou the ghost, my sister,
White sister there,
Am I the ghost, who knows?
My hand, a fallen rose,
Lies snow-white on white snows, and takes no care.

"I cannot see what pleasures
Or what pains were;
What pale new loves and treasures
New years will bear;
What beam will fall, what shower,
What grief or joy for dower;
But one thing-knows the flower; the flower is fair."

III

Glad, but not flushed with gladness,
Since joys go by;
Sad, but not bent with sadness,
Since sorrows die;
Deep in the gleaming glass
She sees all past things pass,
And all sweet life that was lie down and lie.

There glowing ghosts of flowers
Draw down, draw nigh;
And wings of swift spent hours
Take flight and fly;
She sees by formless gleams,
She hears across cold streams,
Dead mouths of many dreams that sing and sigh.
Face fallen and white throat lifted,
With sleepless eye
She sees old loves that drifted,
She knew not why,
Old loves and faded fears
Float down a stream that hears
The flowing of all men's tears beneath the sky.""",
    },
    {
        "id": "ekphrasis-pater-mona-lisa",
        "gutenberg_id": "4060-ekphrasis-mona-lisa",
        "title": "The Mona Lisa",
        "author": "Pater, Walter, 1839-1894",
        "form": "prose",
        "source_url": "https://www.gutenberg.org/ebooks/4060",
        "subjects": [
            "Ekphrasis",
            "Art criticism",
            "Leonardo da Vinci, 1452-1519",
            "Mona Lisa",
            "Renaissance art",
        ],
        "labels": labels(
            "prose",
            moods=["meditative", "mysterious", "philosophical"],
            themes=["art", "beauty", "time", "portraiture", "aesthetic criticism"],
        ),
        "media": [
            {
                "id": "art-mona-lisa-pater",
                "media_type": "image",
                "data_url": "https://commons.wikimedia.org/wiki/Special:FilePath/Leonardo_da_Vinci_-_Mona_Lisa.jpg?width=900",
                "alt_text": "Leonardo da Vinci's Mona Lisa.",
                "caption": "Artwork: Leonardo da Vinci, Mona Lisa, circa 1503-1506. Wikimedia Commons, public domain.",
            }
        ],
        "text": """From The Renaissance: Studies in Art and Poetry, in the essay on Leonardo da Vinci.

Set it for a moment beside one of those white Greek goddesses or beautiful women of antiquity, and how would they be troubled by this beauty, into which the soul with all its maladies has passed! All the thoughts and experience of the world have etched and moulded there, in that which they have of power to refine and make expressive the outward form, the animalism of Greece, the lust of Rome, the mysticism of the middle age with its spiritual ambition and imaginative loves, the return of the Pagan world, the sins of the Borgias.

She is older than the rocks among which she sits; like the vampire, she has been dead many times, and learned the secrets of the grave; and has been a diver in deep seas, and keeps their fallen day about her; and trafficked for strange webs with Eastern merchants; and, as Leda, was the mother of Helen of Troy, and, as Saint Anne, the mother of Mary; and all this has been to her but as the sound of lyres and flutes, and lives only in the delicacy with which it has moulded the changing lineaments, and tinged the eyelids and the hands.

The fancy of a perpetual life, sweeping together ten thousand experiences, is an old one; and modern philosophy has conceived the idea of humanity as wrought upon by, and summing up in itself, all modes of thought and life. Certainly Lady Lisa might stand as the embodiment of the old fancy, the symbol of the modern idea.""",
    },
    {
        "id": "ekphrasis-michael-field-la-gioconda",
        "gutenberg_id": "curated-ekphrasis-field-gioconda",
        "title": "La Gioconda",
        "author": "Field, Michael, 1846-1914; 1862-1913",
        "form": "poetry",
        "source_url": "https://books.google.com/books/about/Sight_and_song_poems.html?id=q5PJMT7pJBAC",
        "subjects": [
            "Ekphrasis",
            "English poetry",
            "Leonardo da Vinci, 1452-1519",
            "Mona Lisa",
            "Art and literature",
        ],
        "labels": labels(
            "poetry",
            moods=["mysterious", "compressed", "contemplative"],
            themes=["art", "beauty", "portraiture", "desire", "decadence"],
        ),
        "media": [
            {
                "id": "art-mona-lisa-field",
                "media_type": "image",
                "data_url": "https://commons.wikimedia.org/wiki/Special:FilePath/Leonardo_da_Vinci_-_Mona_Lisa.jpg?width=900",
                "alt_text": "Leonardo da Vinci's Mona Lisa.",
                "caption": "Artwork: Leonardo da Vinci, Mona Lisa, circa 1503-1506. Wikimedia Commons, public domain.",
            }
        ],
        "text": """Historic, side-long, implicating eyes;
A smile of velvet's lustre on the cheek;
Calm lips the smile leads upward; hand that lies
Glowing and soft, the patience in its rest
Of cruelty that waits and doth not seek
For prey; a dusky forehead and a breast
Where twilight touches ripeness amorously:
Behind her, crystal rocks, a sea and skies
Of evanescent blue on cloud and creek;
Landscape that shines suppressive of its zest
For those vicissitudes by which men die.""",
    },
]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as source:
        for line in source:
            if line.strip():
                records.append(json.loads(line))
    return records


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output:
        for record in records:
            output.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")


def upsert_records(path: Path, records: list[dict[str, Any]], key: str = "id") -> None:
    current = read_jsonl(path)
    by_key = {record[key]: record for record in current if key in record}
    for record in records:
        by_key[record[key]] = record
    write_jsonl(path, by_key.values())


def word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9']+", text))


def embedding_input_for(work: dict[str, Any], excerpt: dict[str, Any]) -> dict[str, Any]:
    return {
        "excerpt_id": excerpt["id"],
        "work_id": work["id"],
        "embedding_model": settings.embedding_model,
        "embedding_dimensions": settings.embedding_dimensions,
        "embedding_text": build_excerpt_embedding_text(
            ExcerptEmbeddingInput(
                excerpt_id=0,
                title=excerpt["display_title"],
                author=work["author"],
                form=work["form"],
                subjects=work["subjects"],
                text=excerpt["text"],
            )
        ),
    }


def build_records() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    processed_at = datetime.now(timezone.utc).isoformat()
    works: list[dict[str, Any]] = []
    excerpts: list[dict[str, Any]] = []
    embedding_inputs: list[dict[str, Any]] = []

    for piece in PIECES:
        work_id = piece["id"]
        canonical_author_value = canonical_author(piece["author"])
        canonical_title_value = canonical_title(piece["title"])
        text_path = CURATED_DIR / f"{work_id}.txt"
        text_path.parent.mkdir(parents=True, exist_ok=True)
        text_path.write_text(piece["text"].strip() + "\n", encoding="utf-8")
        count = word_count(piece["text"])
        work = {
            "id": work_id,
            "gutenberg_id": piece["gutenberg_id"],
            "title": piece["title"],
            "author": piece["author"],
            "language": "en",
            "form": piece["form"],
            "subjects": piece["subjects"],
            "bookshelves": ["Curated Ekphrasis", "Category: Poetry" if piece["form"] == "poetry" else "Category: Essays"],
            "source_url": piece["source_url"],
            "raw_path": str(text_path.relative_to(ROOT)),
            "clean_path": str(text_path.relative_to(ROOT)),
            "clean_word_count": count,
            "excerpt_count": 1,
            "total_chunk_count": 1,
            "quality_filtered_chunk_count": 0,
            "processed_at": processed_at,
            "canonical_author": canonical_author_value,
            "canonical_title": canonical_title_value,
            "canonical_work_key": f"{canonical_author_value}::{canonical_title_value}",
        }
        excerpt = {
            "id": f"{work_id}-excerpt-0001",
            "work_id": work_id,
            "gutenberg_id": piece["gutenberg_id"],
            "excerpt_index": 1,
            "title": piece["title"],
            "display_title": piece["title"],
            "work_title": piece["title"],
            "author": piece["author"],
            "form": piece["form"],
            "subjects": piece["subjects"],
            "labels": piece["labels"],
            "text": piece["text"].strip(),
            "chunk_type": "poem" if piece["form"] == "poetry" else "prose_excerpt",
            "word_count": count,
            "section_title": piece["title"],
            "section_index": 1,
            "section_excerpt_index": 1,
            "section_excerpt_count": 1,
            "excerpt_label": piece["title"],
            "media": piece["media"],
            "canonical_author": canonical_author_value,
            "canonical_work_title": canonical_title_value,
            "canonical_work_key": f"{canonical_author_value}::{canonical_title_value}",
        }
        works.append(work)
        excerpts.append(excerpt)
        embedding_inputs.append(embedding_input_for(work, excerpt))

    return works, excerpts, embedding_inputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Add curated public-domain ekphrastic pieces to the processed corpus.")
    parser.add_argument("--write-manifest-only", action="store_true")
    args = parser.parse_args()

    works, excerpts, embedding_inputs = build_records()
    CURATED_DIR.mkdir(parents=True, exist_ok=True)
    write_jsonl(CURATED_DIR / "ekphrastic_works.jsonl", works)
    write_jsonl(CURATED_DIR / "ekphrastic_excerpts.jsonl", excerpts)
    write_jsonl(CURATED_DIR / "ekphrastic_embedding_inputs.jsonl", embedding_inputs)

    if not args.write_manifest_only:
        upsert_records(WORKS_PATH, works)
        upsert_records(EXCERPTS_PATH, excerpts)
        upsert_records(EMBEDDING_INPUTS_PATH, embedding_inputs, key="excerpt_id")
        clear_processed_corpus_cache()
        clear_processed_embedding_cache()
        clear_processed_latent_factor_cache()

    print(
        f"Prepared {len(works)} ekphrastic works and {len(excerpts)} excerpts. "
        f"Manifest: {CURATED_DIR}"
    )


if __name__ == "__main__":
    main()
