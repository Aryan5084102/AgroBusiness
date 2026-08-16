'use client';

import { AppShell } from '@/components/layout/AppShell/AppShell';
import { PageHeader } from '@/components/ui/PageHeader';
import { InvoicesScreen } from '@/features/invoices/InvoicesScreen';
import { RequireAuth } from '@/features/auth/RequireAuth';

export default function InvoicesPage() {
  return (
    <RequireAuth permissions={['sales.create']}>
      <AppShell title="Invoices">
        <PageHeader
          title="Invoices"
          description="Every retail and wholesale invoice raised, with its lines and taxes."
        />
        <InvoicesScreen />
      </AppShell>
    </RequireAuth>
  );
}
