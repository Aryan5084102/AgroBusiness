'use client';

import { AppShell } from '@/components/layout/AppShell/AppShell';
import { PageHeader } from '@/components/ui/PageHeader';
import { AuditScreen } from '@/features/audit/AuditScreen';
import { RequireAuth } from '@/features/auth/RequireAuth';

export default function AuditPage() {
  return (
    <RequireAuth permissions={['audit.view']}>
      <AppShell title="Audit log">
        <PageHeader
          title="Audit log"
          description="An append-only record of sign-ins and privileged actions. Nothing here can be edited."
        />
        <AuditScreen />
      </AppShell>
    </RequireAuth>
  );
}
