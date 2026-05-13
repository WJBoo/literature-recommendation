import { AppShell } from "../../components/AppShell";
import { ProfileDashboard } from "../../components/ProfileDashboard";

export default function ProfilePage() {
  return (
    <AppShell>
      <section className="hero">
        <p className="eyebrow">Profile</p>
        <h1>Your reading profile.</h1>
        <p className="muted">
          Saved pieces, annotations, liked works, and recommendation controls live here.
        </p>
      </section>
      <ProfileDashboard />
    </AppShell>
  );
}
