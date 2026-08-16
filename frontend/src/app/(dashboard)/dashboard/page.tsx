'use client';

import { AppShell } from '@/components/layout/AppShell/AppShell';
import { PageHeader } from '@/components/ui/PageHeader';
import { DashboardScreen } from '@/features/dashboard/DashboardScreen';
import { RequireAuth } from '@/features/auth/RequireAuth';

export default function DashboardPage() {
  return (
    <RequireAuth>
      <AppShell title="Dashboard">
        <PageHeader
          title="Today at a glance"
          description="Everything that needs your attention, tailored to what your role covers."
        />
        <DashboardScreen />
      </AppShell>
    </RequireAuth>
  );
}
