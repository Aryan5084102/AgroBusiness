// Dashboard feature API (owner metrics).
import { apiFetch } from '@/lib/api/client';

export interface DashboardSummary {
  as_of: string;
  sales_today_total: string;
  retail_today_total: string;
  wholesale_today_total: string;
  collected_today_total: string;
  receivables_outstanding: string;
  low_stock_product_count: number;
}

export function fetchDashboard(): Promise<DashboardSummary> {
  return apiFetch<DashboardSummary>('/api/v1/reports/dashboard');
}
