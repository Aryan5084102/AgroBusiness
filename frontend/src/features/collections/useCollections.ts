'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchOutstanding, receivePayment, type ReceivePaymentInput } from './api';

export function useOutstanding(customerId: string | null) {
  return useQuery({
    queryKey: ['outstanding', customerId],
    queryFn: () => fetchOutstanding(customerId as string),
    enabled: Boolean(customerId),
  });
}

export function useReceivePayment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: ReceivePaymentInput) => receivePayment(input),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['outstanding', variables.customerId] });
      queryClient.invalidateQueries({ queryKey: ['customers'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}
