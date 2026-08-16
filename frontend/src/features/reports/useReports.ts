'use client';

import { useQuery } from '@tanstack/react-query';
import {
  fetchGstSummary,
  fetchPurchaseRegister,
  fetchSalesRegister,
  fetchSalesTrend,
  fetchStockValuation,
  fetchTopProducts,
} from './api';

export function useSalesRegister(from: string, to: string, enabled = true) {
  return useQuery({
    queryKey: ['reports', 'sales-register', from, to],
    queryFn: () => fetchSalesRegister(from, to),
    enabled,
  });
}

export function usePurchaseRegister(from: string, to: string, enabled = true) {
  return useQuery({
    queryKey: ['reports', 'purchase-register', from, to],
    queryFn: () => fetchPurchaseRegister(from, to),
    enabled,
  });
}

export function useGstSummary(from: string, to: string, enabled = true) {
  return useQuery({
    queryKey: ['reports', 'gst', from, to],
    queryFn: () => fetchGstSummary(from, to),
    enabled,
  });
}

export function useStockValuation(enabled = true) {
  return useQuery({
    queryKey: ['reports', 'stock-valuation'],
    queryFn: fetchStockValuation,
    enabled,
  });
}

export function useTopProducts(days = 30, enabled = true) {
  return useQuery({
    queryKey: ['reports', 'top-products', days],
    queryFn: () => fetchTopProducts(days),
    enabled,
  });
}

export function useSalesTrend(days = 14, enabled = true) {
  return useQuery({
    queryKey: ['reports', 'trend', days],
    queryFn: () => fetchSalesTrend(days),
    enabled,
  });
}

/** Convenience: an ISO date N days back and today, for default report ranges. */
export function dateRange(days: number): { from: string; to: string } {
  const today = new Date();
  const start = new Date(today);
  start.setDate(today.getDate() - (days - 1));
  const iso = (d: Date) => d.toISOString().slice(0, 10);
  return { from: iso(start), to: iso(today) };
}
