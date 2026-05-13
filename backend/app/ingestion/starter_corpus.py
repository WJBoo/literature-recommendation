from __future__ import annotations

from dataclasses import dataclass, field

from app.ingestion.metadata import GutenbergWorkMetadata


@dataclass(frozen=True)
class StarterCorpusWork:
    gutenberg_id: str
    title: str
    authors: list[str]
    form: str
    subjects: list[str] = field(default_factory=list)
    bookshelves: list[str] = field(default_factory=list)
    start_patterns: list[str] = field(default_factory=list)
    language: str = "en"

    @property
    def work_id(self) -> str:
        return f"gutenberg-{self.gutenberg_id}"

    def to_metadata(self) -> GutenbergWorkMetadata:
        return GutenbergWorkMetadata(
            gutenberg_id=self.gutenberg_id,
            title=self.title,
            authors=self.authors,
            language=self.language,
            subjects=self.subjects,
            bookshelves=[*self.bookshelves, self.form],
        )


STARTER_CORPUS: list[StarterCorpusWork] = [
    StarterCorpusWork(
        gutenberg_id="1342",
        title="Pride and Prejudice",
        authors=["Jane Austen"],
        form="prose",
        subjects=["romance", "satire", "manners", "courtship", "social class"],
        start_patterns=[r"It is a truth universally acknowledged"],
    ),
    StarterCorpusWork(
        gutenberg_id="84",
        title="Frankenstein",
        authors=["Mary Wollstonecraft Shelley"],
        form="prose",
        subjects=["gothic", "science", "ambition", "creation", "responsibility"],
        start_patterns=[r"Letter 1\s+_To Mrs\. Saville, England\._"],
    ),
    StarterCorpusWork(
        gutenberg_id="2701",
        title="Moby-Dick",
        authors=["Herman Melville"],
        form="prose",
        subjects=["adventure", "sea", "obsession", "philosophy", "epic"],
        start_patterns=[r"Call me Ishmael"],
    ),
    StarterCorpusWork(
        gutenberg_id="11",
        title="Alice's Adventures in Wonderland",
        authors=["Lewis Carroll"],
        form="prose",
        subjects=["fantasy", "nonsense", "childhood", "satire"],
        start_patterns=[r"Alice was beginning to get very tired"],
    ),
    StarterCorpusWork(
        gutenberg_id="1661",
        title="The Adventures of Sherlock Holmes",
        authors=["Arthur Conan Doyle"],
        form="prose",
        subjects=["mystery", "detective", "logic", "crime"],
        start_patterns=[r"To Sherlock Holmes she is always _the_ woman"],
    ),
    StarterCorpusWork(
        gutenberg_id="98",
        title="A Tale of Two Cities",
        authors=["Charles Dickens"],
        form="prose",
        subjects=["historical fiction", "revolution", "sacrifice", "justice"],
        start_patterns=[r"It was the best of times"],
    ),
    StarterCorpusWork(
        gutenberg_id="5200",
        title="Metamorphosis",
        authors=["Franz Kafka"],
        form="prose",
        subjects=["modernism", "alienation", "family", "absurd"],
        start_patterns=[r"One morning, when Gregor Samsa"],
    ),
    StarterCorpusWork(
        gutenberg_id="174",
        title="The Picture of Dorian Gray",
        authors=["Oscar Wilde"],
        form="prose",
        subjects=["gothic", "aestheticism", "beauty", "morality"],
        start_patterns=[r"The studio was filled with the rich odour"],
    ),
    StarterCorpusWork(
        gutenberg_id="345",
        title="Dracula",
        authors=["Bram Stoker"],
        form="prose",
        subjects=["gothic", "horror", "vampires", "letters"],
        start_patterns=[r"_3 May\. Bistritz\._"],
    ),
    StarterCorpusWork(
        gutenberg_id="76",
        title="Adventures of Huckleberry Finn",
        authors=["Mark Twain"],
        form="prose",
        subjects=["adventure", "satire", "river", "friendship"],
        start_patterns=[r"CHAPTER I\.\s+You .on.t know about me"],
    ),
    StarterCorpusWork(
        gutenberg_id="1041",
        title="Shakespeare's Sonnets",
        authors=["William Shakespeare"],
        form="poetry",
        subjects=["poetry", "love", "time", "beauty", "memory"],
        bookshelves=["Poetry"],
        start_patterns=[r"^I\s+From fairest creatures"],
    ),
    StarterCorpusWork(
        gutenberg_id="16328",
        title="Beowulf: An Anglo-Saxon Epic Poem",
        authors=["J. Lesslie Hall"],
        form="poetry",
        subjects=["epic poetry", "hero", "battle", "myth", "fate"],
        bookshelves=["Poetry"],
        start_patterns=[r"Lo! the Spear-Danes"],
    ),
    StarterCorpusWork(
        gutenberg_id="158",
        title="Emma",
        authors=["Jane Austen"],
        form="prose",
        subjects=["romance", "manners", "social class", "comedy", "courtship"],
        start_patterns=[r"Emma Woodhouse, handsome, clever, and rich"],
    ),
    StarterCorpusWork(
        gutenberg_id="161",
        title="Sense and Sensibility",
        authors=["Jane Austen"],
        form="prose",
        subjects=["romance", "family", "inheritance", "manners", "sisters"],
        start_patterns=[r"The family of Dashwood had long been settled"],
    ),
    StarterCorpusWork(
        gutenberg_id="1260",
        title="Jane Eyre",
        authors=["Charlotte Bronte"],
        form="prose",
        subjects=["gothic", "romance", "independence", "class", "memory"],
        start_patterns=[r"There was no possibility of taking a walk"],
    ),
    StarterCorpusWork(
        gutenberg_id="768",
        title="Wuthering Heights",
        authors=["Emily Bronte"],
        form="prose",
        subjects=["gothic", "romance", "revenge", "family", "moorland"],
        start_patterns=[r"I have just returned from a visit to my landlord"],
    ),
    StarterCorpusWork(
        gutenberg_id="1400",
        title="Great Expectations",
        authors=["Charles Dickens"],
        form="prose",
        subjects=["coming of age", "class", "crime", "memory", "ambition"],
        start_patterns=[r"My father's family name being Pirrip"],
    ),
    StarterCorpusWork(
        gutenberg_id="829",
        title="Gulliver's Travels",
        authors=["Jonathan Swift"],
        form="prose",
        subjects=["satire", "adventure", "travel", "politics", "fantasy"],
        start_patterns=[r"My father had a small estate"],
    ),
    StarterCorpusWork(
        gutenberg_id="74",
        title="The Adventures of Tom Sawyer",
        authors=["Mark Twain"],
        form="prose",
        subjects=["adventure", "childhood", "satire", "friendship", "river"],
        start_patterns=[r"TOM!"],
    ),
    StarterCorpusWork(
        gutenberg_id="120",
        title="Treasure Island",
        authors=["Robert Louis Stevenson"],
        form="prose",
        subjects=["adventure", "pirates", "sea", "treasure", "coming of age"],
        start_patterns=[r"Squire Trelawney, Dr\. Livesey"],
    ),
    StarterCorpusWork(
        gutenberg_id="43",
        title="The Strange Case of Dr. Jekyll and Mr. Hyde",
        authors=["Robert Louis Stevenson"],
        form="prose",
        subjects=["gothic", "mystery", "duality", "science", "morality"],
        start_patterns=[r"Mr\. Utterson the lawyer"],
    ),
    StarterCorpusWork(
        gutenberg_id="35",
        title="The Time Machine",
        authors=["H. G. Wells"],
        form="prose",
        subjects=["science fiction", "time", "class", "future", "adventure"],
        start_patterns=[r"The Time Traveller"],
    ),
    StarterCorpusWork(
        gutenberg_id="36",
        title="The War of the Worlds",
        authors=["H. G. Wells"],
        form="prose",
        subjects=["science fiction", "invasion", "survival", "war", "fear"],
        start_patterns=[r"No one would have believed"],
    ),
    StarterCorpusWork(
        gutenberg_id="1952",
        title="The Yellow Wallpaper",
        authors=["Charlotte Perkins Gilman"],
        form="prose",
        subjects=["gothic", "psychology", "marriage", "confinement", "feminism"],
        start_patterns=[r"It is very seldom that mere ordinary people"],
    ),
    StarterCorpusWork(
        gutenberg_id="219",
        title="Heart of Darkness",
        authors=["Joseph Conrad"],
        form="prose",
        subjects=["imperialism", "river", "darkness", "memory", "moral ambiguity"],
        start_patterns=[r"The Nellie, a cruising yawl"],
    ),
    StarterCorpusWork(
        gutenberg_id="2554",
        title="Crime and Punishment",
        authors=["Fyodor Dostoyevsky"],
        form="prose",
        subjects=["crime", "guilt", "philosophy", "poverty", "redemption"],
        start_patterns=[r"On an exceptionally hot evening"],
    ),
    StarterCorpusWork(
        gutenberg_id="2591",
        title="Grimms' Fairy Tales",
        authors=["Jacob Grimm", "Wilhelm Grimm"],
        form="prose",
        subjects=["fairy tale", "folk tale", "magic", "family", "danger"],
        start_patterns=[r"THE GOLDEN BIRD"],
    ),
    StarterCorpusWork(
        gutenberg_id="45",
        title="Anne of Green Gables",
        authors=["L. M. Montgomery"],
        form="prose",
        subjects=["coming of age", "family", "friendship", "imagination", "rural life"],
        start_patterns=[r"Mrs\. Rachel Lynde lived just where"],
    ),
    StarterCorpusWork(
        gutenberg_id="215",
        title="The Call of the Wild",
        authors=["Jack London"],
        form="prose",
        subjects=["adventure", "wilderness", "survival", "instinct", "animals"],
        start_patterns=[r"Buck did not read the newspapers"],
    ),
    StarterCorpusWork(
        gutenberg_id="16",
        title="Peter Pan",
        authors=["J. M. Barrie"],
        form="prose",
        subjects=["fantasy", "childhood", "adventure", "memory", "family"],
        start_patterns=[r"All children, except one, grow up"],
    ),
    StarterCorpusWork(
        gutenberg_id="55",
        title="The Wonderful Wizard of Oz",
        authors=["L. Frank Baum"],
        form="prose",
        subjects=["fantasy", "quest", "friendship", "home", "magic"],
        start_patterns=[r"Dorothy lived in the midst"],
    ),
    StarterCorpusWork(
        gutenberg_id="17396",
        title="The Secret Garden",
        authors=["Frances Hodgson Burnett"],
        form="prose",
        subjects=["childhood", "healing", "garden", "family", "friendship"],
        start_patterns=[r"When Mary Lennox was sent to Misselthwaite Manor"],
    ),
    StarterCorpusWork(
        gutenberg_id="1524",
        title="Hamlet",
        authors=["William Shakespeare"],
        form="drama",
        subjects=["tragedy", "revenge", "grief", "madness", "power"],
        start_patterns=[r"ACT I"],
    ),
    StarterCorpusWork(
        gutenberg_id="1513",
        title="Romeo and Juliet",
        authors=["William Shakespeare"],
        form="drama",
        subjects=["tragedy", "romance", "family", "fate", "youth"],
        start_patterns=[r"Two households, both alike in dignity"],
    ),
    StarterCorpusWork(
        gutenberg_id="2542",
        title="A Doll's House",
        authors=["Henrik Ibsen"],
        form="drama",
        subjects=["marriage", "identity", "freedom", "society", "family"],
        start_patterns=[r"ACT I"],
    ),
    StarterCorpusWork(
        gutenberg_id="1727",
        title="The Odyssey",
        authors=["Homer"],
        form="poetry",
        subjects=["epic poetry", "journey", "homecoming", "myth", "sea"],
        bookshelves=["Poetry"],
        start_patterns=[r"Tell me, O Muse"],
    ),
    StarterCorpusWork(
        gutenberg_id="6130",
        title="The Iliad",
        authors=["Homer"],
        form="poetry",
        subjects=["epic poetry", "war", "honor", "wrath", "myth"],
        bookshelves=["Poetry"],
        start_patterns=[r"Achilles[’'] wrath, to Greece the direful spring"],
    ),
    StarterCorpusWork(
        gutenberg_id="8800",
        title="The Divine Comedy",
        authors=["Dante Alighieri"],
        form="poetry",
        subjects=["epic poetry", "journey", "spirituality", "justice", "afterlife"],
        bookshelves=["Poetry"],
        start_patterns=[r"In the midway of this our mortal life"],
    ),
]


def gutenberg_text_url_candidates(gutenberg_id: str) -> list[str]:
    return [
        f"https://www.gutenberg.org/ebooks/{gutenberg_id}.txt.utf-8",
        f"https://www.gutenberg.org/files/{gutenberg_id}/{gutenberg_id}-0.txt",
        f"https://www.gutenberg.org/files/{gutenberg_id}/{gutenberg_id}.txt",
        f"https://www.gutenberg.org/cache/epub/{gutenberg_id}/pg{gutenberg_id}.txt",
    ]
