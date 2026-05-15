from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
import re
from urllib.parse import quote

from app.schemas.recommendations import (
    ListeningRecommendationResponse,
    MusicCatalogResponse,
    MusicTrackResponse,
    PoemOfTheDayResponse,
    RecommendedWork,
)
from app.services.processed_corpus import ProcessedCorpusService, ProcessedExcerpt


GENERIC_POEM_TITLE_RE = re.compile(r"^(?:poem|section|excerpt)\s+\d+(?:,?\s+section\s+\d+)?$", re.IGNORECASE)
TOKEN_RE = re.compile(r"[a-z][a-z']{2,}")
POEM_OF_DAY_MIN_WORDS = 12
POEM_OF_DAY_MAX_WORDS = 220
EPIC_SECTION_TITLE_RE = re.compile(r"\b(?:book|canto)\s+(?:[ivxlcdm]+|\d+)\b", re.IGNORECASE)
EPIC_POEM_OF_DAY_TERMS = (
    "epic poetry",
    "epic poem",
    "the iliad",
    "the odyssey",
    "aeneid",
    "beowulf",
    "paradise lost",
    "faerie queene",
    "divine comedy",
    "inferno",
    "purgatorio",
    "paradiso",
    "mahabharata",
    "maha-bharata",
    "ramayana",
    "song of roland",
    "chanson de roland",
    "orlando furioso",
    "jerusalem delivered",
    "kalevala",
)

TONE_KEYWORDS: dict[str, set[str]] = {
    "romantic": {"love", "beloved", "heart", "beauty", "kiss", "romance", "sweet", "desire"},
    "melancholy": {"death", "sorrow", "grief", "lonely", "tears", "dark", "mourning", "memory"},
    "gothic": {"ghost", "terror", "horror", "haunted", "grave", "blood", "vampire", "night"},
    "pastoral": {"spring", "flower", "garden", "bird", "river", "forest", "meadow", "green"},
    "epic": {"king", "battle", "war", "sword", "knight", "hero", "gods", "troy"},
    "playful": {"laugh", "merry", "comic", "wit", "humor", "fairy", "child", "jest"},
    "contemplative": {"soul", "time", "thought", "dream", "silence", "memory", "mind", "spirit"},
    "dramatic": {"enter", "scene", "act", "tragedy", "lord", "queen", "cried", "voice"},
    "adventurous": {"ship", "island", "road", "adventure", "journey", "sea", "pirate", "quest"},
    "serene": {"moon", "gentle", "calm", "light", "evening", "sleep", "quiet", "soft"},
}

TONE_LABELS = {
    "romantic": "romantic and intimate",
    "melancholy": "melancholy and inward",
    "gothic": "shadowed and suspenseful",
    "pastoral": "pastoral and bright",
    "epic": "epic and ceremonial",
    "playful": "playful and quick-witted",
    "contemplative": "contemplative and reflective",
    "dramatic": "dramatic and theatrical",
    "adventurous": "adventurous and kinetic",
    "serene": "serene and nocturnal",
}


@dataclass(frozen=True)
class MusicTrack:
    id: str
    title: str
    composer: str
    performer: str
    duration: str
    filename: str
    source_url: str
    license: str
    tones: tuple[str, ...]

    @property
    def audio_url(self) -> str:
        return f"https://commons.wikimedia.org/wiki/Special:Redirect/file/{quote(self.filename)}"


def commons_file_url(filename: str) -> str:
    return f"https://commons.wikimedia.org/wiki/File:{quote(filename.replace(' ', '_'))}"


def commons_music_track(
    *,
    id: str,
    title: str,
    composer: str,
    performer: str,
    duration: str,
    filename: str,
    license: str,
    tones: tuple[str, ...],
) -> MusicTrack:
    return MusicTrack(
        id=id,
        title=title,
        composer=composer,
        performer=performer,
        duration=duration,
        filename=filename,
        source_url=commons_file_url(filename),
        license=license,
        tones=tones,
    )


TRACKS = [
    MusicTrack(
        id="chopin-nocturne-op9-2",
        title="Nocturne in E-flat major, Op. 9 No. 2",
        composer="Frederic Chopin",
        performer="Beeswaxcandle and Londonjackbooks",
        duration="3:23",
        filename="Chopin Nocturne Op 9 No 2.ogg",
        source_url="https://commons.wikimedia.org/wiki/File:Chopin_Nocturne_Op_9_No_2.ogg",
        license="CC BY-SA 3.0",
        tones=("romantic", "serene", "contemplative"),
    ),
    MusicTrack(
        id="beethoven-moonlight-1",
        title="Moonlight Sonata, I. Adagio sostenuto",
        composer="Ludwig van Beethoven",
        performer="Bernd Krueger",
        duration="6:00",
        filename="Beethoven Moonlight 1st movement.ogg",
        source_url="https://commons.wikimedia.org/wiki/File:Beethoven_Moonlight_1st_movement.ogg",
        license="CC BY-SA 2.0 DE",
        tones=("melancholy", "gothic", "dramatic", "serene"),
    ),
    MusicTrack(
        id="bach-cello-suite-5-prelude",
        title="Cello Suite No. 5, Prelude",
        composer="J. S. Bach",
        performer="Elias Goldstein",
        duration="6:10",
        filename="Bach - Cello Suite No. 5 - 1. Prelude.ogg",
        source_url="https://commons.wikimedia.org/wiki/File:Bach_-_Cello_Suite_No._5_-_1._Prelude.ogg",
        license="Open Audio License / CC BY-SA 2.0-compatible",
        tones=("contemplative", "gothic", "epic"),
    ),
    MusicTrack(
        id="mozart-nachtmusik-allegro",
        title="Eine kleine Nachtmusik, I. Allegro",
        composer="Wolfgang Amadeus Mozart",
        performer="Advent Chamber Orchestra",
        duration="5:55",
        filename="Mozart - Eine kleine Nachtmusik - 1. Allegro.ogg",
        source_url="https://commons.wikimedia.org/wiki/File:Mozart_-_Eine_kleine_Nachtmusik_-_1._Allegro.ogg",
        license="CC BY-SA 2.0",
        tones=("playful", "adventurous", "pastoral"),
    ),
    MusicTrack(
        id="tchaikovsky-swan-lake-scene",
        title="Swan Lake, Op. 20 No. 10, Scene",
        composer="Pyotr Ilyich Tchaikovsky",
        performer="John Barbirolli and the London Philharmonic Orchestra",
        duration="2:30",
        filename="Tchaikovsky Swan Lake Op.20 No.10. Scène.ogg",
        source_url="https://commons.wikimedia.org/wiki/File:Tchaikovsky_Swan_Lake_Op.20_No.10._Sc%C3%A8ne.ogg",
        license="Public domain recording on Wikimedia Commons",
        tones=("romantic", "dramatic", "melancholy"),
    ),
    MusicTrack(
        id="tchaikovsky-swan-lake-waltz",
        title="Swan Lake, Op. 20 No. 2, Waltz",
        composer="Pyotr Ilyich Tchaikovsky",
        performer="John Barbirolli and the London Philharmonic Orchestra",
        duration="4:24",
        filename="Tchaikovsky Swan Lake Op.20 No.2.Waltz.ogg",
        source_url="https://commons.wikimedia.org/wiki/File:Tchaikovsky_Swan_Lake_Op.20_No.2.Waltz.ogg",
        license="Public domain recording on Wikimedia Commons",
        tones=("pastoral", "romantic", "serene"),
    ),
    MusicTrack(
        id="tchaikovsky-swan-lake-czardas",
        title="Swan Lake, Op. 20 No. 20, Hungarian Dance",
        composer="Pyotr Ilyich Tchaikovsky",
        performer="John Barbirolli and the London Philharmonic Orchestra",
        duration="3:21",
        filename="Tchaikovsky Swan Lake Op.20 No.20. Hungarian Dance-Czardas.ogg",
        source_url="https://commons.wikimedia.org/wiki/File:Tchaikovsky_Swan_Lake_Op.20_No.20._Hungarian_Dance-Czardas.ogg",
        license="Public domain recording on Wikimedia Commons",
        tones=("adventurous", "epic", "playful"),
    ),
    MusicTrack(
        id="satie-gymnopedie-1",
        title="Gymnopedie No. 1",
        composer="Erik Satie",
        performer="Teknopazzo",
        duration="3:25",
        filename="Gymnopedie No. 1..ogg",
        source_url="https://commons.wikimedia.org/wiki/File:Gymnopedie_No._1..ogg",
        license="CC0 1.0",
        tones=("serene", "melancholy", "contemplative"),
    ),
    commons_music_track(
        id="beethoven-emperor-adagio",
        title="Piano Concerto No. 5, II. Adagio un poco mosso",
        composer="Ludwig van Beethoven",
        performer="Ursula Oppens and DuPage Symphony Orchestra",
        duration="6:59",
        filename="Beethoven Op. 73 - 2 Adagio.ogg",
        license="CC BY-SA 3.0",
        tones=("serene", "contemplative", "romantic"),
    ),
    commons_music_track(
        id="beethoven-emperor-rondo",
        title="Piano Concerto No. 5, III. Rondo",
        composer="Ludwig van Beethoven",
        performer="Ursula Oppens and DuPage Symphony Orchestra",
        duration="9:18",
        filename="Beethoven Op. 73 - 3 Rondo.ogg",
        license="CC BY-SA 3.0",
        tones=("epic", "adventurous", "playful"),
    ),
    commons_music_track(
        id="debussy-clair-de-lune",
        title="Clair de lune from Suite bergamasque",
        composer="Claude Debussy",
        performer="Laurens Goedhart",
        duration="5:04",
        filename="Clair de lune (Claude Debussy) Suite bergamasque.ogg",
        license="CC BY 3.0",
        tones=("serene", "romantic", "contemplative"),
    ),
    commons_music_track(
        id="debussy-deuxieme-arabesque",
        title="Deuxieme Arabesque",
        composer="Claude Debussy",
        performer="Patrizia Prati",
        duration="4:00",
        filename="Claude Debussy - Deuxième Arabesque - Patrizia Prati.ogg",
        license="CC BY-SA 4.0",
        tones=("pastoral", "playful", "serene"),
    ),
    commons_music_track(
        id="debussy-cahier-esquisses",
        title="D'un cahier d'esquisses",
        composer="Claude Debussy",
        performer="Eunmi Ko",
        duration="4:36",
        filename="Claude Debussy - D´un cahier d´esquisses - Eunmi Ko.ogg",
        license="CC BY-SA 4.0",
        tones=("contemplative", "melancholy", "serene"),
    ),
    commons_music_track(
        id="vivaldi-winter-largo",
        title="The Four Seasons: Winter, II. Largo",
        composer="Antonio Vivaldi",
        performer="John Harrison",
        duration="2:12",
        filename="11 - Vivaldi Winter mvt 2 Largo - John Harrison violin.ogg",
        license="CC BY-SA",
        tones=("serene", "melancholy", "contemplative"),
    ),
    commons_music_track(
        id="vivaldi-winter-allegro",
        title="The Four Seasons: Winter, III. Allegro",
        composer="Antonio Vivaldi",
        performer="John Harrison",
        duration="3:13",
        filename="12 - Vivaldi Winter mvt 3 Allegro - John Harrison violin.ogg",
        license="CC BY-SA",
        tones=("dramatic", "adventurous", "gothic"),
    ),
    commons_music_track(
        id="vivaldi-mandolin-concerto-rv425",
        title="Mandolin Concerto in C major, RV 425",
        composer="Antonio Vivaldi",
        performer="The Milan Baroque Soloists",
        duration="8:20",
        filename="Antonio Vivaldi, Mandolin Concerto in C major, RV 425.ogg",
        license="Public domain mark / PDM-owner",
        tones=("pastoral", "playful", "romantic"),
    ),
    commons_music_track(
        id="vivaldi-cello-concerto-g-1",
        title="Cello Concerto in G major, RV 413, I. Allegro",
        composer="Antonio Vivaldi",
        performer="Advent Chamber Orchestra with Stephen Balderston",
        duration="3:16",
        filename="Vivaldi - Cello Concerto Gmaj - 1. Allegro.ogg",
        license="CC BY-SA 2.0",
        tones=("adventurous", "pastoral", "epic"),
    ),
    commons_music_track(
        id="vivaldi-cello-concerto-g-2",
        title="Cello Concerto in G major, RV 413, II. Largo",
        composer="Antonio Vivaldi",
        performer="Advent Chamber Orchestra with Stephen Balderston",
        duration="3:58",
        filename="Vivaldi - Cello Concerto Gmaj - 2. Largo.ogg",
        license="CC BY-SA 2.0",
        tones=("melancholy", "contemplative", "serene"),
    ),
    commons_music_track(
        id="vivaldi-cello-concerto-g-3",
        title="Cello Concerto in G major, RV 413, III. Allegro",
        composer="Antonio Vivaldi",
        performer="Advent Chamber Orchestra with Stephen Balderston",
        duration="2:40",
        filename="Vivaldi - Cello Concerto Gmaj - 3. Allegro.ogg",
        license="CC BY-SA 2.0",
        tones=("playful", "adventurous", "pastoral"),
    ),
    commons_music_track(
        id="vivaldi-la-notte-1",
        title="La Notte, I",
        composer="Antonio Vivaldi",
        performer="Wikimedia Commons contributor",
        duration="1:11",
        filename="Antonio Vivaldi - La Notte - 1.ogg",
        license="CC BY-SA 3.0",
        tones=("gothic", "dramatic", "melancholy"),
    ),
    commons_music_track(
        id="vivaldi-la-notte-2",
        title="La Notte, II",
        composer="Antonio Vivaldi",
        performer="Wikimedia Commons contributor",
        duration="0:47",
        filename="Antonio Vivaldi - La Notte - 2.ogg",
        license="CC BY-SA 3.0",
        tones=("adventurous", "dramatic", "gothic"),
    ),
    commons_music_track(
        id="vivaldi-la-notte-3",
        title="La Notte, III",
        composer="Antonio Vivaldi",
        performer="Wikimedia Commons contributor",
        duration="0:45",
        filename="Antonio Vivaldi - La Notte - 3.ogg",
        license="CC BY-SA 3.0",
        tones=("serene", "gothic", "contemplative"),
    ),
    commons_music_track(
        id="vivaldi-la-notte-4",
        title="La Notte, IV",
        composer="Antonio Vivaldi",
        performer="Wikimedia Commons contributor",
        duration="0:57",
        filename="Antonio Vivaldi - La Notte - 4.ogg",
        license="CC BY-SA 3.0",
        tones=("dramatic", "adventurous", "playful"),
    ),
    commons_music_track(
        id="mozart-flute-quartet-1",
        title="Flute Quartet No. 1 in D major, I. Allegro",
        composer="Wolfgang Amadeus Mozart",
        performer="Wikimedia Commons contributor",
        duration="7:10",
        filename="Wolfgang Amadeus Mozart - Flute Quartet No. 1 in D Major - 1. Allegro.ogg",
        license="CC BY-SA 2.0",
        tones=("pastoral", "playful", "adventurous"),
    ),
    commons_music_track(
        id="mozart-flute-quartet-2",
        title="Flute Quartet No. 1 in D major, II. Adagio",
        composer="Wolfgang Amadeus Mozart",
        performer="Wikimedia Commons contributor",
        duration="2:29",
        filename="Wolfgang Amadeus Mozart - Flute Quartet No. 1 in D Major - 2. Adagio.ogg",
        license="CC BY-SA 2.0",
        tones=("serene", "romantic", "contemplative"),
    ),
    commons_music_track(
        id="mozart-flute-quartet-3",
        title="Flute Quartet No. 1 in D major, III. Rondeau",
        composer="Wolfgang Amadeus Mozart",
        performer="Wikimedia Commons contributor",
        duration="4:15",
        filename="Wolfgang Amadeus Mozart - Flute Quartet No. 1 in D Major - 3. Rondeau - Allegro.ogg",
        license="CC BY-SA 2.0",
        tones=("playful", "pastoral", "adventurous"),
    ),
    commons_music_track(
        id="mozart-kv421-1",
        title="String Quartet No. 15 in D minor, K. 421, I",
        composer="Wolfgang Amadeus Mozart",
        performer="Max Strub Quartett",
        duration="8:48",
        filename="02 Mozart KV 421 1.ogg",
        license="Public domain",
        tones=("dramatic", "contemplative", "melancholy"),
    ),
    commons_music_track(
        id="mozart-kv421-4",
        title="String Quartet No. 15 in D minor, K. 421, IV",
        composer="Wolfgang Amadeus Mozart",
        performer="Max Strub Quartett",
        duration="8:26",
        filename="06 Mozart KV 421 4.ogg",
        license="Public domain",
        tones=("playful", "dramatic", "romantic"),
    ),
    commons_music_track(
        id="chopin-etude-op10-3",
        title="Etude in E major, Op. 10 No. 3",
        composer="Frederic Chopin",
        performer="Martha Goldstein",
        duration="4:07",
        filename="Frederic Chopin - Opus 10 - Twelve Grand Etudes - E Major.ogg",
        license="CC BY-SA 2.0",
        tones=("romantic", "melancholy", "contemplative"),
    ),
    commons_music_track(
        id="chopin-etude-op10-12",
        title="Etude in C minor, Op. 10 No. 12",
        composer="Frederic Chopin",
        performer="Martha Goldstein",
        duration="2:44",
        filename="Frederic Chopin - Opus 10 - Twelve Grand Etudes - c minor.ogg",
        license="Public domain",
        tones=("dramatic", "epic", "adventurous"),
    ),
    commons_music_track(
        id="chopin-etude-op10-5",
        title="Etude in G-flat major, Op. 10 No. 5",
        composer="Frederic Chopin",
        performer="Martha Goldstein",
        duration="1:49",
        filename="Frederic Chopin - Opus 10 - Twelve Grand Etudes - G Flat Major.ogg",
        license="CC BY-SA 2.0",
        tones=("playful", "adventurous", "pastoral"),
    ),
    commons_music_track(
        id="chopin-etude-op10-9",
        title="Etude in F minor, Op. 10 No. 9",
        composer="Frederic Chopin",
        performer="Martha Goldstein",
        duration="1:59",
        filename="Frederic Chopin - Opus 10 - Twelve Grand Etudes - f minor.ogg",
        license="CC BY-SA 2.0",
        tones=("melancholy", "dramatic", "contemplative"),
    ),
    commons_music_track(
        id="chopin-etude-op10-4",
        title="Etude in C-sharp minor, Op. 10 No. 4",
        composer="Frederic Chopin",
        performer="Muriel Nguyen Xuan",
        duration="2:31",
        filename="Muriel-Nguyen-Xuan-Chopin-etude-opus10-4.ogg",
        license="CC BY-SA 4.0",
        tones=("adventurous", "dramatic", "epic"),
    ),
    commons_music_track(
        id="bach-goldberg-aria",
        title="Goldberg Variations, Aria",
        composer="J. S. Bach",
        performer="Bradley Lehman / Dave Grossman",
        duration="3:48",
        filename="988-aria.lehman1.ogg",
        license="Public domain",
        tones=("serene", "contemplative", "romantic"),
    ),
    commons_music_track(
        id="bach-goldberg-var-1",
        title="Goldberg Variations, Variation 1",
        composer="J. S. Bach",
        performer="Bradley Lehman / Dave Grossman",
        duration="2:01",
        filename="988-v01.lehman1.ogg",
        license="Public domain",
        tones=("playful", "pastoral", "adventurous"),
    ),
    commons_music_track(
        id="bach-goldberg-var-5",
        title="Goldberg Variations, Variation 5",
        composer="J. S. Bach",
        performer="Bradley Lehman / Dave Grossman",
        duration="2:01",
        filename="988-v05.lehman1.ogg",
        license="Public domain",
        tones=("adventurous", "playful", "epic"),
    ),
    commons_music_track(
        id="bach-goldberg-var-13",
        title="Goldberg Variations, Variation 13",
        composer="J. S. Bach",
        performer="Bradley Lehman / Dave Grossman",
        duration="5:18",
        filename="988-v13.lehman1.ogg",
        license="Public domain",
        tones=("romantic", "serene", "contemplative"),
    ),
    commons_music_track(
        id="bach-passacaglia-pratt",
        title="Passacaglia and Fugue in C minor, BWV 582",
        composer="J. S. Bach",
        performer="Awadagin Pratt",
        duration="11:59",
        filename="20091104 Awadagin Pratt - Bach's Passacaglia and Fugue in C minor, BWV 582.ogg",
        license="Public domain",
        tones=("epic", "gothic", "dramatic", "contemplative"),
    ),
]


class DailyFeatureService:
    def __init__(self, corpus_service: ProcessedCorpusService | None = None) -> None:
        self.corpus_service = corpus_service or ProcessedCorpusService()

    def poem_of_the_day(self, target_date: date | None = None) -> PoemOfTheDayResponse | None:
        target_date = target_date or date.today()
        candidates = [
            excerpt
            for excerpt in self.corpus_service.list_excerpts()
            if is_poem_of_day_candidate(excerpt)
        ]
        if not candidates:
            return None

        preferred = [excerpt for excerpt in candidates if not GENERIC_POEM_TITLE_RE.match(excerpt.title)]
        selected_pool = preferred or candidates
        selected = min(
            selected_pool,
            key=lambda excerpt: daily_rank_key(target_date.isoformat(), excerpt),
        )
        return PoemOfTheDayResponse(
            date=target_date.isoformat(),
            work=RecommendedWork(
                id=selected.id,
                title=display_daily_poem_title(selected),
                author=selected.author,
                form=selected.form,
                reason="Chosen from the poetry corpus for **today's reading**",
                excerpt=selected.preview,
                tags=poem_tags(selected),
                work_title=selected.work_title,
                section_title=selected.section_title,
                excerpt_label=selected.excerpt_label,
            ),
        )


    def music_catalog(
        self,
        preferred_tones: list[str] | None = None,
        preferred_composers: list[str] | None = None,
    ) -> MusicCatalogResponse:
        tones = {tone: TONE_LABELS[tone] for tone in sorted(TONE_LABELS)}
        composers = sorted({track.composer for track in TRACKS})
        preferred_tone_set = {tone.strip().lower() for tone in preferred_tones or [] if tone.strip()}
        preferred_composer_set = {
            composer.strip().lower()
            for composer in preferred_composers or []
            if composer.strip()
        }
        tracks = sorted(
            TRACKS,
            key=lambda track: music_preference_rank(
                track,
                preferred_tone_set,
                preferred_composer_set,
            ),
        )
        return MusicCatalogResponse(
            tones=tones,
            composers=composers,
            tracks=[track_response(track, track.tones[0]) for track in tracks],
        )

    def listening_for_item(self, item_id: str) -> ListeningRecommendationResponse | None:
        item = self.corpus_service.find_reader_item(item_id)
        if item is None:
            return None

        tone, evidence = infer_tone(item)
        tracks = recommend_tracks(tone)
        return ListeningRecommendationResponse(
            item_id=item.id,
            title=display_title(item),
            author=item.author,
            tone=tone,
            tone_label=TONE_LABELS.get(tone, tone),
            summary=listening_summary(tone, evidence),
            tracks=[track_response(track, tone) for track in tracks],
        )


def music_preference_rank(
    track: MusicTrack,
    preferred_tones: set[str],
    preferred_composers: set[str],
) -> tuple[int, str, str]:
    tone_miss = 0 if not preferred_tones or preferred_tones.intersection(track.tones) else 1
    composer_miss = (
        0
        if not preferred_composers or track.composer.lower() in preferred_composers
        else 1
    )
    return (tone_miss + composer_miss, track.composer, track.title)


def is_poem_of_day_candidate(excerpt: ProcessedExcerpt) -> bool:
    if excerpt.form.lower() != "poetry":
        return False
    if not POEM_OF_DAY_MIN_WORDS <= excerpt.word_count <= POEM_OF_DAY_MAX_WORDS:
        return False

    title_context = " ".join(
        part
        for part in [
            excerpt.title,
            excerpt.work_title,
            excerpt.section_title or "",
        ]
        if part
    ).lower()
    metadata_context = " ".join(
        [
            title_context,
            " ".join(excerpt.subjects),
            " ".join(label.get("label", "") for label in excerpt.labels),
        ]
    ).lower()
    if any(term in metadata_context for term in EPIC_POEM_OF_DAY_TERMS):
        return False
    return not EPIC_SECTION_TITLE_RE.search(title_context)


def daily_rank_key(day: str, excerpt: ProcessedExcerpt) -> str:
    return sha256(f"{day}:{excerpt.id}".encode("utf-8")).hexdigest()


def infer_tone(excerpt: ProcessedExcerpt) -> tuple[str, list[str]]:
    haystack = " ".join(
        [
            excerpt.title,
            excerpt.work_title,
            excerpt.form,
            " ".join(excerpt.subjects),
            " ".join(label.get("label", "") for label in excerpt.labels),
            excerpt.text[:4000],
        ]
    ).lower()
    tokens = TOKEN_RE.findall(haystack)
    counts = Counter(tokens)
    scores: dict[str, int] = {}
    evidence_by_tone: dict[str, list[str]] = {}
    for tone, keywords in TONE_KEYWORDS.items():
        matched = [keyword for keyword in keywords if counts[keyword] > 0 or keyword in haystack]
        subject_boost = 2 if any(keyword in haystack for keyword in keywords) else 0
        scores[tone] = sum(counts[keyword] for keyword in keywords) + subject_boost
        evidence_by_tone[tone] = matched[:4]

    if excerpt.form.lower() == "drama":
        scores["dramatic"] += 2
    if "love stories" in haystack or "romance" in haystack:
        scores["romantic"] += 3
    if "science fiction" in haystack:
        scores["adventurous"] += 2
    if "gothic" in haystack:
        scores["gothic"] += 3
    if excerpt.form.lower() == "poetry":
        scores["contemplative"] += 1

    tone = max(scores, key=lambda key: (scores[key], key))
    if scores[tone] <= 1:
        tone = "contemplative"
    return tone, evidence_by_tone.get(tone, [])


def recommend_tracks(tone: str, limit: int = 4) -> list[MusicTrack]:
    return sorted(
        TRACKS,
        key=lambda track: (tone not in track.tones, track.tones.index(tone) if tone in track.tones else 99, track.title),
    )[:limit]


def track_response(track: MusicTrack, tone: str) -> MusicTrackResponse:
    tone_label = TONE_LABELS.get(tone, tone)
    article = "an" if tone_label[:1].lower() in {"a", "e", "i", "o", "u"} else "a"
    return MusicTrackResponse(
        id=track.id,
        title=track.title,
        composer=track.composer,
        performer=track.performer,
        duration=track.duration,
        tone_tags=list(track.tones),
        audio_url=track.audio_url,
        source_url=track.source_url,
        license=track.license,
        reason=f"Recommended for {article} {tone_label} passage.",
    )


def listening_summary(tone: str, evidence: list[str]) -> str:
    label = TONE_LABELS.get(tone, tone)
    if evidence:
        return f"This passage reads as {label}, with signals like {', '.join(evidence)}."
    return f"This passage reads as {label} from its form, metadata, and language pattern."


def poem_tags(excerpt: ProcessedExcerpt) -> list[str]:
    labels = [label.get("label", "") for label in excerpt.labels]
    tags: list[str] = []
    for tag in ["Poetry", *[label.title() for label in labels if label]]:
        if tag not in tags:
            tags.append(tag)
    return tags[:5] or ["Poetry"]


def display_daily_poem_title(excerpt: ProcessedExcerpt) -> str:
    if GENERIC_POEM_TITLE_RE.match(excerpt.title) and excerpt.work_title:
        return excerpt.work_title
    return display_title(excerpt)


def display_title(excerpt: ProcessedExcerpt) -> str:
    if excerpt.form.lower() == "poetry":
        return excerpt.title
    return excerpt.work_title or excerpt.title
