'use client';

import { AppShell } from '@/components/layout/AppShell/AppShell';
import { ComingSoon } from '@/components/feedback/ComingSoon';
import { PageHeader } from '@/components/ui/PageHeader';
import { RequireAuth } from '@/features/auth/RequireAuth';

export default function SettingsPage() {
  return (
    <RequireAuth>
      <AppShell title="Settings">
        <PageHeader title="Settings" description="Users, roles, branches and branding." />
        <ComingSoon
          feature="Organization settings & user management"
          note="Users, roles and RBAC are implemented and tested (GET/POST /users). The settings UI is being built."
        />
      </AppShell>
    </RequireAuth>
  );
}
