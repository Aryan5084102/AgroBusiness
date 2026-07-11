'use client';

import { AppShell } from '@/components/layout/AppShell/AppShell';
import { PageHeader } from '@/components/ui/PageHeader';
import { RequireAuth } from '@/features/auth/RequireAuth';
import { SuppliersPanel } from '@/features/suppliers/SuppliersPanel';

export default function PurchasesPage() {
  return (
    <RequireAuth>
      <AppShell title="Purchases">
        <PageHeader
          title="Suppliers"
          description="Manage suppliers. Purchase orders and goods receipt UIs are next."
        />
        <SuppliersPanel />
      </AppShell>
    </RequireAuth>
  );
}
