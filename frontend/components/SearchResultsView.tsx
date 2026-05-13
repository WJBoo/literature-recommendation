"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  fetchAccountDirectory,
  fetchCurrentAccount,
  fetchFollowedAuthors,
  searchCatalog,
} from "../lib/api";
import type { AccountDirectoryUser, SearchResults, Work } from "../lib/types";
import { WorkCard } from "./WorkCard";

type SearchMode = "all" | "writers" | "authors" | "works";

type SearchResultsViewProps = {
  mode?: string;
  query: string;
};

const defaultSearchTerms = [
  "romance",
  "epic poetry",
  "gothic",
  "satire",
  "philosophy",
  "adventure",
  "love",
  "time",
  "Jane Austen",
  "William Shakespeare",
];

const searchModes: Array<{ value: SearchMode; label: string }> = [
  { value: "all", label: "All" },
  { value: "writers", label: "Linguaphilia Writers" },
  { value: "authors", label: "Historical Authors" },
  { value: "works", label: "Works" },
];

export function SearchResultsView({ mode = "all", query }: SearchResultsViewProps) {
  const trimmedQuery = query.trim();
  const activeMode = normalizeSearchMode(mode);
  const [resultsState, setResultsState] = useState<{
    query: string;
    results: SearchResults;
  } | null>(null);
  const [readerDirectory, setReaderDirectory] = useState<AccountDirectoryUser[]>([]);
  const [recommended, setRecommended] = useState<Work[]>([]);
  const [suggestedAuthors, setSuggestedAuthors] = useState<SearchResults["authors"]>([]);
  const [recommendedTerms, setRecommendedTerms] = useState(defaultSearchTerms);
  const [errorState, setErrorState] = useState<{ query: string; message: string } | null>(null);
  const results = resultsState?.query === trimmedQuery ? resultsState.results : null;
  const error = errorState?.query === trimmedQuery ? errorState.message : null;

  useEffect(() => {
    let mounted = true;
    void fetchAccountDirectory()
      .then((directory) => {
        if (mounted) {
          setReaderDirectory(directory);
        }
      })
      .catch(() => {
        if (mounted) {
          setReaderDirectory([]);
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    let mounted = true;
    if (!trimmedQuery) {
      return;
    }
    void searchCatalog(trimmedQuery)
      .then((items) => {
        if (mounted) {
          setResultsState({ query: trimmedQuery, results: items });
          setErrorState(null);
        }
      })
      .catch((caught) => {
        if (mounted) {
          setErrorState({
            query: trimmedQuery,
            message: caught instanceof Error ? caught.message : "Unable to search.",
          });
        }
      });
    return () => {
      mounted = false;
    };
  }, [trimmedQuery]);

  useEffect(() => {
    let mounted = true;
    if (trimmedQuery) {
      return;
    }
    void Promise.all([fetchCurrentAccount(), fetchFollowedAuthors()])
      .then(([account, followedAuthors]) => {
        if (!mounted) {
          return;
        }
        setRecommendedTerms(
          buildRecommendedSearchTerms({
            preferenceTerms: [
              ...(account?.preferences.genres ?? []),
              ...(account?.preferences.forms ?? []),
              ...(account?.preferences.themes ?? []),
              ...(account?.preferences.moods ?? []),
              ...(account?.preferences.authors ?? []),
              ...(account?.preferences.books ?? []),
            ],
            followedAuthorTerms: followedAuthors.map((author) => author.name),
          }),
        );
      })
      .catch(() => {
        if (mounted) {
          setRecommendedTerms(defaultSearchTerms);
        }
      });
    return () => {
      mounted = false;
    };
  }, [trimmedQuery]);

  useEffect(() => {
    let mounted = true;
    if (trimmedQuery) {
      return;
    }
    const previewTerm = recommendedTerms[0] ?? "poetry";
    void searchCatalog(previewTerm)
      .then((catalog) => {
        if (!mounted) {
          return;
        }
        setRecommended(catalog.works.slice(0, 12));
        setSuggestedAuthors(catalog.authors.slice(0, 6));
        setErrorState(null);
      })
      .catch((caught) => {
        if (mounted) {
          setErrorState({
            query: "",
            message: caught instanceof Error ? caught.message : "Unable to load recommendations.",
          });
        }
      });
    return () => {
      mounted = false;
    };
  }, [recommendedTerms, trimmedQuery]);

  const matchedReaders = useMemo(
    () => filterLinguaphiliaWriters(readerDirectory, trimmedQuery),
    [readerDirectory, trimmedQuery],
  );
  const displayReaders = trimmedQuery ? matchedReaders : matchedReaders.slice(0, 6);

  if (!trimmedQuery) {
    return (
      <div className="search-results">
        <SearchModeTabs activeMode={activeMode} query={trimmedQuery} />
        {error ? <p className="form-message error-message">{error}</p> : null}
        <section className="section">
          <div className="row-header">
            <div>
              <h2>Suggested Searches</h2>
            </div>
          </div>
          <div className="recommended-term-grid">
            {recommendedTerms.map((term) => (
              <Link
                className="recommended-search-term"
                href={searchHref(term, activeMode)}
                key={term}
              >
                {term}
              </Link>
            ))}
          </div>
        </section>

        {shouldShowSection(activeMode, "writers") ? (
          <LinguaphiliaWritersSection readers={displayReaders} signedIn={readerDirectory.length > 0} />
        ) : null}

        {shouldShowSection(activeMode, "works") ? (
          <WorksSection emptyText="Loading recommendations." title="Recommended" works={recommended} />
        ) : null}

        {shouldShowSection(activeMode, "authors") ? (
          <HistoricalAuthorsSection authors={suggestedAuthors} emptyText="Search by name to find historical authors." title="Explore Historical Authors" />
        ) : null}
      </div>
    );
  }

  if (error) {
    return (
      <div className="search-results">
        <SearchModeTabs activeMode={activeMode} query={trimmedQuery} />
        <p className="form-message error-message">{error}</p>
      </div>
    );
  }

  if (!results) {
    return (
      <div className="search-results">
        <SearchModeTabs activeMode={activeMode} query={trimmedQuery} />
        <section className="form-surface">
          <p className="muted">Searching.</p>
        </section>
      </div>
    );
  }

  return (
    <div className="search-results">
      <SearchModeTabs activeMode={activeMode} query={trimmedQuery} />
      {shouldShowSection(activeMode, "writers") ? (
        <LinguaphiliaWritersSection readers={displayReaders} signedIn={readerDirectory.length > 0} />
      ) : null}
      {shouldShowSection(activeMode, "authors") ? (
        <HistoricalAuthorsSection authors={results.authors} emptyText="No historical author matches yet." title="Historical Authors" />
      ) : null}
      {shouldShowSection(activeMode, "works") ? (
        <WorksSection emptyText="No work matches yet." title="Works and passages" works={results.works} />
      ) : null}
    </div>
  );
}

function SearchModeTabs({ activeMode, query }: { activeMode: SearchMode; query: string }) {
  return (
    <nav aria-label="Search categories" className="search-mode-tabs segmented-control">
      {searchModes.map((option) => (
        <Link
          aria-current={activeMode === option.value ? "page" : undefined}
          className={activeMode === option.value ? "segment active-segment" : "segment"}
          href={searchModeHref(query, option.value)}
          key={option.value}
        >
          {option.label}
        </Link>
      ))}
    </nav>
  );
}

function LinguaphiliaWritersSection({
  readers,
  signedIn,
}: {
  readers: AccountDirectoryUser[];
  signedIn: boolean;
}) {
  return (
    <section className="section">
      <div className="row-header">
        <div>
          <h2>Linguaphilia Writers</h2>
          <p className="muted">{readers.length} matches</p>
        </div>
      </div>
      {readers.length ? (
        <div className="reader-card-grid search-reader-grid">
          {readers.map((reader) => (
            <Link className="reader-card search-reader-card" href={`/readers/${reader.id}`} key={reader.id}>
              <ReaderAvatar reader={reader} />
              <span className="search-reader-copy">
                <strong>{reader.display_name}</strong>
                <span className="muted">
                  {formatProfileRole(reader.profile_role)} · {reader.account_visibility} · {reader.post_count} posts
                </span>
                <span>{reader.bio || "Reading and writing on Linguaphilia."}</span>
              </span>
            </Link>
          ))}
        </div>
      ) : (
        <p className="muted">
          {signedIn
            ? "No Linguaphilia writer profiles match yet."
            : "Sign in from Profile to search Linguaphilia reader and writer profiles."}
        </p>
      )}
    </section>
  );
}

function HistoricalAuthorsSection({
  authors,
  emptyText,
  title,
}: {
  authors: SearchResults["authors"];
  emptyText: string;
  title: string;
}) {
  return (
    <section className="section">
      <div className="row-header">
        <div>
          <h2>{title}</h2>
          <p className="muted">{authors.length} matches</p>
        </div>
      </div>
      {authors.length ? (
        <div className="author-result-grid">
          {authors.map((author) => (
            <Link className="author-result-card" href={`/authors/${author.id}`} key={author.id}>
              <h3>{author.name}</h3>
              <p className="muted">
                {author.work_count} works · {author.excerpt_count} excerpts
              </p>
              <div className="tag-list">
                {author.forms.map((form) => (
                  <span className="tag" key={form}>
                    {form}
                  </span>
                ))}
              </div>
            </Link>
          ))}
        </div>
      ) : (
        <p className="muted">{emptyText}</p>
      )}
    </section>
  );
}

function WorksSection({
  emptyText,
  title,
  works,
}: {
  emptyText: string;
  title: string;
  works: Work[];
}) {
  return (
    <section className="section">
      <div className="row-header">
        <div>
          <h2>{title}</h2>
          <p className="muted">{works.length} matches</p>
        </div>
      </div>
      {works.length ? (
        <div className="work-row">
          {works.map((work) => (
            <WorkCard excerptLength="short" key={work.id} work={work} />
          ))}
        </div>
      ) : (
        <p className="muted">{emptyText}</p>
      )}
    </section>
  );
}

function ReaderAvatar({ reader }: { reader: AccountDirectoryUser }) {
  if (reader.avatar_data_url) {
    return (
      <span
        aria-label={`${reader.display_name} profile image`}
        className="reader-card-avatar search-reader-avatar"
        role="img"
        style={{ backgroundImage: `url(${reader.avatar_data_url})` }}
      />
    );
  }
  return (
    <span className="reader-card-avatar reader-card-avatar-placeholder search-reader-avatar" aria-hidden="true">
      {reader.display_name.slice(0, 1).toUpperCase()}
    </span>
  );
}

function filterLinguaphiliaWriters(
  readers: AccountDirectoryUser[],
  query: string,
): AccountDirectoryUser[] {
  const normalizedQuery = query.trim().toLowerCase();
  const writerCandidates = readers.filter(
    (reader) => reader.profile_role !== "reader" || reader.post_count > 0,
  );
  const candidates = writerCandidates.length ? writerCandidates : readers;
  if (!normalizedQuery) {
    return candidates;
  }
  return candidates.filter((reader) =>
    [reader.display_name, reader.bio ?? "", formatProfileRole(reader.profile_role)]
      .join(" ")
      .toLowerCase()
      .includes(normalizedQuery),
  );
}

function buildRecommendedSearchTerms({
  preferenceTerms,
  followedAuthorTerms,
}: {
  preferenceTerms: string[];
  followedAuthorTerms: string[];
}): string[] {
  const combined = [...preferenceTerms, ...followedAuthorTerms, ...defaultSearchTerms];
  const seen = new Set<string>();
  const terms: string[] = [];
  for (const term of combined) {
    const normalized = term.trim().split(/\s+/).join(" ");
    const key = normalized.toLowerCase();
    if (!normalized || seen.has(key)) {
      continue;
    }
    terms.push(normalized);
    seen.add(key);
    if (terms.length >= 12) {
      break;
    }
  }
  return terms;
}

function formatProfileRole(role: AccountDirectoryUser["profile_role"]): string {
  if (role === "writer_reader") {
    return "Writer/reader";
  }
  return role.slice(0, 1).toUpperCase() + role.slice(1);
}

function normalizeSearchMode(mode: string): SearchMode {
  if (mode === "writers" || mode === "authors" || mode === "works") {
    return mode;
  }
  return "all";
}

function shouldShowSection(activeMode: SearchMode, section: Exclude<SearchMode, "all">): boolean {
  return activeMode === "all" || activeMode === section;
}

function searchHref(term: string, activeMode: SearchMode): string {
  return searchModeHref(term, activeMode);
}

function searchModeHref(query: string, mode: SearchMode): string {
  const params = new URLSearchParams();
  if (query) {
    params.set("query", query);
  }
  if (mode !== "all") {
    params.set("mode", mode);
  }
  const queryString = params.toString();
  return queryString ? `/search?${queryString}` : "/search";
}
