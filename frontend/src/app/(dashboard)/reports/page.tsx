'use client';

import { AppShell } from '@/components/layout/AppShell/AppShell';
import { PageHeader } from '@/components/ui/PageHeader';
import { ReportsScreen } from '@/features/reports/ReportsScreen';
import { RequireAuth } from '@/features/auth/RequireAuth';

export default function ReportsPage() {
  return (
    <RequireAuth permissions={['report.view']}>
      <AppShell title="Reports">
        <PageHeader
          title="Reports"
          description="Sales, purchases, GST and stock valuation — filter by date and export to CSV."
        />
        <ReportsScreen />
      </AppShell>
    </RequireAuth>
  );
}
