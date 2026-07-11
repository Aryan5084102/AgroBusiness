'use client';

import { AppShell } from '@/components/layout/AppShell/AppShell';
import { ComingSoon } from '@/components/feedback/ComingSoon';
import { PageHeader } from '@/components/ui/PageHeader';
import { RequireAuth } from '@/features/auth/RequireAuth';

export default function SalesPage() {
  return (
    <RequireAuth>
      <AppShell title="Sales">
        <PageHeader title="Sales" description="Retail POS and wholesale orders." />
        <ComingSoon
          feature="Retail POS & wholesale ordering"
          note="Sale finalization, FEFO stock deduction, pricing and payments are implemented and tested via the API (POST /pos/invoices, /wholesale/orders). The counter UI is being built."
        />
      </AppShell>
    </RequireAuth>
  );
}
