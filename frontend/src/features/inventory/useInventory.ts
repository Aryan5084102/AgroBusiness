'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createAdjustment,
  createTransfer,
  fetchBatches,
  fetchMovements,
  fetchStock,
  type AdjustmentInput,
  type MovementQuery,
  type StockQuery,
  type TransferInput,
} from './api';

export function useStock(params: StockQuery, enabled = true) {
  return useQuery({
    queryKey: ['inventory', 'stock', params],
    queryFn: () => fetchStock(params),
    enabled,
  });
}

export function useMovements(params: MovementQuery, enabled = true) {
  return useQuery({
    queryKey: ['inventory', 'movements', params],
    queryFn: () => fetchMovements(params),
    enabled,
  });
}

export function useBatches(
  params: { warehouseId?: string; expiringWithinDays?: number },
  enabled = true,
) {
  return useQuery({
    queryKey: ['inventory', 'batches', params],
    queryFn: () => fetchBatches(params),
    enabled,
  });
}

// Stock changes ripple into products, dashboard and the ledger — refresh all.
function invalidateStock(queryClient: ReturnType<typeof useQueryClient>) {
  queryClient.invalidateQueries({ queryKey: ['inventory'] });
  queryClient.invalidateQueries({ queryKey: ['products'] });
  queryClient.invalidateQueries({ queryKey: ['dashboard'] });
}

export function useCreateAdjustment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: AdjustmentInput) => createAdjustment(input),
    onSuccess: () => invalidateStock(queryClient),
  });
}

export function useCreateTransfer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: TransferInput) => createTransfer(input),
    onSuccess: () => invalidateStock(queryClient),
  });
}
