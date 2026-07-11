'use client';

import { formatCurrency } from '@/lib/formatting/currency';
import { useDashboard } from './useDashboard';
import styles from './DashboardMetrics.module.scss';

interface Metric {
  label: string;
  value: string;
  hint?: string;
  tone?: 'default' | 'warn';
}

// Owner dashboard tiles backed by the reports/dashboard endpoint.
export function DashboardMetrics() {
  const { data, isLoading, isError } = useDashboard();

  if (isError) {
    return (
      <p role="alert" className={styles.error}>
        Could not load dashboard metrics.
      </p>
    );
  }

  const metrics: Metric[] = [
    { label: 'Sales today', value: money(data?.sales_today_total) },
    { label: 'Retail today', value: money(data?.retail_today_total) },
    { label: 'Wholesale today', value: money(data?.wholesale_today_total) },
    { label: 'Collected today', value: money(data?.collected_today_total) },
    { label: 'Receivables outstanding', value: money(data?.receivables_outstanding) },
    {
      label: 'Low-stock products',
      value: data ? String(data.low_stock_product_count) : '—',
      tone: data && data.low_stock_product_count > 0 ? 'warn' : 'default',
      hint: 'Below configured minimum',
    },
  ];

  return (
    <div className={styles.grid}>
      {metrics.map((m) => (
        <section
          key={m.label}
          className={`${styles.card} ${m.tone === 'warn' ? styles.warn : ''}`}
        >
          <p className={styles.label}>{m.label}</p>
          <p className={`${styles.value} tabular-nums`}>{isLoading ? '…' : m.value}</p>
          {m.hint ? <p className={styles.hint}>{m.hint}</p> : null}
        </section>
      ))}
    </div>
  );
}

function money(value: string | undefined): string {
  return value === undefined ? '—' : formatCurrency(value);
}
