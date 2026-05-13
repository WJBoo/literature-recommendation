# Deploying Linguaphilia with Railway, Vercel, and Cloudflare R2

This is the intended beta stack:

- Backend API: Railway Docker service
- Database/vector index: Railway PostgreSQL with `pgvector`
- Frontend: Vercel, rooted at `frontend/`
- Uploaded media: Cloudflare R2 using its S3-compatible API

The app has been adjusted so the deployed backend can read the corpus from Postgres instead of requiring the large local JSONL corpus files in the Docker image.

## 1. Cloudflare R2

Create the media bucket first because Railway needs these values as environment variables.

1. In Cloudflare, create an R2 bucket, for example `linguaphilia-media`.
2. Create an R2 API token with Object Read & Write access scoped to that bucket.
3. Copy these values:
   - Access Key ID
   - Secret Access Key
   - S3 endpoint, shaped like `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`
4. Enable public access for rendered images/videos. For a beta, the `r2.dev` public URL is acceptable. For production, connect a custom domain.

Railway variables from this step:

```bash
MEDIA_STORAGE_BACKEND=s3
OBJECT_STORAGE_BUCKET=linguaphilia-media
OBJECT_STORAGE_REGION=auto
OBJECT_STORAGE_ENDPOINT_URL=https://<ACCOUNT_ID>.r2.cloudflarestorage.com
OBJECT_STORAGE_ACCESS_KEY_ID=<access-key-id>
OBJECT_STORAGE_SECRET_ACCESS_KEY=<secret-access-key>
OBJECT_STORAGE_PUBLIC_BASE_URL=https://<public-r2-domain>
OBJECT_STORAGE_CORPUS_PREFIX=corpus
```

## 2. Railway Backend

The repo now has:

- `Dockerfile` for the FastAPI backend
- `railway.json` with Dockerfile build settings and `/api/health` healthcheck
- database URL normalization for Railway's plain `postgresql://...` URLs

In Railway:

1. Create a new project.
2. Add a PostgreSQL service.
3. Add a backend service from the GitHub repo, or deploy locally with `railway up`.
4. Make sure the backend service uses the repo root so it can see `Dockerfile` and `railway.json`.
5. Add these backend variables:

```bash
APP_ENV=production
EMBEDDING_PROVIDER=hashing
EMBEDDING_MODEL=local-hashing-v1
EMBEDDING_DIMENSIONS=1536
RECOMMENDATION_VECTOR_BACKEND=auto
RECOMMENDATION_VECTOR_CANDIDATE_LIMIT=600
ACCOUNT_STORE_PATH=/app/data/processed/accounts.json
CORS_ORIGINS=["https://<your-vercel-app>.vercel.app"]
```

Railway should inject `DATABASE_URL` from its PostgreSQL service. If not, copy the PostgreSQL service's connection URL into the backend service variables.

### Seed Railway Postgres from Local Data

Because the corpus files are intentionally not committed to Git, seed Railway Postgres from your local machine using Railway env vars. After installing/logging into the Railway CLI and linking the project/service:

```bash
railway run backend/.venv/bin/python scripts/init_database.py
railway run backend/.venv/bin/python scripts/sync_processed_corpus_to_db.py --prune
railway run backend/.venv/bin/python scripts/generate_excerpt_embeddings.py --provider hashing --write-db
railway run backend/.venv/bin/python scripts/check_deployment_readiness.py
```

That pushes the current local corpus and vectors into the Railway database. The deployed API can then use pgvector without needing the local JSONL artifacts in the image.

## 3. Vercel Frontend

In Vercel:

1. Import the same GitHub repo.
2. Set Root Directory to `frontend`.
3. Vercel should detect Next.js. The repo also includes `frontend/vercel.json`.
4. Add this environment variable in Vercel Project Settings:

```bash
NEXT_PUBLIC_API_BASE_URL=https://<your-railway-backend>.up.railway.app
```

After Vercel gives you the frontend URL, return to Railway and update:

```bash
CORS_ORIGINS=["https://<your-vercel-app>.vercel.app"]
```

Then redeploy the Railway backend so the CORS update is active.

## 4. Post-Deploy Checks

Backend:

```bash
curl https://<your-railway-backend>.up.railway.app/api/health
```

Expected:

```json
{"status":"ok"}
```

Frontend:

- Open the Vercel URL.
- Confirm Discover loads recommendations.
- Click into an excerpt.
- Create a test account.
- Upload a small profile image or post image and confirm the resulting URL comes from R2.

## Current Caveat

The broad account/social feature set still uses the JSON account store. On Railway's Docker service this is acceptable for a very small smoke test, but it is not the final durable account architecture. Before inviting real users, either attach persistent storage for `ACCOUNT_STORE_PATH` or complete the DB-backed account service migration.
