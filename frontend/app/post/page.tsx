import { AppShell } from "../../components/AppShell";
import { PostComposer } from "../../components/PostComposer";

export default function PostPage() {
  return (
    <AppShell>
      <section className="hero">
        <p className="eyebrow">Post</p>
        <h1>Share original literature.</h1>
        <p className="muted">
          Draft a poem, story, essay, or excerpt for your own shelf.
        </p>
      </section>
      <PostComposer />
    </AppShell>
  );
}
