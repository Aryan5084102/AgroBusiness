'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  fetchOutstanding,
  fetchPayments,
  fetchReceivables,
  receivePayment,
  type ReceivePaymentInput,
} from './api';

export function useOutstanding(customerId: string | null) {
  return useQuery({
    queryKey: ['outstanding', customerId],
    queryFn: () => fetchOutstanding(customerId as string),
    enabled: Boolean(customerId),
  });
}

export function useReceivables(enabled = true) {
  return useQuery({
    queryKey: ['collections', 'receivables'],
    queryFn: fetchReceivables,
    enabled,
  });
}

export function usePaymentHistory(
  params: { customerId?: string; limit?: number; offset?: number },
  enabled = true,
) {
  return useQuery({
    queryKey: ['collections', 'payments', params],
    queryFn: () => fetchPayments(params),
    enabled,
  });
}

export function useReceivePayment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: ReceivePaymentInput) => receivePayment(input),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['outstanding', variables.customerId] });
      queryClient.invalidateQueries({ queryKey: ['collections'] });
      queryClient.invalidateQueries({ queryKey: ['customers'] });
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
      queryClient.invalidateQueries({ queryKey: ['accounting'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}
