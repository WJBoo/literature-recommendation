import { AppShell } from "../../components/AppShell";
import { MessagesPanel } from "../../components/MessagesPanel";

export default function MessagesPage() {
  return (
    <AppShell>
      <section className="hero">
        <p className="eyebrow">Messages</p>
        <h1>Chats with readers.</h1>
      </section>
      <MessagesPanel />
    </AppShell>
  );
}
