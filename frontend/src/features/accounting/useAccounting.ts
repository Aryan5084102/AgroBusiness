'use client';

import { useQuery } from '@tanstack/react-query';
import { fetchCustomerLedger, fetchJournals, fetchTrialBalance } from './api';

export function useTrialBalance(enabled = true) {
  return useQuery({
    queryKey: ['accounting', 'trial-balance'],
    queryFn: fetchTrialBalance,
    enabled,
  });
}

export function useJournals(offset = 0, enabled = true) {
  return useQuery({
    queryKey: ['accounting', 'journals', offset],
    queryFn: () => fetchJournals(25, offset),
    enabled,
  });
}

export function useCustomerLedger(customerId: string | null) {
  return useQuery({
    queryKey: ['accounting', 'ledger', customerId],
    queryFn: () => fetchCustomerLedger(customerId as string),
    enabled: Boolean(customerId),
  });
}
