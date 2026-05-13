import { BookOpen } from "lucide-react";
import Link from "next/link";
import { Fragment } from "react";
import { authorId } from "../lib/authorIds";
import type { Work } from "../lib/types";

export type ExcerptLength = "short" | "medium" | "long";

const excerptLengthLimits: Record<ExcerptLength, number> = {
  short: 120,
  medium: 220,
  long: 360,
};

export function WorkCard({
  work,
  excerptLength = "medium",
}: {
  work: Work;
  excerptLength?: ExcerptLength;
}) {
  const byline =
    work.work_title && work.work_title !== work.title
      ? work.work_title
      : null;
  const preview = truncateExcerpt(work.excerpt, excerptLengthLimits[excerptLength]);

  return (
    <article className="work-card">
      <p className="eyebrow">{work.form}</p>
      <div className="work-card-heading">
        <h3 className="work-card-title">{work.title}</h3>
        {byline ? <p className="work-card-work-title">{byline}</p> : null}
        <p className="work-card-author">
          <Link className="text-link" href={`/authors/${authorId(work.author)}`}>
            {work.author}
          </Link>
        </p>
      </div>
      <p className="work-card-reason">{renderReason(work.reason)}</p>
      <p className="work-card-excerpt">{preview}</p>
      <Link className="primary-button" href={`/work/${work.id}`}>
        <BookOpen size={17} aria-hidden="true" />
        Read
      </Link>
      <div className="tag-list">
        {work.tags.map((tag) => (
          <span className="tag" key={tag}>
            {tag}
          </span>
        ))}
      </div>
    </article>
  );
}

function renderReason(reason: string) {
  const parts = reason.split(/(\*\*[^*]+\*\*)/g).filter(Boolean);
  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={`${part}-${index}`}>{part.slice(2, -2)}</strong>;
    }
    return <Fragment key={`${part}-${index}`}>{part}</Fragment>;
  });
}

function truncateExcerpt(excerpt: string, characterLimit: number): string {
  const normalized = excerpt.replace(/\s+/g, " ").trim();
  if (normalized.length <= characterLimit) {
    return normalized;
  }

  const clipped = normalized.slice(0, characterLimit);
  const lastSpace = clipped.lastIndexOf(" ");
  return `${clipped.slice(0, lastSpace > 80 ? lastSpace : characterLimit).trim()}...`;
}
