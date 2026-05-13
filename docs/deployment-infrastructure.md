# Deployment Infrastructure

Linguaphilia is now shaped so the same code can run locally, in a small beta, and later against a much larger Gutenberg-scale corpus. The goal is not a huge distributed system yet; it is to keep the pieces swappable before the corpus and user activity grow.

## Required Services

### PostgreSQL + pgvector

Use managed Postgres with the `vector` extension enabled. The local `docker-compose.yml` uses `pgvector/pgvector:pg16`, which mirrors the production requirement.

Runtime tables cover works, excerpts, classifications, embeddings, users, preferences, interactions, messages, submissions, saved folders, saved excerpts, ingestion runs, and corpus artifact manifests.

```bash
docker compose up -d postgres
backend/.venv/bin/python scripts/init_database.py
backend/.venv/bin/python scripts/sync_processed_corpus_to_db.py --prune
backend/.venv/bin/python scripts/generate_excerpt_embeddings.py --provider hashing --write-db
```

For production, set:

```bash
DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST:5432/DBNAME
RECOMMENDATION_VECTOR_BACKEND=auto
```

The API tries pgvector first and falls back to processed JSONL if the database is unavailable. For a public beta, aim for pgvector to be the normal path, not the fallback.

### Object Storage

Use S3-compatible storage for uploaded media and large corpus artifacts. Good options are AWS S3, Cloudflare R2, Fly volumes plus S3, or MinIO for local testing.

Local prototype mode keeps media inline:

```bash
MEDIA_STORAGE_BACKEND=inline
```

Local file-backed staging mode writes uploads under `data/uploads` and serves them from the backend:

```bash
MEDIA_STORAGE_BACKEND=local
MEDIA_UPLOAD_DIR=../data/uploads
MEDIA_PUBLIC_BASE_URL=http://localhost:8000/media
```

S3/R2/MinIO mode:

```bash
MEDIA_STORAGE_BACKEND=s3
OBJECT_STORAGE_BUCKET=linguaphilia
OBJECT_STORAGE_REGION=auto
OBJECT_STORAGE_ENDPOINT_URL=https://ACCOUNT_ID.r2.cloudflarestorage.com
OBJECT_STORAGE_ACCESS_KEY_ID=...
OBJECT_STORAGE_SECRET_ACCESS_KEY=...
OBJECT_STORAGE_PUBLIC_BASE_URL=https://media.example.com
OBJECT_STORAGE_CORPUS_PREFIX=corpus
```

The backend accepts the same frontend payloads, uploads data URLs when storage is enabled, and stores renderable URLs in account/profile/post records.

## Repeatable Corpus Pipeline

Use this command to run the full staging corpus path in order:

```bash
backend/.venv/bin/python scripts/prepare_deployment_corpus.py \
  --target-works 1500 \
  --embedding-provider hashing \
  --sync-artifacts
```

For a dry run that prints commands without executing them:

```bash
backend/.venv/bin/python scripts/prepare_deployment_corpus.py --dry-run --sync-artifacts
```

The pipeline performs:

1. Bulk Gutenberg ingest.
2. Canonicalization.
3. Quality filtering.
4. Excerpt embedding generation.
5. Latent-factor generation.
6. Database initialization.
7. Corpus/excerpt sync to Postgres.
8. Embedding sync to pgvector.
9. Optional artifact sync to local/S3 storage.
10. Recommendation benchmark.

To sync existing corpus artifacts without re-ingesting:

```bash
MEDIA_STORAGE_BACKEND=local backend/.venv/bin/python scripts/sync_corpus_artifacts_to_storage.py
```

Add raw Gutenberg files too when storage capacity is ready:

```bash
MEDIA_STORAGE_BACKEND=s3 backend/.venv/bin/python scripts/sync_corpus_artifacts_to_storage.py \
  --include processed --include clean --include raw --write-db
```

## Readiness Check

Run this before publishing a test build:

```bash
backend/.venv/bin/python scripts/check_deployment_readiness.py
```

It reports processed corpus counts, storage mode, pgvector availability, synced DB row counts, and whether the excerpt embedding index exists.

## What Is Still Intentionally Not Overbuilt

- Account features still use the prototype JSON service at runtime unless a DB-backed account service is added. The SQL tables exist, but the current feature surface is broader than those tables.
- Search can remain Postgres/vector-backed for beta. Dedicated search infrastructure should wait until query behavior shows it is needed.
- The whole Gutenberg corpus should be ingested in batches, with benchmarks after each batch, rather than all at once before the recommendation UX stabilizes.
