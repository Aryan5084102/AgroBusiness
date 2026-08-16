'use client';

import { AppShell } from '@/components/layout/AppShell/AppShell';
import { PageHeader } from '@/components/ui/PageHeader';
import { RequireAuth } from '@/features/auth/RequireAuth';
import { ProductsTable } from '@/features/products/ProductsTable';

export default function ProductsPage() {
  return (
    <RequireAuth permissions={['product.view']}>
      <AppShell title="Products">
        <PageHeader
          title="Products"
          description="Your catalogue of seeds, fertilizers, pesticides, machines, spares and tools."
        />
        <ProductsTable />
      </AppShell>
    </RequireAuth>
  );
}
