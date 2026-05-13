# Recommendation Roadmap

## Phase 1: Content-Based

The MVP should recommend from user preferences and text similarity.

Inputs:

- User-selected genres, themes, moods, authors, difficulty, and length.
- Work and excerpt metadata.
- Text embeddings for excerpts and whole works using `text-embedding-3-small` at 1536 dimensions.
- PostgreSQL `pgvector` storage for nearest-neighbor lookup.

Ranking:

- Compute similarity between the user profile vector and excerpt vectors.
- Add metadata boosts for explicit preferences.
- Deduplicate by work so rows do not repeat the same book too often.
- Diversify by genre, period, author, and form.

Implementation notes:

- `read_start`, `like`, `save`, and `skip` events are logged immediately.
- Interaction-based recommendation should wait until there is real behavior.
- The current rule-based classifier seeds form, genre, and mood labels until model-based classification is needed.
- The current API route vector-ranks demo works with a deterministic local vectorizer so the app remains runnable without an API key; production excerpt ranking should use OpenAI embeddings and pgvector.

## Phase 2: Interaction-Aware

Add behavior once enough usage exists.

Signals:

- Opened work.
- Read duration.
- Scroll depth.
- Completion.
- Like/dislike.
- Save.
- Search.
- Follow author/genre/user.
- Skip or quick bounce.

## Phase 3: Hybrid Ranking

Blend:

- Content similarity.
- Collaborative filtering.
- Popularity and freshness.
- User intent by surface: For You, Continue Reading, Genre Row, Search, Profile.

The recommender should keep explanations available, such as "because you like gothic romance" or "similar in tone to your saved poems."
