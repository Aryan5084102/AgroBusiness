'use client';

import { AppShell } from '@/components/layout/AppShell/AppShell';
import { PageHeader } from '@/components/ui/PageHeader';
import { PosScreen } from '@/features/pos/PosScreen';
import { RequireAuth } from '@/features/auth/RequireAuth';

export default function SalesPage() {
  return (
    <RequireAuth>
      <AppShell title="Retail POS">
        <PageHeader
          title="Retail counter"
          description="Search products, build the cart, take payment. Prices and stock come live from the server."
        />
        <PosScreen />
      </AppShell>
    </RequireAuth>
  );
}
