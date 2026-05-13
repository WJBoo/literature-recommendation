"use client";

import { useEffect, useMemo, useState } from "react";
import {
  fetchCurrentAccount,
  fetchRecommendations,
  getStoredPreferenceProfile,
} from "../lib/api";
import type {
  PreferenceProfile,
  RecommendationSection,
  Work,
} from "../lib/types";
import { RecommendationRow } from "./RecommendationRow";
import type { ExcerptLength } from "./WorkCard";

type RecommendationSurfaceProps = {
  fallbackSections: RecommendationSection[];
};

const excerptLengthOptions: { value: ExcerptLength; label: string }[] = [
  { value: "short", label: "Short" },
  { value: "medium", label: "Medium" },
  { value: "long", label: "Long" },
];

const excerptLengthStorageKey = "linguaphilia_excerpt_length";
const excerptLengthWordLimits: Record<ExcerptLength, number | null> = {
  short: 400,
  medium: 900,
  long: null,
};
const genericTags = new Set(["all", "drama", "fiction", "literature", "novel", "prose", "text"]);
const stopwords = new Set([
  "and",
  "because",
  "for",
  "from",
  "into",
  "more",
  "the",
  "this",
  "that",
  "with",
  "your",
]);

export function RecommendationSurface({ fallbackSections }: RecommendationSurfaceProps) {
  const [works, setWorks] = useState<Work[] | null>(null);
  const [preferences, setPreferences] = useState<PreferenceProfile | null>(null);
  const [excerptLength, setExcerptLength] = useState<ExcerptLength>("medium");

  useEffect(() => {
    const storedValue = window.localStorage.getItem(excerptLengthStorageKey);
    if (isExcerptLength(storedValue)) {
      const timeout = window.setTimeout(() => setExcerptLength(storedValue), 0);
      return () => window.clearTimeout(timeout);
    }
    return undefined;
  }, []);

  useEffect(() => {
    let mounted = true;
    const storedPreferences = getStoredPreferenceProfile();
    void fetchCurrentAccount()
      .catch(() => null)
      .then(async (account) => {
        const activePreferences = account?.preferences ?? storedPreferences ?? undefined;
        const items = await fetchRecommendations(activePreferences, {
          maxWordCount: excerptLengthWordLimits[excerptLength],
        });
        return { activePreferences, items };
      })
      .then(({ activePreferences, items }) => {
        if (mounted) {
          setWorks(items);
          setPreferences(activePreferences ?? null);
        }
      })
      .catch(() => {
        if (mounted) {
          setWorks(null);
        }
      });

    return () => {
      mounted = false;
    };
  }, [excerptLength]);

  const sections = useMemo(() => {
    if (!works?.length) {
      return fallbackSections;
    }

    return buildDiscoverySections(works, preferences, fallbackSections);
  }, [fallbackSections, preferences, works]);

  function handleExcerptLengthChange(value: ExcerptLength): void {
    setExcerptLength(value);
    window.localStorage.setItem(excerptLengthStorageKey, value);
  }

  return (
    <>
      <div className="recommendation-controls" aria-label="Recommendation display settings">
        <span className="control-label">Excerpt length</span>
        <div className="segmented-control">
          {excerptLengthOptions.map((option) => (
            <button
              className={`segment ${excerptLength === option.value ? "active-segment" : ""}`}
              key={option.value}
              onClick={() => handleExcerptLengthChange(option.value)}
              type="button"
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>
      {sections.map((section) => (
        <RecommendationRow key={section.title} section={section} excerptLength={excerptLength} />
      ))}
    </>
  );
}

function buildDiscoverySections(
  works: Work[],
  preferences: PreferenceProfile | null,
  fallbackSections: RecommendationSection[],
): RecommendationSection[] {
  const sections: RecommendationSection[] = [
    {
      title: "For You",
      subtitle: "",
      works,
    },
  ];

  for (const label of genreRowLabels(works, preferences)) {
    sections.push({
      title: titleCase(label),
      subtitle: "",
      works: prioritizeByTerms(works, [label]),
    });
  }

  for (const fallback of fallbackSections) {
    if (!sections.some((section) => sameValue(section.title, fallback.title))) {
      sections.push(fallback);
    }
  }

  return sections
    .map((section) => ({ ...section, works: limitWorks(dedupeWorks(section.works)) }))
    .filter((section) => section.works.length > 0)
    .filter(uniqueSectionTitle)
    .slice(0, 8);
}

function genreRowLabels(works: Work[], preferences: PreferenceProfile | null): string[] {
  const labels = [
    ...(preferences?.genres ?? []),
    ...topTopicalTags(works),
    ...(preferences?.forms ?? []),
    ...topForms(works),
  ];
  const seen = new Set<string>();
  return labels
    .map((label) => label.trim())
    .filter((label) => {
      const normalized = normalize(label);
      if (!normalized || genericTags.has(normalized) || seen.has(normalized)) {
        return false;
      }
      seen.add(normalized);
      return true;
    })
    .slice(0, 6);
}

function prioritizeByTerms(works: Work[], values: string[]): Work[] {
  const terms = values.flatMap((value) => tokenize(value));
  return prioritizeWorks(works, (work) => {
    const exactTagMatch = values.some((value) => hasExactTagOrForm(work, value)) ? 4 : 0;
    return exactTagMatch + scoreWorkByTerms(work, terms);
  });
}

function prioritizeWorks(works: Work[], scorer: (work: Work) => number): Work[] {
  return works
    .map((work, index) => ({ index, score: scorer(work), work }))
    .sort((left, right) => right.score - left.score || left.index - right.index)
    .map((entry) => entry.work);
}

function scoreWorkByTerms(work: Work, terms: string[]): number {
  const text = searchableWorkText(work);
  return terms.reduce((score, term) => score + (text.includes(term) ? 1 : 0), 0);
}

function searchableWorkText(work: Work): string {
  return `${work.title} ${work.author} ${work.form} ${work.reason} ${work.excerpt} ${work.tags.join(" ")}`.toLowerCase();
}

function hasExactTagOrForm(work: Work, value: string): boolean {
  const normalizedValue = normalize(value);
  return normalize(work.form) === normalizedValue || work.tags.some((tag) => normalize(tag) === normalizedValue);
}

function topTopicalTags(works: Work[]): string[] {
  const counts = new Map<string, number>();

  for (const work of works) {
    for (const tag of work.tags) {
      const normalizedTag = normalize(tag);
      if (!normalizedTag || genericTags.has(normalizedTag)) {
        continue;
      }
      counts.set(tag, (counts.get(tag) ?? 0) + 1);
    }
  }

  return Array.from(counts.entries())
    .sort((left, right) => right[1] - left[1])
    .map(([tag]) => tag);
}

function topForms(works: Work[]): string[] {
  const counts = new Map<string, number>();
  for (const work of works) {
    counts.set(work.form, (counts.get(work.form) ?? 0) + 1);
  }
  return Array.from(counts.entries())
    .sort((left, right) => right[1] - left[1])
    .map(([form]) => form);
}

function dedupeWorks(works: Work[]): Work[] {
  const seen = new Set<string>();
  return works.filter((work) => {
    if (seen.has(work.id)) {
      return false;
    }
    seen.add(work.id);
    return true;
  });
}

function limitWorks(works: Work[]): Work[] {
  return works.slice(0, 12);
}

function uniqueSectionTitle(section: RecommendationSection, index: number, sections: RecommendationSection[]): boolean {
  return sections.findIndex((candidate) => sameValue(candidate.title, section.title)) === index;
}

function normalize(value: string | null | undefined): string {
  return value?.trim().toLowerCase() ?? "";
}

function sameValue(left: string | null | undefined, right: string | null | undefined): boolean {
  return normalize(left) === normalize(right);
}

function titleCase(value: string): string {
  return value
    .split(/[\s_-]+/)
    .filter(Boolean)
    .map((word) => `${word[0].toUpperCase()}${word.slice(1).toLowerCase()}`)
    .join(" ");
}

function tokenize(value: string): string[] {
  return value
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter((term) => term.length > 2 && !stopwords.has(term));
}

function isExcerptLength(value: string | null): value is ExcerptLength {
  return value === "short" || value === "medium" || value === "long";
}
