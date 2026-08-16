'use client';

import { AppShell } from '@/components/layout/AppShell/AppShell';
import { PageHeader } from '@/components/ui/PageHeader';
import { RequireAuth } from '@/features/auth/RequireAuth';
import { ServiceScreen } from '@/features/service/ServiceScreen';

export default function ServicePage() {
  return (
    <RequireAuth permissions={['service.manage']}>
      <AppShell title="Repair jobs">
        <PageHeader
          title="Workshop"
          description="Book machines in, fit spare parts, and bill labour — warranty cover is applied automatically."
        />
        <ServiceScreen />
      </AppShell>
    </RequireAuth>
  );
}
