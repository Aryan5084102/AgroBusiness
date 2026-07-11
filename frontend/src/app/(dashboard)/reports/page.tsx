'use client';

import { AppShell } from '@/components/layout/AppShell/AppShell';
import { ComingSoon } from '@/components/feedback/ComingSoon';
import { PageHeader } from '@/components/ui/PageHeader';
import { DashboardMetrics } from '@/features/dashboard/DashboardMetrics';
import { RequireAuth } from '@/features/auth/RequireAuth';

export default function ReportsPage() {
  return (
    <RequireAuth>
      <AppShell title="Reports">
        <PageHeader
          title="Reports"
          description="Live summary. Detailed registers and exports are next."
        />
        <DashboardMetrics />
        <div style={{ marginTop: 'var(--space-6)' }}>
          <ComingSoon
            feature="Sales / purchase / stock / GST registers with CSV & PDF export"
            note="The GST summary and dashboard aggregations are implemented and tested (GET /reports/gst-summary, /reports/dashboard). Filtered registers and exports are being built."
          />
        </div>
      </AppShell>
    </RequireAuth>
  );
}
