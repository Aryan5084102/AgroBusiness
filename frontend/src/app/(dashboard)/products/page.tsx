'use client';

import { AppShell } from '@/components/layout/AppShell/AppShell';
import { PageHeader } from '@/components/ui/PageHeader';
import { RequireAuth } from '@/features/auth/RequireAuth';
import { ProductsTable } from '@/features/products/ProductsTable';

export default function ProductsPage() {
  return (
    <RequireAuth>
      <AppShell title="Products">
        <PageHeader
          title="Products"
          description="Catalogue of seeds, fertilizers, pesticides, machines and spares."
        />
        <ProductsTable />
      </AppShell>
    </RequireAuth>
  );
}
