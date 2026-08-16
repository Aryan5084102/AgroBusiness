'use client';

import { AppShell } from '@/components/layout/AppShell/AppShell';
import { PageHeader } from '@/components/ui/PageHeader';
import { AccountingScreen } from '@/features/accounting/AccountingScreen';
import { RequireAuth } from '@/features/auth/RequireAuth';

export default function AccountingPage() {
  return (
    <RequireAuth permissions={['report.view_profit']}>
      <AppShell title="Accounting">
        <PageHeader
          title="Books"
          description="Trial balance, journal register and per-customer statements, posted automatically from your documents."
        />
        <AccountingScreen />
      </AppShell>
    </RequireAuth>
  );
}
