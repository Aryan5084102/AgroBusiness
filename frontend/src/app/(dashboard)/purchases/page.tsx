'use client';

import { useState } from 'react';
import { AppShell } from '@/components/layout/AppShell/AppShell';
import { PageHeader } from '@/components/ui/PageHeader';
import { GoodsReceiptScreen } from '@/features/goods-receipt/GoodsReceiptScreen';
import { RequireAuth } from '@/features/auth/RequireAuth';
import { SuppliersPanel } from '@/features/suppliers/SuppliersPanel';
import styles from './page.module.scss';

type Tab = 'receive' | 'suppliers';

export default function PurchasesPage() {
  const [tab, setTab] = useState<Tab>('receive');
  return (
    <RequireAuth>
      <AppShell title="Purchases">
        <PageHeader
          title="Purchases"
          description="Receive stock from suppliers and manage the supplier list."
        />
        <div className={styles.tabs} role="tablist" aria-label="Purchases sections">
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'receive'}
            className={`${styles.tab} ${tab === 'receive' ? styles.active : ''}`}
            onClick={() => setTab('receive')}
          >
            Goods receipt
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'suppliers'}
            className={`${styles.tab} ${tab === 'suppliers' ? styles.active : ''}`}
            onClick={() => setTab('suppliers')}
          >
            Suppliers
          </button>
        </div>
        {tab === 'receive' ? <GoodsReceiptScreen /> : <SuppliersPanel />}
      </AppShell>
    </RequireAuth>
  );
}
