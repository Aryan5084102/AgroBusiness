'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchSuppliers } from '@/features/suppliers/api';
import { createGoodsReceipt, type GoodsReceiptInput } from './api';

export function useSupplierOptions() {
  return useQuery({ queryKey: ['suppliers'], queryFn: fetchSuppliers });
}

export function useCreateGoodsReceipt() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: GoodsReceiptInput) => createGoodsReceipt(input),
    onSuccess: () => {
      // A receipt adds stock, so every stock-derived view is now stale.
      queryClient.invalidateQueries({ queryKey: ['products'] });
      queryClient.invalidateQueries({ queryKey: ['inventory'] });
      queryClient.invalidateQueries({ queryKey: ['purchases'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}
