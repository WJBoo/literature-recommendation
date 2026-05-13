"use client";

import { BookOpen, Clock3 } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState, useSyncExternalStore } from "react";
import { fetchAccountReadingProgress } from "../lib/api";
import type { ContinueReadingItem } from "../lib/types";
import {
  continueReadingStorageEvent,
  writeContinueReadingItem,
} from "./ReadingProgressTracker";

export function ContinueReadingPanel() {
  const localSnapshot = useSyncExternalStore(
    subscribeToContinueReadingStore,
    readContinueReadingSnapshot,
    emptyContinueReadingSnapshot,
  );
  const localItem = useMemo(() => parseContinueReadingSnapshot(localSnapshot), [localSnapshot]);
  const [accountItem, setAccountItem] = useState<ContinueReadingItem | null>(null);
  const item = accountItem ?? localItem;

  useEffect(() => {
    let mounted = true;
    void fetchAccountReadingProgress()
      .then((nextItem) => {
        if (!mounted || !nextItem) {
          return;
        }
        setAccountItem(nextItem);
        writeContinueReadingItem(nextItem);
      })
      .catch(() => undefined);
    return () => {
      mounted = false;
    };
  }, []);

  return (
    <section className="continue-reading-page" aria-labelledby="continue-reading-heading">
      <div className="page-heading">
        <p className="eyebrow">Continue Reading</p>
        <h1 id="continue-reading-heading">Return to your latest piece</h1>
      </div>

      {item ? (
        <article className="continue-reading-card">
          <div className="continue-reading-icon">
            <BookOpen size={24} aria-hidden="true" />
          </div>
          <div className="continue-reading-copy">
            <p className="eyebrow">{item.form}</p>
            <h2>{item.title}</h2>
            <p className="muted">
              {partLabel(item)} {partLabel(item) ? "· " : ""}{item.author}
            </p>
            <p className="continue-reading-time">
              <Clock3 size={15} aria-hidden="true" />
              Last opened {formatSavedAt(item.saved_at)}
            </p>
          </div>
          <Link className="primary-button" href={`/work/${item.id}`}>
            Continue
          </Link>
        </article>
      ) : (
        <div className="empty-state-panel">
          <h2>No recent reading yet</h2>
          <p className="muted">Open any work and Linguaphilia will keep your place here.</p>
          <Link className="primary-button" href="/">
            Discover something to read
          </Link>
        </div>
      )}
    </section>
  );
}

function subscribeToContinueReadingStore(callback: () => void): () => void {
  if (typeof window === "undefined") {
    return () => undefined;
  }
  window.addEventListener("storage", callback);
  window.addEventListener(continueReadingStorageEvent, callback);
  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener(continueReadingStorageEvent, callback);
  };
}

function readContinueReadingSnapshot(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem("linguaphilia_continue_reading");
}

function emptyContinueReadingSnapshot(): string | null {
  return null;
}

function parseContinueReadingSnapshot(value: string | null): ContinueReadingItem | null {
  if (!value) {
    return null;
  }
  try {
    const parsed = JSON.parse(value) as ContinueReadingItem;
    return parsed?.id ? parsed : null;
  } catch {
    return null;
  }
}

function partLabel(item: ContinueReadingItem): string | null {
  return item.section_title ?? item.excerpt_label ?? item.work_title ?? null;
}

function formatSavedAt(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "recently";
  }
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}
