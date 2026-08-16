'use client';

import { AppShell } from '@/components/layout/AppShell/AppShell';
import { PageHeader } from '@/components/ui/PageHeader';
import { PurchasesScreen } from '@/features/purchases/PurchasesScreen';
import { RequireAuth } from '@/features/auth/RequireAuth';

export default function PurchasesPage() {
  return (
    <RequireAuth permissions={['purchase.view']}>
      <AppShell title="Purchases">
        <PageHeader
          title="Purchases"
          description="Receive stock from suppliers, review past receipts and manage the supplier list."
        />
        <PurchasesScreen />
      </AppShell>
    </RequireAuth>
  );
}
