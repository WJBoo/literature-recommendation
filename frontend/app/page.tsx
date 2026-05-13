import { AppShell } from "../components/AppShell";
import { PoemOfTheDay } from "../components/PoemOfTheDay";
import { RecommendationSurface } from "../components/RecommendationSurface";
import { recommendationSections } from "../lib/mockData";

export default function HomePage() {
  return (
    <AppShell>
      <section className="hero">
        <div className="dictionary-entry" aria-labelledby="linguaphilia-heading">
          <div className="dictionary-headword">
            <h1 className="dictionary-word" id="linguaphilia-heading">
              Linguaphilia
            </h1>
            <span className="dictionary-pronunciation"> lin-gwa-fil-ee-uh</span>
          </div>
          <p className="dictionary-definition">
            <span className="dictionary-number">1.</span>
            <span className="dictionary-part">noun</span> A love of language
          </p>
          <p className="dictionary-definition">
            <span className="dictionary-number">2.</span>
            <span className="dictionary-part">noun</span> A platform to discover new ways of using language.
          </p>
        </div>
      </section>
      <PoemOfTheDay />
      <RecommendationSurface fallbackSections={recommendationSections} />
    </AppShell>
  );
}
