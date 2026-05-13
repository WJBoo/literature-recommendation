"use client";

import { ChevronLeft, ChevronRight, ChevronsLeft } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { fetchRecommendedAlternative } from "../lib/recommendationNavigation";
import type { TouchEvent } from "react";
import type { ReaderNavigationItem } from "../lib/types";

type ReaderNavigationProps = {
  currentExcerptId: string;
  currentWorkId: string;
  currentWorkTitle?: string | null;
  currentAuthor?: string | null;
  currentSectionExcerptIndex?: number | null;
  currentSectionExcerptCount?: number | null;
  firstItem?: ReaderNavigationItem | null;
  previousItem?: ReaderNavigationItem | null;
  nextItem?: ReaderNavigationItem | null;
};

const HORIZONTAL_WHEEL_THRESHOLD = 80;
const TOUCH_SWIPE_THRESHOLD = 72;
const NAVIGATION_LOCK_MS = 650;

export function ReaderNavigation({
  currentExcerptId,
  currentWorkId,
  currentWorkTitle,
  currentAuthor,
  currentSectionExcerptIndex,
  currentSectionExcerptCount,
  firstItem,
  previousItem,
  nextItem,
}: ReaderNavigationProps) {
  const router = useRouter();
  const navigationLocked = useRef(false);
  const touchStart = useRef<{ x: number; y: number } | null>(null);
  const continuationKey = [
    currentExcerptId,
    currentWorkId,
    currentWorkTitle ?? "",
    currentAuthor ?? "",
  ].join("|");
  const [continuation, setContinuation] = useState<{
    key: string;
    item: ReaderNavigationItem | null;
  } | null>(null);
  const continuationItem = continuation?.key === continuationKey ? continuation.item : null;
  const isLoadingContinuation = !nextItem && continuation?.key !== continuationKey;
  const effectiveNextItem = nextItem ?? continuationItem;
  const continuesCurrentSection = Boolean(
    nextItem &&
      currentSectionExcerptIndex &&
      currentSectionExcerptCount &&
      currentSectionExcerptIndex < currentSectionExcerptCount,
  );
  const nextLabel = continuesCurrentSection ? "Continue chapter" : nextItem ? "Next" : "Next book";

  const navigateTo = useCallback(
    (target?: ReaderNavigationItem | null) => {
      if (!target || navigationLocked.current) {
        return;
      }
      navigationLocked.current = true;
      router.push(`/work/${target.id}`);
      window.setTimeout(() => {
        navigationLocked.current = false;
      }, NAVIGATION_LOCK_MS);
    },
    [router],
  );

  useEffect(() => {
    let mounted = true;
    if (nextItem) {
      return () => {
        mounted = false;
      };
    }

    void fetchRecommendedAlternative({
      currentExcerptId,
      currentWorkId,
      currentWorkTitle,
      currentAuthor,
    })
      .then((target) => {
        if (mounted) {
          setContinuation({ key: continuationKey, item: target });
        }
      })
      .catch(() => {
        if (mounted) {
          setContinuation({ key: continuationKey, item: null });
        }
      });

    return () => {
      mounted = false;
    };
  }, [continuationKey, currentAuthor, currentExcerptId, currentWorkId, currentWorkTitle, nextItem]);

  useEffect(() => {
    function handleWheel(event: WheelEvent) {
      const horizontalMovement = Math.abs(event.deltaX);
      const verticalMovement = Math.abs(event.deltaY);
      if (
        horizontalMovement < HORIZONTAL_WHEEL_THRESHOLD ||
        horizontalMovement < verticalMovement * 1.2
      ) {
        return;
      }

      const target = event.deltaX > 0 ? effectiveNextItem : previousItem;
      if (!target) {
        return;
      }
      event.preventDefault();
      navigateTo(target);
    }

    window.addEventListener("wheel", handleWheel, { passive: false });
    return () => window.removeEventListener("wheel", handleWheel);
  }, [effectiveNextItem, navigateTo, previousItem]);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.altKey) {
        return;
      }
      if (event.key === "ArrowRight") {
        navigateTo(effectiveNextItem);
      }
      if (event.key === "ArrowLeft") {
        navigateTo(previousItem);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [effectiveNextItem, navigateTo, previousItem]);

  function handleTouchStart(event: TouchEvent<HTMLElement>) {
    const touch = event.touches[0];
    touchStart.current = { x: touch.clientX, y: touch.clientY };
  }

  function handleTouchEnd(event: TouchEvent<HTMLElement>) {
    const start = touchStart.current;
    const touch = event.changedTouches[0];
    touchStart.current = null;
    if (!start || !touch) {
      return;
    }

    const deltaX = touch.clientX - start.x;
    const deltaY = touch.clientY - start.y;
    if (Math.abs(deltaX) < TOUCH_SWIPE_THRESHOLD || Math.abs(deltaX) < Math.abs(deltaY) * 1.2) {
      return;
    }

    navigateTo(deltaX < 0 ? effectiveNextItem : previousItem);
  }

  if (!firstItem && !previousItem && !effectiveNextItem && !isLoadingContinuation) {
    return null;
  }

  return (
    <nav
      aria-label="Reader navigation"
      className="reader-navigation"
      onTouchEnd={handleTouchEnd}
      onTouchStart={handleTouchStart}
    >
      {previousItem ? (
        <Link className="secondary-button reader-nav-button" href={`/work/${previousItem.id}`}>
          <ChevronLeft size={18} aria-hidden="true" />
          <span>Previous</span>
        </Link>
      ) : (
        <span className="secondary-button reader-nav-button disabled-button" aria-disabled="true">
          <ChevronLeft size={18} aria-hidden="true" />
          <span>Previous</span>
        </span>
      )}
      {firstItem ? (
        <Link className="secondary-button reader-nav-button" href={`/work/${firstItem.id}`}>
          <ChevronsLeft size={18} aria-hidden="true" />
          <span>Beginning</span>
        </Link>
      ) : (
        <span className="secondary-button reader-nav-button disabled-button" aria-disabled="true">
          <ChevronsLeft size={18} aria-hidden="true" />
          <span>Beginning</span>
        </span>
      )}
      {effectiveNextItem ? (
        <Link className="secondary-button reader-nav-button" href={`/work/${effectiveNextItem.id}`}>
          <span>{nextLabel}</span>
          <ChevronRight size={18} aria-hidden="true" />
        </Link>
      ) : (
        <span className="secondary-button reader-nav-button disabled-button" aria-disabled="true">
          <span>{isLoadingContinuation ? "Finding next" : "Next"}</span>
          <ChevronRight size={18} aria-hidden="true" />
        </span>
      )}
    </nav>
  );
}
