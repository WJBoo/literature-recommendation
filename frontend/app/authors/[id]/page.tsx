import Link from "next/link";
import { notFound } from "next/navigation";
import { AppShell } from "../../../components/AppShell";
import { AuthorFollowButton } from "../../../components/AuthorFollowButton";
import { fetchAuthorProfile } from "../../../lib/api";

export default async function AuthorPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const author = await fetchAuthorProfile(id).catch(() => null);
  if (!author) {
    notFound();
  }

  return (
    <AppShell>
      <section className="author-profile-hero">
        <div className="author-avatar" aria-hidden="true">
          {author.name.slice(0, 1)}
        </div>
        <div className="author-profile-copy">
          <p className="eyebrow">Author</p>
          <h1>{author.name}</h1>
          <p className="muted">
            {author.work_count} works · {author.excerpt_count} excerpts in the local corpus
          </p>
          <div className="profile-stats">
            <span>
              <strong>{author.forms.length}</strong>
              forms
            </span>
            <span>
              <strong>{author.subjects.length}</strong>
              themes
            </span>
            <span>
              <strong>{author.sample_excerpts.length}</strong>
              samples
            </span>
          </div>
          <AuthorFollowButton authorId={author.id} initialFollowed={author.followed} />
        </div>
      </section>

      <section className="section">
        <div className="row-header">
          <div>
            <h2>Works</h2>
            <p className="muted">Corpus-derived works and excerpt sets.</p>
          </div>
        </div>
        <div className="author-work-grid">
          {author.works.map((work) => (
            <Link className="author-work-card" href={`/work/${work.first_excerpt_id}`} key={work.work_id}>
              <p className="eyebrow">{work.form}</p>
              <h3>{work.title}</h3>
              <p className="muted">{work.excerpt_count} excerpts</p>
              <div className="tag-list">
                {work.subjects.slice(0, 4).map((subject) => (
                  <span className="tag" key={subject}>
                    {subject}
                  </span>
                ))}
              </div>
            </Link>
          ))}
        </div>
      </section>

      <section className="section">
        <div className="row-header">
          <div>
            <h2>Sample passages</h2>
            <p className="muted">Longer excerpts that help characterize this author.</p>
          </div>
        </div>
        <div className="author-excerpt-grid">
          {author.sample_excerpts.map((excerpt) => (
            <Link className="author-excerpt-card" href={`/work/${excerpt.id}`} key={excerpt.id}>
              <p className="eyebrow">{excerpt.form}</p>
              <h3>{excerpt.title}</h3>
              <p className="muted">
                {excerpt.work_title} · {excerpt.word_count} words
              </p>
              <p>{excerpt.preview}</p>
            </Link>
          ))}
        </div>
      </section>
    </AppShell>
  );
}
