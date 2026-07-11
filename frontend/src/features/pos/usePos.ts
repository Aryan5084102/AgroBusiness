'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  fetchQuote,
  fetchWarehouses,
  finalizeSale,
  type CartLine,
  type FinalizeInput,
} from './api';

export function useWarehouses() {
  return useQuery({ queryKey: ['warehouses'], queryFn: fetchWarehouses });
}

export function useQuote(warehouseId: string | null, lines: CartLine[]) {
  return useQuery({
    queryKey: ['pos-quote', warehouseId, lines],
    queryFn: () => fetchQuote(warehouseId as string, lines),
    enabled: Boolean(warehouseId) && lines.length > 0,
  });
}

export function useFinalizeSale() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: FinalizeInput) => finalizeSale(input),
    onSuccess: () => {
      // Stock and dashboard changed; refresh dependent views.
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['products'] });
    },
  });
}
