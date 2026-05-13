import { AppShell } from "../../components/AppShell";
import { SearchBox } from "../../components/SearchBox";
import { SearchResultsView } from "../../components/SearchResultsView";

export default async function SearchPage({
  searchParams,
}: {
  searchParams: Promise<{ mode?: string; query?: string }>;
}) {
  const { mode = "all", query = "" } = await searchParams;

  return (
    <AppShell>
      <SearchBox mode={mode} />
      <section className="hero">
        <p className="eyebrow">Search</p>
        <h1>{query ? `Results for ${query}` : "Search Linguaphilia."}</h1>
        <p className="muted">Find authors, works, passages, genres, forms, and themes.</p>
      </section>
      <SearchResultsView mode={mode} query={query} />
    </AppShell>
  );
}
