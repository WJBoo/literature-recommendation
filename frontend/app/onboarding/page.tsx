import { AppShell } from "../../components/AppShell";
import { AccountPreferencesForm } from "../../components/AccountPreferencesForm";

export default function OnboardingPage() {
  return (
    <AppShell>
      <section className="hero">
        <p className="eyebrow">Preferences</p>
        <h1>Tune your first recommendations.</h1>
        <p className="muted">
          Choose the textures, forms, and moods you want the library to notice first.
        </p>
      </section>
      <AccountPreferencesForm />
    </AppShell>
  );
}
