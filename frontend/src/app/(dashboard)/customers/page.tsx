'use client';

import { AppShell } from '@/components/layout/AppShell/AppShell';
import { PageHeader } from '@/components/ui/PageHeader';
import { CustomersPanel } from '@/features/customers/CustomersPanel';
import { RequireAuth } from '@/features/auth/RequireAuth';

export default function CustomersPage() {
  return (
    <RequireAuth>
      <AppShell title="Customers">
        <PageHeader
          title="Customers & dealers"
          description="Farmers, retailers and dealers with credit limits and outstanding balances."
        />
        <CustomersPanel />
      </AppShell>
    </RequireAuth>
  );
}
