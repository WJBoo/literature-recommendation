import type { RecommendationSection } from "../lib/types";
import { WorkCard } from "./WorkCard";
import type { ExcerptLength } from "./WorkCard";

export function RecommendationRow({
  section,
  excerptLength,
}: {
  section: RecommendationSection;
  excerptLength: ExcerptLength;
}) {
  return (
    <section className="section">
      <div className="row-header">
        <div>
          <h2>{section.title}</h2>
          {section.subtitle ? <p className="muted">{section.subtitle}</p> : null}
        </div>
      </div>
      <div className="work-row">
        {section.works.map((work) => (
          <WorkCard key={work.id} work={work} excerptLength={excerptLength} />
        ))}
      </div>
    </section>
  );
}
