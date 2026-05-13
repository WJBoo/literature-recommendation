import { AppShell } from "../../components/AppShell";
import { NotificationsCenter } from "../../components/NotificationsCenter";

export default function NotificationsPage() {
  return (
    <AppShell>
      <section className="hero">
        <p className="eyebrow">Tune</p>
        <h1>Notifications center.</h1>
      </section>
      <NotificationsCenter />
    </AppShell>
  );
}
