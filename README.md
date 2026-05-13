# Literature Recommendation Engine

A personalized literature discovery site for public-domain works and user-submitted writing.

The first version is designed around content-based recommendations: every work and excerpt gets cleaned, chunked, embedded, and matched against a user profile built from onboarding preferences. Later versions can blend in interaction-based signals such as likes, saves, reading time, completion, follows, and skips.

## Workspace Layout

```text
backend/              FastAPI app, ingestion pipeline, recommender logic
frontend/             Next.js app for discovery, reading, profile, posting, messaging
data/raw/gutenberg/   Local Gutenberg downloads and catalog files
data/processed/       Cleaned text, excerpts, embeddings, derived datasets
docs/                 Architecture and implementation notes
scripts/              Operational scripts for ingestion and seeding
```

## Current Scaffold

- FastAPI backend skeleton with health and recommendation routes.
- Gutenberg ingestion modules for metadata loading, text cleaning, and chunking.
- Poem-aware chunking rule: poems up to 1500 words are preserved intact.
- Content-based recommender service placeholder with deterministic demo behavior.
- Next.js frontend skeleton with a Spotify-like discovery homepage, reader route, onboarding, profile, messages, and posting pages.
- Backend chunking tests for the poem preservation rule and prose ordering.
- Documentation for architecture, data pipeline, and recommendation roadmap.

## Next Steps

1. Generate embeddings for works and excerpts.
2. Switch recommendation reads from JSONL fallback to PostgreSQL + pgvector.
3. Add account creation and preference persistence.
4. Blend saved/liked/passed excerpts into each user's recommendation profile.

## Starter Gutenberg Import

The starter corpus importer downloads a small curated set of Project Gutenberg texts,
cleans them, chunks them, classifies excerpts, and writes JSONL files under
`data/processed`.

```bash
cd "/Users/william/Desktop/Summer 2025/Literature Recommendation Engine"
backend/.venv/bin/python scripts/ingest_starter_gutenberg.py
```

Outputs:

- `data/raw/gutenberg/*.txt`
- `data/processed/gutenberg_clean/*.txt`
- `data/processed/gutenberg_works.jsonl`
- `data/processed/gutenberg_excerpts.jsonl`
- `data/processed/gutenberg_embedding_inputs.jsonl`

## Bulk Gutenberg Import

For recommendation performance testing, use the catalog-driven bulk importer. It
downloads the official compressed Gutenberg catalog, filters to English literary
texts, downloads a controlled batch, and rewrites the processed corpus files.

Preview the first 1,000-work candidate set without downloading texts:

```bash
cd "/Users/william/Desktop/Summer 2025/Literature Recommendation Engine"
backend/.venv/bin/python scripts/ingest_bulk_gutenberg.py --target-works 1000 --dry-run
```

Run the full 1,000-work ingestion:

```bash
cd "/Users/william/Desktop/Summer 2025/Literature Recommendation Engine"
backend/.venv/bin/python scripts/ingest_bulk_gutenberg.py --target-works 1000
backend/.venv/bin/python scripts/canonicalize_processed_corpus.py --write
backend/.venv/bin/python scripts/generate_excerpt_embeddings.py --provider hashing
backend/.venv/bin/python scripts/generate_latent_factors.py --factors 32 --max-terms 8000
backend/.venv/bin/python scripts/benchmark_recommendations.py --runs 5 --mode async
```

The importer writes download/processing failures to
`data/processed/gutenberg_bulk_failures.jsonl`, so large batches can be tuned
without stopping on the first bad source file.

By default the importer balances prose, poetry, and drama while prioritizing
high-scoring literary metadata. Add `--selection-mode score` to take the
highest-scoring catalog records directly. It also skips records whose author is
only `Unknown`, `Anonymous`, or `Various`; add `--allow-unknown-authors` if
anthology-style coverage matters more than author-profile quality. It skips
catalog records that are clearly split `Part`/`Volume` fragments and deduplicates
same-author titles; use `--allow-part-records` or `--allow-duplicate-titles` for
raw coverage.

`scripts/canonicalize_processed_corpus.py --write` annotates canonical
author/title keys and removes duplicate edition records from the processed
JSONL files before embeddings and latent factors are regenerated.

## Database Storage

The backend schema is SQLAlchemy-owned and targets PostgreSQL with `pgvector`.
The included `docker-compose.yml` starts a local database using the same
credentials as `.env.example`.

```bash
cd "/Users/william/Desktop/Summer 2025/Literature Recommendation Engine"
docker compose up -d postgres
backend/.venv/bin/python scripts/init_database.py
backend/.venv/bin/python scripts/sync_processed_corpus_to_db.py
backend/.venv/bin/python scripts/generate_excerpt_embeddings.py --provider hashing --write-db
```

Tables now cover works, excerpts, excerpt classifications, excerpt/work/user
embeddings, users, onboarding preferences, interactions, message threads,
user submissions, saved folders, and saved excerpts.

The recommendation endpoint now tries PostgreSQL + pgvector first when
available. If the database is down or unsynced, it automatically falls back to
the JSONL scorer. To force the file-backed path during debugging, set:

```bash
RECOMMENDATION_VECTOR_BACKEND=file
```

To benchmark the indexed path when Postgres is running:

```bash
cd "/Users/william/Desktop/Summer 2025/Literature Recommendation Engine"
backend/.venv/bin/python scripts/benchmark_recommendations.py --runs 1 --mode async
```

## Excerpt Embeddings

Generate one persisted vector per processed excerpt:

```bash
cd "/Users/william/Desktop/Summer 2025/Literature Recommendation Engine"
backend/.venv/bin/python scripts/generate_excerpt_embeddings.py --provider hashing
```

This writes `data/processed/gutenberg_excerpt_embeddings.jsonl`. If PostgreSQL
is running and the corpus has been synced to the database, add `--write-db` to
also upsert vectors into `excerpt_embeddings`.

## Prototype Accounts

Until PostgreSQL is available in the local shell, account data is stored in the
ignored file `data/processed/accounts.json`. The API supports:

- `POST /api/accounts/register`
- `POST /api/accounts/login`
- `GET /api/accounts/me`
- `PUT /api/accounts/preferences`

The frontend onboarding and profile pages use these routes to create an account,
sign in, save genres/forms/themes/moods/authors/books, and reuse the saved
profile when requesting recommendations.

## Deployment Infrastructure

For the current beta hosting path, use [Railway + Vercel + Cloudflare R2](docs/deploy-railway-vercel-cloudflare.md).


Before a public beta, use the production-shaped path documented in `docs/deployment-infrastructure.md`:

```bash
docker compose up -d postgres
backend/.venv/bin/python scripts/prepare_deployment_corpus.py --skip-ingest --sync-artifacts --dry-run
backend/.venv/bin/python scripts/check_deployment_readiness.py
```

Set `MEDIA_STORAGE_BACKEND=local` for local/staging uploaded media, or `MEDIA_STORAGE_BACKEND=s3` plus the `OBJECT_STORAGE_*` variables for S3/R2/MinIO. The backend will move profile/post data URLs into storage and keep renderable URLs in account records.

## Verification

Backend scaffold checks:

```bash
cd backend
python -m unittest discover -s tests
```

Frontend verification on this machine should use the project-local Node runtime under `.tools/`:

```bash
cd frontend
PATH="../.tools/node/node-v24.14.0-darwin-arm64/bin:$PATH" ../.tools/node/node-v24.14.0-darwin-arm64/bin/npm run dev
```

The `.tools/` directory is ignored because it contains local runtime tooling, not application source.
