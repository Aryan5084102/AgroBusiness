'use client';

import { AppShell } from '@/components/layout/AppShell/AppShell';
import { PageHeader } from '@/components/ui/PageHeader';
import { InventoryScreen } from '@/features/inventory/InventoryScreen';
import { RequireAuth } from '@/features/auth/RequireAuth';

export default function InventoryPage() {
  return (
    <RequireAuth permissions={['inventory.view']}>
      <AppShell title="Inventory">
        <PageHeader
          title="Inventory"
          description="Stock on hand, batch expiry and the full movement ledger."
        />
        <InventoryScreen />
      </AppShell>
    </RequireAuth>
  );
}
