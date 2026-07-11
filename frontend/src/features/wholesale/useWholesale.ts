'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { createOrder, dispatchOrder, type CreateOrderInput } from './api';

export function useCreateOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateOrderInput) => createOrder(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['customers'] }),
  });
}

export function useDispatchOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (orderId: string) => dispatchOrder(orderId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customers'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}
