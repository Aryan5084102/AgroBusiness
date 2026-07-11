import { AppShell } from '@/components/layout/AppShell/AppShell';
import { RequireAuth } from '@/features/auth/RequireAuth';
import styles from './page.module.scss';

// Authenticated dashboard shell. Real owner metrics (sales, receivables, stock
// value, alerts) are populated in later phases.
export default function DashboardPage() {
  return (
    <RequireAuth>
      <DashboardContent />
    </RequireAuth>
  );
}

function DashboardContent() {
  return (
    <AppShell title="Dashboard">
      <div className={styles.grid}>
        {['Today’s sales', 'Receivables', 'Stock value', 'Low-stock items'].map(
          (label) => (
            <section key={label} className={styles.card}>
              <p className={styles.label}>{label}</p>
              <p className={`${styles.value} tabular-nums`}>—</p>
              <p className={styles.hint}>Available from Phase 4 onward</p>
            </section>
          ),
        )}
      </div>
    </AppShell>
  );
}
