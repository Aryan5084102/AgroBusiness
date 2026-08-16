'use client';

import { AppShell } from '@/components/layout/AppShell/AppShell';
import { PageHeader } from '@/components/ui/PageHeader';
import { RequireAuth } from '@/features/auth/RequireAuth';
import { WholesaleScreen } from '@/features/wholesale/WholesaleScreen';

export default function WholesalePage() {
  return (
    <RequireAuth permissions={['sales.create']}>
      <AppShell title="Wholesale orders">
        <PageHeader
          title="Wholesale orders"
          description="Create dealer orders with credit control, reserve stock, then dispatch and invoice."
        />
        <WholesaleScreen />
      </AppShell>
    </RequireAuth>
  );
}
