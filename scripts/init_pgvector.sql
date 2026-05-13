CREATE EXTENSION IF NOT EXISTS vector;

-- SQLAlchemy owns table creation later, but this documents the required database extension.
-- Excerpt, work, and user profile embeddings should use vector(1536) for text-embedding-3-small.
