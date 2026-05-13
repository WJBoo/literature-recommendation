"use client";

import { Lock, MessageCircle, Search, UserCheck, UserPlus } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  fetchAccountDirectory,
  followReader,
  searchCatalog,
  unfollowReader,
} from "../lib/api";
import type { AccountDirectoryUser, AuthorSearchResult } from "../lib/types";

export function WriterDiscovery() {
  const [query, setQuery] = useState("");
  const [readers, setReaders] = useState<AccountDirectoryUser[]>([]);
  const [authors, setAuthors] = useState<AuthorSearchResult[]>([]);
  const [status, setStatus] = useState<string | null>(null);
  const [updatingFollowId, setUpdatingFollowId] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    void fetchAccountDirectory()
      .then((directory) => {
        if (mounted) {
          setReaders(directory);
        }
      })
      .catch((caught) => {
        if (mounted) {
          setStatus(caught instanceof Error ? caught.message : "Unable to load writers.");
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    let mounted = true;
    const trimmed = query.trim();
    if (trimmed.length < 2) {
      return;
    }
    void searchCatalog(trimmed)
      .then((results) => {
        if (mounted) {
          setAuthors(results.authors);
        }
      })
      .catch(() => {
        if (mounted) {
          setAuthors([]);
        }
      });
    return () => {
      mounted = false;
    };
  }, [query]);

  const visibleAuthors = query.trim().length >= 2 ? authors : [];
  const filteredReaders = useMemo(() => {
    const trimmed = query.trim().toLowerCase();
    const writerReaders = readers.filter((reader) => reader.post_count > 0);
    const candidates = writerReaders.length ? writerReaders : readers;
    if (!trimmed) {
      return candidates;
    }
    return candidates.filter((reader) =>
      [reader.display_name, reader.bio ?? "", formatProfileRole(reader.profile_role)]
        .join(" ")
        .toLowerCase()
        .includes(trimmed),
    );
  }, [query, readers]);

  async function handleFollowToggle(reader: AccountDirectoryUser) {
    setUpdatingFollowId(reader.id);
    setStatus(null);
    try {
      const updatedDirectory = reader.followed_by_me
        ? await unfollowReader(reader.id)
        : await followReader(reader.id);
      setReaders(updatedDirectory);
    } catch (caught) {
      setStatus(caught instanceof Error ? caught.message : "Unable to update follow.");
    } finally {
      setUpdatingFollowId(null);
    }
  }

  return (
    <div className="writer-discovery">
      <section className="form-surface writer-search-panel">
        <label className="search-control writer-search-control">
          <Search size={18} aria-hidden="true" />
          <input
            className="search"
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search writers, readers, authors, or bios"
            value={query}
          />
        </label>
        {status ? <p className="form-message error-message">{status}</p> : null}
      </section>

      <section className="section">
        <div className="row-header">
          <div>
            <h2>Writers on Linguaphilia</h2>
          </div>
        </div>
        {filteredReaders.length ? (
          <div className="reader-card-grid">
            {filteredReaders.map((reader) => (
              <article className="reader-card" key={reader.id}>
                <Link className="reader-card-profile" href={`/readers/${reader.id}`}>
                  <WriterAvatar reader={reader} />
                  <span>
                    <strong>{reader.display_name}</strong>
                    <span className="muted">
                      {formatProfileRole(reader.profile_role)} ·{" "}
                      {reader.account_visibility === "private" ? "Private" : "Public"} ·{" "}
                      {reader.post_count} posts
                    </span>
                  </span>
                </Link>
                <p className="reader-card-bio">{reader.bio || "Reading and writing on Linguaphilia."}</p>
                <div className="reader-card-actions">
                  <button
                    className={reader.followed_by_me ? "secondary-button active-button" : "secondary-button"}
                    disabled={updatingFollowId === reader.id}
                    onClick={() => void handleFollowToggle(reader)}
                    type="button"
                  >
                    {reader.followed_by_me ? (
                      <UserCheck size={16} aria-hidden="true" />
                    ) : (
                      <UserPlus size={16} aria-hidden="true" />
                    )}
                    {reader.followed_by_me ? "Following" : "Follow"}
                  </button>
                  <Link
                    className={reader.can_message ? "primary-button" : "primary-button disabled-button"}
                    href={reader.can_message ? `/messages?reader=${reader.id}` : `/readers/${reader.id}`}
                    title={reader.can_message ? "Message" : "Follow first to unlock one message."}
                  >
                    {reader.can_message ? (
                      <MessageCircle size={16} aria-hidden="true" />
                    ) : (
                      <Lock size={16} aria-hidden="true" />
                    )}
                    Message
                  </Link>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className="muted">No writer profiles match yet.</p>
        )}
      </section>

      <section className="section">
        <div className="row-header">
          <div>
            <h2>Gutenberg Authors</h2>
          </div>
        </div>
        {visibleAuthors.length ? (
          <div className="author-result-grid">
            {visibleAuthors.map((author) => (
              <Link className="author-result-card" href={`/authors/${author.id}`} key={author.id}>
                <h3>{author.name}</h3>
                <p className="muted">
                  Author · {author.work_count} works · {author.excerpt_count} excerpts
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
          <p className="muted">
            Search by name to find authors from the local Gutenberg corpus.
          </p>
        )}
      </section>
    </div>
  );
}

function WriterAvatar({ reader }: { reader: AccountDirectoryUser }) {
  if (reader.avatar_data_url) {
    return (
      <Image
        alt={`${reader.display_name} profile`}
        className="reader-card-avatar"
        height={52}
        src={reader.avatar_data_url}
        unoptimized
        width={52}
      />
    );
  }
  return (
    <span className="reader-card-avatar reader-card-avatar-placeholder" aria-hidden="true">
      {reader.display_name.slice(0, 1).toUpperCase()}
    </span>
  );
}

function formatProfileRole(role: AccountDirectoryUser["profile_role"]): string {
  if (role === "writer") {
    return "Writer";
  }
  if (role === "writer_reader") {
    return "Writer/reader";
  }
  return "Reader";
}
