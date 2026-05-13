# Backend

FastAPI backend for ingestion, recommendation, accounts, and reading interactions.

## Local Development

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

The first scaffold uses placeholder data so the API shape can be developed before the database and embeddings are fully wired.

## Database

From the repository root:

```bash
docker compose up -d postgres
backend/.venv/bin/python scripts/init_database.py
backend/.venv/bin/python scripts/sync_processed_corpus_to_db.py
```

The database stores Gutenberg works/excerpts, classification labels, future
embedding vectors, users, preferences, interactions, and saved excerpt folders.


## Media and Corpus Artifact Storage

The default local prototype keeps uploaded profile/post media inline in the JSON account store. For staging or production, set:

```bash
MEDIA_STORAGE_BACKEND=local
MEDIA_PUBLIC_BASE_URL=http://localhost:8000/media
```

or configure `MEDIA_STORAGE_BACKEND=s3` with the `OBJECT_STORAGE_*` variables in `.env.example`.

Corpus artifacts can be synced with:

```bash
backend/.venv/bin/python scripts/sync_corpus_artifacts_to_storage.py
```

Run `scripts/check_deployment_readiness.py` before publishing to verify corpus files, storage settings, pgvector, database counts, and vector indexing.
