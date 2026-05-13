"use client";

import { useEffect } from "react";
import { updateAccountReadingProgress } from "../lib/api";
import type { ContinueReadingItem } from "../lib/types";

export const continueReadingStorageKey = "linguaphilia_continue_reading";
export const continueReadingStorageEvent = "linguaphilia:continue-reading-storage";

export function ReadingProgressTracker({ item }: { item: Omit<ContinueReadingItem, "saved_at"> }) {
  useEffect(() => {
    const record: ContinueReadingItem = {
      ...item,
      saved_at: new Date().toISOString(),
    };
    writeContinueReadingItem(record);
    void updateAccountReadingProgress(item)
      .then((accountRecord) => {
        if (accountRecord) {
          writeContinueReadingItem(accountRecord);
        }
      })
      .catch(() => undefined);
  }, [item]);

  return null;
}

export function readContinueReadingItem(): ContinueReadingItem | null {
  if (typeof window === "undefined") {
    return null;
  }
  const raw = window.localStorage.getItem(continueReadingStorageKey);
  if (!raw) {
    return null;
  }
  try {
    const parsed = JSON.parse(raw) as ContinueReadingItem;
    return parsed?.id ? parsed : null;
  } catch {
    return null;
  }
}

export function writeContinueReadingItem(item: ContinueReadingItem): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(continueReadingStorageKey, JSON.stringify(item));
  window.dispatchEvent(new Event(continueReadingStorageEvent));
}
