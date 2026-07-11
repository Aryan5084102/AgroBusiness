import { AppShell } from '@/components/layout/AppShell/AppShell';
import { PageHeader } from '@/components/ui/PageHeader';
import { DashboardMetrics } from '@/features/dashboard/DashboardMetrics';
import { RequireAuth } from '@/features/auth/RequireAuth';

// Authenticated owner dashboard backed by the reports/dashboard endpoint.
export default function DashboardPage() {
  return (
    <RequireAuth>
      <AppShell title="Dashboard">
        <PageHeader
          title="Today at a glance"
          description="Live sales, collections, receivables and stock alerts."
        />
        <DashboardMetrics />
      </AppShell>
    </RequireAuth>
  );
}
