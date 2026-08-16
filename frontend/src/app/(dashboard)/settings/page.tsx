'use client';

import { AppShell } from '@/components/layout/AppShell/AppShell';
import { PageHeader } from '@/components/ui/PageHeader';
import { RequireAuth } from '@/features/auth/RequireAuth';
import { SettingsScreen } from '@/features/settings/SettingsScreen';

export default function SettingsPage() {
  return (
    <RequireAuth permissions={['user.manage', 'settings.manage']}>
      <AppShell title="Settings">
        <PageHeader
          title="Settings"
          description="Business details, staff accounts, roles and your branch/warehouse structure."
        />
        <SettingsScreen />
      </AppShell>
    </RequireAuth>
  );
}
