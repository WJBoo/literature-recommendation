# Data Pipeline

## Gutenberg Access

Use Project Gutenberg's approved bulk access paths instead of crawling normal web pages. The intended sources are:

- Offline catalog metadata files.
- Robot harvest endpoints for approved file downloads.
- Mirrors for larger local collections.

The app should store source metadata with each work, including Gutenberg ID, title, author, language, subjects, and source URL.

## Processing Stages

1. Load catalog metadata.
2. Select a manageable corpus.
3. Download or import text/HTML files.
4. Clean boilerplate and normalize text.
5. Detect work shape: prose, poetry, drama, mixed, unknown.
6. Chunk text into excerpts.
7. Generate embeddings.
8. Store works, excerpts, metadata, and vectors.

## Scaling Plan

Use `scripts/ingest_bulk_gutenberg.py` for controlled corpus growth:

- 1,000 English literary works for recommendation quality and latency baselines.
- 5,000 works after moving nearest-neighbor lookup to PostgreSQL + pgvector.
- Larger corpus sizes only after replacing dense full-matrix latent-factor
  generation with a sparse or randomized approach.

After each bulk ingest, regenerate:

1. Canonical corpus files with `scripts/canonicalize_processed_corpus.py --write`.
2. `gutenberg_excerpt_embeddings.jsonl`.
3. `gutenberg_excerpt_latent_factors.json`.
4. `recommendation_benchmark.json`.

## Indexed Recommendation Storage

The file-backed recommender is useful as a fallback, but it scans every excerpt.
For larger corpora, run PostgreSQL with pgvector and sync the processed corpus:

```bash
docker compose up -d postgres
backend/.venv/bin/python scripts/init_database.py
backend/.venv/bin/python scripts/sync_processed_corpus_to_db.py
backend/.venv/bin/python scripts/generate_excerpt_embeddings.py --provider hashing --write-db
```

The API attempts pgvector nearest-neighbor retrieval first and falls back to
JSONL if the database is unavailable. `init_database.py` creates the pgvector
extension and an `ivfflat` cosine index on excerpt embeddings.

## Chunking Rules

Initial policy:

- Prose excerpts target 300-900 words.
- Poems up to 1500 words remain intact.
- Poems over 1500 words split on stanza or section boundaries where possible, then line boundaries, then word boundaries only as a last resort.
- Drama should prefer scene/speech boundaries.
- Excerpts should keep stable source offsets so reader pages can reconstruct context.

## Output Records

Each excerpt should include:

- Work ID.
- Excerpt ID.
- Text.
- Start/end offsets or logical section markers.
- Word count.
- Chunk type: full_poem, poem_section, prose_excerpt, chapter, scene, unknown.
- Metadata inherited from the work.


## Deployment Pipeline

Use `scripts/prepare_deployment_corpus.py` as the repeatable staging pipeline. It wraps ingestion, canonicalization, quality filtering, embedding generation, latent-factor generation, database sync, optional artifact storage sync, and benchmarking.

```bash
backend/.venv/bin/python scripts/prepare_deployment_corpus.py --target-works 1500 --sync-artifacts
```

Use `scripts/check_deployment_readiness.py` before publishing to confirm processed corpus counts, storage mode, pgvector availability, database row counts, and vector index creation.

Large raw/clean text files should be pushed to object storage with `scripts/sync_corpus_artifacts_to_storage.py` once `MEDIA_STORAGE_BACKEND=local` or `MEDIA_STORAGE_BACKEND=s3` is configured.
