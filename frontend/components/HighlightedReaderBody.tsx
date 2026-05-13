"use client";

import { useEffect, useMemo, useState } from "react";
import { fetchAccountExcerptSocial, fetchSavedFolders } from "../lib/api";
import type { SavedHighlightColor } from "../lib/types";

type HighlightedReaderBodyProps = {
  excerptId: string;
  initialAnnotationId?: string | null;
  text: string;
};

type SavedHighlight = {
  id: string;
  text: string;
  start: number | null;
  end: number | null;
  color: SavedHighlightColor;
  comment: string | null;
  source: "own" | "other";
};

type HighlightRange = {
  id: string;
  start: number;
  end: number;
  color: SavedHighlightColor;
  comments: string[];
};

type ReaderSegment = {
  key: string;
  text: string;
  color?: SavedHighlightColor;
  comments?: string[];
};

type ReaderTextSize = "small" | "medium" | "large" | "x-large";

const fallbackHighlightColor: SavedHighlightColor = "yellow";
const readerTextSizeStorageKey = "linguaphilia_reader_text_size";
const readerTextSizeOptions: Array<{ value: ReaderTextSize; label: string }> = [
  { value: "small", label: "Small" },
  { value: "medium", label: "Medium" },
  { value: "large", label: "Large" },
  { value: "x-large", label: "XL" },
];

export function HighlightedReaderBody({
  excerptId,
  initialAnnotationId = null,
  text,
}: HighlightedReaderBodyProps) {
  const [ownHighlights, setOwnHighlights] = useState<SavedHighlight[]>([]);
  const [otherHighlights, setOtherHighlights] = useState<SavedHighlight[]>([]);
  const [showOtherHighlights, setShowOtherHighlights] = useState(Boolean(initialAnnotationId));
  const [expandedHighlightId, setExpandedHighlightId] = useState<string | null>(null);
  const [textSize, setTextSize] = useState<ReaderTextSize>("medium");

  useEffect(() => {
    const storedSize = window.localStorage.getItem(readerTextSizeStorageKey);
    if (isReaderTextSize(storedSize)) {
      const timeout = window.setTimeout(() => setTextSize(storedSize), 0);
      return () => window.clearTimeout(timeout);
    }
    return undefined;
  }, []);

  useEffect(() => {
    let mounted = true;

    async function loadHighlights() {
      const [folders, social] = await Promise.all([
        fetchSavedFolders(),
        fetchAccountExcerptSocial(excerptId),
      ]);
      if (!mounted) {
        return;
      }
      const nextHighlights = new Map<string, SavedHighlight>();
      for (const folder of folders) {
        for (const item of folder.items) {
          if (item.saved_kind !== "selection" || item.excerpt_id !== excerptId || !item.selected_text) {
            continue;
          }
          nextHighlights.set(item.id, {
            id: item.id,
            text: item.selected_text,
            start: item.selection_start,
            end: item.selection_end,
            color: item.highlight_color ?? fallbackHighlightColor,
            comment: item.note,
            source: "own",
          });
        }
      }
      const socialHighlights =
        social?.annotations
          .filter((annotation) => annotation.excerpt_id === excerptId && annotation.selected_text)
          .filter((annotation) => !nextHighlights.has(annotation.id))
          .map((annotation) => ({
            id: annotation.id,
            text: annotation.selected_text,
            start: annotation.selection_start,
            end: annotation.selection_end,
            color: annotation.highlight_color ?? fallbackHighlightColor,
            comment: `${annotation.user.display_name}: ${
              annotation.note || "annotated this passage."
            }`,
            source: "other" as const,
          })) ?? [];
      setOwnHighlights(Array.from(nextHighlights.values()));
      setOtherHighlights(socialHighlights);
      if (initialAnnotationId) {
        setShowOtherHighlights(true);
        setExpandedHighlightId(initialAnnotationId);
      }
    }

    void loadHighlights().catch(() => {
      if (mounted) {
        setOwnHighlights([]);
        setOtherHighlights([]);
      }
    });

    function handleSavedHighlightsChanged(event: Event) {
      const detail = (event as CustomEvent<{ excerptId?: string }>).detail;
      if (!detail?.excerptId || detail.excerptId === excerptId) {
        void loadHighlights().catch(() => {
          setOwnHighlights([]);
          setOtherHighlights([]);
        });
      }
    }

    window.addEventListener("saved-highlights-changed", handleSavedHighlightsChanged);
    return () => {
      mounted = false;
      window.removeEventListener("saved-highlights-changed", handleSavedHighlightsChanged);
    };
  }, [excerptId, initialAnnotationId]);

  const highlights = useMemo(() => {
    const combined = showOtherHighlights ? [...ownHighlights, ...otherHighlights] : ownHighlights;
    if (!initialAnnotationId) {
      return combined;
    }
    return [...combined].sort((left, right) => {
      if (left.id === initialAnnotationId) {
        return -1;
      }
      if (right.id === initialAnnotationId) {
        return 1;
      }
      return 0;
    });
  }, [initialAnnotationId, otherHighlights, ownHighlights, showOtherHighlights]);
  const segments = useMemo(() => segmentTextWithHighlights(text, highlights), [highlights, text]);

  function handleTextSizeChange(value: ReaderTextSize): void {
    setTextSize(value);
    window.localStorage.setItem(readerTextSizeStorageKey, value);
  }

  return (
    <>
      <div className="reader-display-controls" aria-label="Reader display settings">
        <span className="control-label">Text size</span>
        <div className="segmented-control reader-text-size-control">
          {readerTextSizeOptions.map((option) => (
            <button
              aria-pressed={textSize === option.value}
              className={textSize === option.value ? "segment active-segment" : "segment"}
              key={option.value}
              onClick={() => handleTextSizeChange(option.value)}
              type="button"
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>
      {otherHighlights.length ? (
        <div className="reader-annotation-banner">
          <span>
            {otherHighlights.length} visible annotation
            {otherHighlights.length === 1 ? "" : "s"} from other readers.
          </span>
          <button
            className="secondary-button"
            onClick={() => setShowOtherHighlights((current) => !current)}
            type="button"
          >
            {showOtherHighlights ? "Hide annotations" : "Show annotations"}
          </button>
        </div>
      ) : null}
      <article className={`reader-body reader-body-${textSize}`}>
        {segments.map((segment) => {
          if (!segment.color) {
            return <span key={segment.key}>{segment.text}</span>;
          }

          const comments = segment.comments ?? [];
          const hasComment = comments.length > 0;
          const isExpanded = expandedHighlightId === segment.key;
          return (
            <span className="reader-highlight-shell" key={segment.key}>
              <button
                aria-expanded={hasComment ? isExpanded : undefined}
                className={`reader-highlight-button highlight-${segment.color}`}
                onClick={() => {
                  if (hasComment) {
                    setExpandedHighlightId(isExpanded ? null : segment.key);
                  }
                }}
                title={hasComment ? "Click to see comment" : "No comment saved"}
                type="button"
              >
                {segment.text}
              </button>
              {hasComment && isExpanded ? (
                <span className="highlight-comment-popover">
                  {comments.map((comment, index) => (
                    <span className="highlight-comment-line" key={`${segment.key}-comment-${index}`}>
                      {comment}
                    </span>
                  ))}
                </span>
              ) : null}
            </span>
          );
        })}
      </article>
    </>
  );
}

function isReaderTextSize(value: string | null): value is ReaderTextSize {
  return value === "small" || value === "medium" || value === "large" || value === "x-large";
}

function segmentTextWithHighlights(text: string, highlights: SavedHighlight[]): ReaderSegment[] {
  const ranges = buildHighlightRanges(text, highlights);
  if (!ranges.length) {
    return [{ key: "plain-0", text }];
  }

  const segments: ReaderSegment[] = [];
  let cursor = 0;
  ranges.forEach((range, index) => {
    if (range.start > cursor) {
      segments.push({
        key: `plain-${index}-${cursor}`,
        text: text.slice(cursor, range.start),
      });
    }
    segments.push({
      key: range.id,
      text: text.slice(range.start, range.end),
      color: range.color,
      comments: range.comments,
    });
    cursor = range.end;
  });

  if (cursor < text.length) {
    segments.push({ key: `plain-end-${cursor}`, text: text.slice(cursor) });
  }
  return segments;
}

function buildHighlightRanges(text: string, highlights: SavedHighlight[]): HighlightRange[] {
  const ranges: HighlightRange[] = [];
  for (const highlight of highlights) {
    const directRange = getValidDirectRange(text, highlight);
    const range = directRange ?? findNormalizedRange(text, highlight);
    if (!range) {
      continue;
    }
    const existingRange = ranges.find(
      (existing) => existing.start === range.start && existing.end === range.end,
    );
    if (existingRange) {
      if (highlight.comment) {
        existingRange.comments.push(highlight.comment);
      }
      continue;
    }
    if (ranges.some((existing) => rangesOverlap(existing, range))) {
      continue;
    }
    ranges.push({
      id: highlight.id,
      color: highlight.color,
      comments: highlight.comment ? [highlight.comment] : [],
      ...range,
    });
  }
  return ranges.sort((left, right) => left.start - right.start);
}

function getValidDirectRange(
  text: string,
  highlight: SavedHighlight,
): { start: number; end: number } | null {
  if (highlight.start === null || highlight.end === null) {
    return null;
  }
  if (highlight.start < 0 || highlight.end > text.length || highlight.start >= highlight.end) {
    return null;
  }
  const selectedText = text.slice(highlight.start, highlight.end);
  if (normalizeForMatch(selectedText) !== normalizeForMatch(highlight.text)) {
    return null;
  }
  return { start: highlight.start, end: highlight.end };
}

function findNormalizedRange(
  text: string,
  highlight: SavedHighlight,
): { start: number; end: number } | null {
  const needle = normalizeForMatch(highlight.text);
  if (!needle) {
    return null;
  }
  const { normalized, originalIndexes } = buildNormalizedTextMap(text);
  const normalizedStart = normalized.indexOf(needle);
  if (normalizedStart < 0) {
    return null;
  }
  const normalizedEnd = normalizedStart + needle.length - 1;
  return {
    start: originalIndexes[normalizedStart],
    end: originalIndexes[normalizedEnd] + 1,
  };
}

function buildNormalizedTextMap(text: string): {
  normalized: string;
  originalIndexes: number[];
} {
  const normalized: string[] = [];
  const originalIndexes: number[] = [];
  let previousWasWhitespace = false;

  for (let index = 0; index < text.length; index += 1) {
    const character = text[index];
    if (/\s/.test(character)) {
      if (normalized.length && !previousWasWhitespace) {
        normalized.push(" ");
        originalIndexes.push(index);
      }
      previousWasWhitespace = true;
      continue;
    }
    normalized.push(character.toLowerCase());
    originalIndexes.push(index);
    previousWasWhitespace = false;
  }

  if (normalized[normalized.length - 1] === " ") {
    normalized.pop();
    originalIndexes.pop();
  }

  return { normalized: normalized.join(""), originalIndexes };
}

function normalizeForMatch(text: string): string {
  return text.replace(/\s+/g, " ").trim().toLowerCase();
}

function rangesOverlap(
  left: { start: number; end: number },
  right: { start: number; end: number },
): boolean {
  return left.start < right.end && right.start < left.end;
}
