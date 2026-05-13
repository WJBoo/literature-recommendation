import { AppShell } from "../../components/AppShell";
import { WriterDiscovery } from "../../components/WriterDiscovery";

export default function ConnectPage() {
  return (
    <AppShell>
      <section className="hero">
        <p className="eyebrow">Discover Writers</p>
        <h1>Find writers, readers, and authors.</h1>
      </section>
      <WriterDiscovery />
    </AppShell>
  );
}
