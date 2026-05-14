import Link from "next/link";
import Image from "next/image";
import { AppShell } from "../../../components/AppShell";
import { AuthorFollowButton } from "../../../components/AuthorFollowButton";
import { HighlightedReaderBody } from "../../../components/HighlightedReaderBody";
import { InteractionButtons } from "../../../components/InteractionButtons";
import { ListeningPanel } from "../../../components/ListeningPanel";
import { PostOwnerControls } from "../../../components/PostOwnerControls";
import { ReaderNavigation } from "../../../components/ReaderNavigation";
import { ReadingProgressTracker } from "../../../components/ReadingProgressTracker";
import { fetchReaderItem } from "../../../lib/api";
import { authorId } from "../../../lib/authorIds";
import { getWork } from "../../../lib/mockData";
import type { PostMediaItem } from "../../../lib/types";

const sampleReaderText = `The room had grown quiet enough for every small thought to sound like a footstep. Outside, the street carried on with its ordinary business, but here the page seemed to gather the afternoon into a single breath.

She read the sentence again, slower this time, and found that it had changed while she was away from it. Or perhaps she had changed. Literature had a way of doing that: waiting in the same place until the reader arrived as someone else.

The recommendation felt less like a command than an invitation. Continue, it seemed to say, and see what kind of attention you become.`;

export default async function WorkPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams?: Promise<{ annotation?: string }>;
}) {
  const { id } = await params;
  const annotationId = (await searchParams)?.annotation ?? null;
  const fallbackWork = getWork(id);
  const item = await fetchReaderItem(id).catch(() => ({
    id: fallbackWork.id,
    work_id: fallbackWork.id,
    title: fallbackWork.title,
    author: fallbackWork.author,
    form: fallbackWork.form,
    text: sampleReaderText,
    chunk_type: "demo",
    word_count: sampleReaderText.split(/\s+/).length,
    subjects: fallbackWork.tags,
    work_title: fallbackWork.title,
    section_title: null,
    section_excerpt_index: null,
    section_excerpt_count: null,
    excerpt_label: null,
    media: [],
    first_item: null,
    previous_item: null,
    next_item: null,
  }));
  const workByline =
    item.work_title && item.work_title !== item.title ? `${item.work_title} · ` : "";
  const partByline = readerPartByline(item);
  const writerId = authorId(item.author);
  const hasSiblingExcerpts = readerHasSiblingExcerpts(item);

  return (
    <AppShell>
      <div className="reader">
        <Link className="secondary-button" href="/">
          Back to discovery
        </Link>
        <ReadingProgressTracker
          item={{
            id: item.id,
            work_id: item.work_id,
            title: item.title,
            author: item.author,
            form: item.form,
            work_title: item.work_title,
            section_title: item.section_title,
            excerpt_label: item.excerpt_label,
          }}
        />
        <header>
          <p className="eyebrow">{item.form}</p>
          <div className="reader-title-row">
            <h1>{item.title}</h1>
            <AuthorFollowButton authorId={writerId} initialFollowed={false} />
          </div>
          <p className="muted">
            {partByline ? `${partByline} · ` : workByline}
            <Link className="text-link" href={`/authors/${writerId}`}>
              {item.author}
            </Link>{" "}
            · {item.word_count} words
          </p>
        </header>
        {item.media?.length ? <ReaderMedia media={item.media} /> : null}
        <InteractionButtons
          author={item.author}
          excerptId={item.id}
          hasSiblingExcerpts={hasSiblingExcerpts}
          workId={item.work_id}
          workTitle={item.work_title ?? item.title}
        >
          <ListeningPanel excerptId={item.id} />
        </InteractionButtons>
        {item.chunk_type === "user_post" ? <PostOwnerControls postId={item.id} /> : null}
        <ReaderNavigation
          currentAuthor={item.author}
          currentSectionExcerptCount={item.section_excerpt_count}
          currentSectionExcerptIndex={item.section_excerpt_index}
          currentExcerptId={item.id}
          currentWorkId={item.work_id}
          currentWorkTitle={item.work_title ?? item.title}
          firstItem={item.first_item}
          previousItem={item.previous_item}
          nextItem={item.next_item}
        />
        <HighlightedReaderBody
          excerptId={item.id}
          initialAnnotationId={annotationId}
          text={item.text}
        />
        <ChapterContinuationCallout
          nextItem={item.next_item}
          sectionExcerptCount={item.section_excerpt_count}
          sectionExcerptIndex={item.section_excerpt_index}
          sectionTitle={item.section_title}
        />
        <ReaderNavigation
          currentAuthor={item.author}
          currentSectionExcerptCount={item.section_excerpt_count}
          currentSectionExcerptIndex={item.section_excerpt_index}
          currentExcerptId={item.id}
          currentWorkId={item.work_id}
          currentWorkTitle={item.work_title ?? item.title}
          firstItem={item.first_item}
          previousItem={item.previous_item}
          nextItem={item.next_item}
        />
      </div>
    </AppShell>
  );
}

function ChapterContinuationCallout({
  nextItem,
  sectionExcerptCount,
  sectionExcerptIndex,
  sectionTitle,
}: {
  nextItem?: { id: string } | null;
  sectionExcerptCount?: number | null;
  sectionExcerptIndex?: number | null;
  sectionTitle?: string | null;
}) {
  if (!nextItem || !sectionExcerptIndex || !sectionExcerptCount) {
    return null;
  }
  if (sectionExcerptIndex >= sectionExcerptCount) {
    return null;
  }

  const nextExcerptIndex = sectionExcerptIndex + 1;
  const sectionKind = readerSectionKind(sectionTitle);
  return (
    <aside className="reader-continuation-card">
      <span>
        This {sectionKind} continues in Excerpt {nextExcerptIndex}/{sectionExcerptCount}.
      </span>
      <Link className="primary-button" href={`/work/${nextItem.id}`}>
        Continue {sectionKind}
      </Link>
    </aside>
  );
}

function readerSectionKind(sectionTitle?: string | null) {
  const normalized = (sectionTitle ?? "").trim().toLowerCase();
  if (normalized.startsWith("letter")) {
    return "letter";
  }
  if (normalized.startsWith("act") || normalized.startsWith("scene")) {
    return "section";
  }
  return "chapter";
}

function readerPartByline(item: {
  form: string;
  section_title?: string | null;
  section_excerpt_index?: number | null;
  section_excerpt_count?: number | null;
  excerpt_label?: string | null;
}) {
  if (item.form.toLowerCase() === "poetry") {
    return null;
  }

  const sectionTitle = cleanPartLabel(item.section_title);
  const excerptLabel = cleanPartLabel(item.excerpt_label);
  const excerptProgress = readerExcerptProgress(item);
  if (!sectionTitle) {
    return excerptProgress ?? excerptLabel;
  }
  if (excerptProgress) {
    return `${sectionTitle}, ${excerptProgress}`;
  }
  if (!excerptLabel || excerptLabel.toLowerCase().startsWith(sectionTitle.toLowerCase())) {
    return excerptLabel ?? sectionTitle;
  }
  return `${sectionTitle}, ${excerptLabel}`;
}

function readerExcerptProgress(item: {
  section_excerpt_index?: number | null;
  section_excerpt_count?: number | null;
}) {
  if (!item.section_excerpt_index || !item.section_excerpt_count) {
    return null;
  }
  return `Excerpt ${item.section_excerpt_index}/${item.section_excerpt_count}`;
}

function readerHasSiblingExcerpts(item: {
  first_item?: { id: string } | null;
  previous_item?: { id: string } | null;
  next_item?: { id: string } | null;
  section_excerpt_count?: number | null;
}) {
  return Boolean(
    item.first_item ||
      item.previous_item ||
      item.next_item ||
      (item.section_excerpt_count && item.section_excerpt_count > 1),
  );
}

function cleanPartLabel(value?: string | null) {
  return value ? value.replace(/\s+/g, " ").trim() : null;
}

function ReaderMedia({ media }: { media: PostMediaItem[] }) {
  return (
    <div className="reader-media-block">
      {media.map((item) => (
        <figure className="reader-media-figure" key={item.id}>
          {item.media_type === "image" ? (
            <Image
              alt={item.alt_text || item.caption || "Post image"}
              className="reader-media-item"
              height={620}
              loading="eager"
              src={item.data_url}
              unoptimized
              width={960}
            />
          ) : (
            <video className="reader-media-item" controls playsInline src={item.data_url} />
          )}
          {item.caption ? <figcaption>{item.caption}</figcaption> : null}
        </figure>
      ))}
    </div>
  );
}
