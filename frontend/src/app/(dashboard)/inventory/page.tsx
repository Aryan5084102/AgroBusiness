'use client';

import { AppShell } from '@/components/layout/AppShell/AppShell';
import { ComingSoon } from '@/components/feedback/ComingSoon';
import { PageHeader } from '@/components/ui/PageHeader';
import { RequireAuth } from '@/features/auth/RequireAuth';

export default function InventoryPage() {
  return (
    <RequireAuth>
      <AppShell title="Inventory">
        <PageHeader
          title="Inventory"
          description="Stock ledger, batches and transfers."
        />
        <ComingSoon
          feature="Stock, batches, transfers & counts"
          note="The append-only stock ledger, FEFO, reservations and transfers are implemented and tested at the service layer. Read/adjust screens are being built."
        />
      </AppShell>
    </RequireAuth>
  );
}
