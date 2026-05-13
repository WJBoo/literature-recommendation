import { AppShell } from "../../../components/AppShell";
import { ReaderProfileView } from "../../../components/ReaderProfileView";

export default async function ReaderProfilePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <AppShell>
      <ReaderProfileView userId={id} />
    </AppShell>
  );
}
