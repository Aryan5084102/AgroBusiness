'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { createOrder, type CreateOrderInput } from './api';

export function useCreateOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateOrderInput) => createOrder(input),
    onSuccess: () => {
      // Confirming an order reserves stock and moves the dealer's exposure.
      queryClient.invalidateQueries({ queryKey: ['customers'] });
      queryClient.invalidateQueries({ queryKey: ['wholesale'] });
      queryClient.invalidateQueries({ queryKey: ['inventory'] });
    },
  });
}
