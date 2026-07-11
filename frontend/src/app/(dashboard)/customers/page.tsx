'use client';

import { AppShell } from '@/components/layout/AppShell/AppShell';
import { ComingSoon } from '@/components/feedback/ComingSoon';
import { PageHeader } from '@/components/ui/PageHeader';
import { RequireAuth } from '@/features/auth/RequireAuth';

export default function CustomersPage() {
  return (
    <RequireAuth>
      <AppShell title="Customers">
        <PageHeader title="Customers" description="Farmers, retailers and dealers." />
        <ComingSoon
          feature="Customer & dealer CRM"
          note="Customers, credit limits and ledgers back the wholesale and collections flows already tested. The CRM screens are being built."
        />
      </AppShell>
    </RequireAuth>
  );
}
