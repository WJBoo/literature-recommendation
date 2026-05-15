"use client";

import { BookOpen, CalendarDays } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { authorId } from "../lib/authorIds";
import { fetchPoemOfTheDay } from "../lib/api";
import type { PoemOfTheDay as PoemOfTheDayData } from "../lib/types";

export function PoemOfTheDay() {
  const [poem, setPoem] = useState<PoemOfTheDayData | null>(null);

  useEffect(() => {
    let mounted = true;
    void fetchPoemOfTheDay()
      .then((payload) => {
        if (mounted) {
          setPoem(payload);
        }
      })
      .catch(() => {
        if (mounted) {
          setPoem(null);
        }
      });

    return () => {
      mounted = false;
    };
  }, []);

  if (!poem) {
    return null;
  }

  return (
    <section className="poem-of-day" aria-labelledby="poem-of-day-heading">
      <div className="poem-of-day-copy">
        <p className="eyebrow">Poem of the Day</p>
        <h2 id="poem-of-day-heading">{poem.work.title}</h2>
        <p className="poem-of-day-meta">
          <CalendarDays size={15} aria-hidden="true" />
          {formatDailyDate(poem.date)} ·{" "}
          <Link className="text-link" href={`/authors/${authorId(poem.work.author)}`}>
            {poem.work.author}
          </Link>
        </p>
        <p className="poem-of-day-excerpt">{poem.work.excerpt}</p>
      </div>
      <Link className="primary-button" href={`/work/${poem.work.id}?feature=poem-of-the-day`}>
        <BookOpen size={17} aria-hidden="true" />
        Read poem
      </Link>
    </section>
  );
}

function formatDailyDate(value: string): string {
  const date = new Date(`${value}T00:00:00`);
  return new Intl.DateTimeFormat(undefined, {
    month: "long",
    day: "numeric",
    year: "numeric",
  }).format(date);
}
