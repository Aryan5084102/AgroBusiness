'use client';

import { use } from 'react';
import { BillScreen } from '@/features/invoices/BillScreen';
import { RequireAuth } from '@/features/auth/RequireAuth';

/**
 * A single printable bill. No `AppShell` on purpose — this page *is* the
 * document, so it carries no sidebar or app header to strip out at print time.
 */
export default function BillPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return (
    <RequireAuth permissions={['sales.create']}>
      <BillScreen invoiceId={id} />
    </RequireAuth>
  );
}
