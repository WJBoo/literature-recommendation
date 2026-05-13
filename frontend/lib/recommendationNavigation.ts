import {
  fetchCurrentAccount,
  fetchRecommendations,
  getStoredPreferenceProfile,
} from "./api";
import type { ReaderNavigationItem, Work } from "./types";

export type RecommendationNavigationContext = {
  currentExcerptId: string;
  currentWorkId: string;
  currentWorkTitle?: string | null;
  currentAuthor?: string | null;
};

const recentSkipStorageKey = "linguaphilia_recent_skip_work_keys";
const recentSkipLimit = 18;
const skipCandidateLimit = 36;

export async function fetchRecommendedAlternative(
  context: RecommendationNavigationContext,
): Promise<ReaderNavigationItem | null> {
  rememberSkippedWork(context);
  const account = await fetchCurrentAccount().catch(() => null);
  const preferences = account?.preferences ?? getStoredPreferenceProfile() ?? undefined;
  const recommendations = await fetchRecommendations(preferences, { limit: skipCandidateLimit });
  const candidate = pickRecommendedAlternative(recommendations, context);
  return candidate ? toReaderNavigationItem(candidate) : null;
}

export function pickRecommendedAlternative(
  recommendations: Work[],
  context: RecommendationNavigationContext,
): Work | null {
  const recentSkippedWorkKeys = readRecentSkippedWorkKeys();
  const eligible = recommendations.filter((work) => isDifferentExcerpt(work, context));
  const freshEligible = eligible.filter((work) => !recentSkippedWorkKeys.has(workKeyForWork(work)));

  return (
    bestDifferentBook(freshEligible, context, true) ??
    bestDifferentBook(freshEligible, context, false) ??
    bestDifferentBook(eligible, context, true) ??
    bestDifferentBook(eligible, context, false) ??
    eligible[0] ??
    null
  );
}

function bestDifferentBook(
  recommendations: Work[],
  context: RecommendationNavigationContext,
  requireDifferentAuthor: boolean,
): Work | null {
  return (
    recommendations.find(
      (work) =>
        isDifferentWork(work, context) &&
        (!requireDifferentAuthor || isDifferentAuthor(work, context)),
    ) ?? null
  );
}

function toReaderNavigationItem(work: Work): ReaderNavigationItem {
  return {
    id: work.id,
    title: work.title,
    author: work.author,
    form: work.form,
    work_title: work.work_title,
  };
}

function isDifferentExcerpt(work: Work, context: RecommendationNavigationContext): boolean {
  return work.id !== context.currentExcerptId;
}

function isDifferentWork(work: Work, context: RecommendationNavigationContext): boolean {
  const currentTitle = normalize(context.currentWorkTitle);
  const candidateTitle = normalize(work.work_title ?? work.title);
  if (currentTitle && candidateTitle && currentTitle !== candidateTitle) {
    return true;
  }
  if (currentTitle && candidateTitle && currentTitle === candidateTitle) {
    return false;
  }
  return baseWorkId(work.id) !== baseWorkId(context.currentWorkId);
}

function isDifferentAuthor(work: Work, context: RecommendationNavigationContext): boolean {
  const currentAuthor = normalize(context.currentAuthor);
  const candidateAuthor = normalize(work.author);
  return !currentAuthor || !candidateAuthor || currentAuthor !== candidateAuthor;
}

function rememberSkippedWork(context: RecommendationNavigationContext): void {
  if (typeof window === "undefined") {
    return;
  }

  const key = workKeyFromParts(
    context.currentAuthor,
    context.currentWorkTitle,
    context.currentWorkId,
  );
  if (!key) {
    return;
  }

  const existing = readRecentSkippedWorkKeysList().filter((storedKey) => storedKey !== key);
  window.sessionStorage.setItem(
    recentSkipStorageKey,
    JSON.stringify([key, ...existing].slice(0, recentSkipLimit)),
  );
}

function readRecentSkippedWorkKeys(): Set<string> {
  return new Set(readRecentSkippedWorkKeysList());
}

function readRecentSkippedWorkKeysList(): string[] {
  if (typeof window === "undefined") {
    return [];
  }

  const stored = window.sessionStorage.getItem(recentSkipStorageKey);
  if (!stored) {
    return [];
  }

  try {
    const parsed = JSON.parse(stored);
    return Array.isArray(parsed)
      ? parsed.filter((value): value is string => typeof value === "string")
      : [];
  } catch {
    return [];
  }
}

function workKeyForWork(work: Work): string {
  return workKeyFromParts(work.author, work.work_title ?? work.title, baseWorkId(work.id));
}

function workKeyFromParts(
  author?: string | null,
  title?: string | null,
  workId?: string | null,
): string {
  const titleKey = normalize(title);
  const idKey = normalize(baseWorkId(workId ?? ""));
  const primaryWorkKey = titleKey || idKey;
  if (!primaryWorkKey) {
    return "";
  }
  return `${normalize(author)}::${primaryWorkKey}`;
}

function baseWorkId(id: string): string {
  return id.replace(/-excerpt-\d+$/i, "").replace(/-post-\d+$/i, "");
}

function normalize(value?: string | null): string {
  return value?.trim().toLowerCase() ?? "";
}
