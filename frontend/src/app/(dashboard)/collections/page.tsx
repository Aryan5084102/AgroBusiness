'use client';

import { AppShell } from '@/components/layout/AppShell/AppShell';
import { PageHeader } from '@/components/ui/PageHeader';
import { CollectionsScreen } from '@/features/collections/CollectionsScreen';
import { RequireAuth } from '@/features/auth/RequireAuth';

export default function CollectionsPage() {
  return (
    <RequireAuth>
      <AppShell title="Collections">
        <PageHeader
          title="Collections"
          description="Receive customer payments; the server allocates them across open invoices, oldest first."
        />
        <CollectionsScreen />
      </AppShell>
    </RequireAuth>
  );
}
