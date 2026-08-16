'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  dispatchOrder,
  fetchInvoice,
  fetchInvoices,
  fetchOrder,
  fetchOrders,
  fetchReceipt,
  fetchReceipts,
  type InvoiceQuery,
  type OrderStatus,
} from './api';

export function useInvoices(params: InvoiceQuery, enabled = true) {
  return useQuery({
    queryKey: ['invoices', params],
    queryFn: () => fetchInvoices(params),
    enabled,
  });
}

export function useInvoice(invoiceId: string | null) {
  return useQuery({
    queryKey: ['invoice', invoiceId],
    queryFn: () => fetchInvoice(invoiceId as string),
    enabled: Boolean(invoiceId),
  });
}

export function useOrders(
  params: { status?: OrderStatus; search?: string; limit?: number; offset?: number },
  enabled = true,
) {
  return useQuery({
    queryKey: ['wholesale', 'orders', params],
    queryFn: () => fetchOrders(params),
    enabled,
  });
}

export function useOrder(orderId: string | null) {
  return useQuery({
    queryKey: ['wholesale', 'order', orderId],
    queryFn: () => fetchOrder(orderId as string),
    enabled: Boolean(orderId),
  });
}

export function useDispatchOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (orderId: string) => dispatchOrder(orderId),
    onSuccess: () => {
      // Dispatch moves stock and creates an invoice — refresh everything downstream.
      queryClient.invalidateQueries({ queryKey: ['wholesale'] });
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
      queryClient.invalidateQueries({ queryKey: ['inventory'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['customers'] });
    },
  });
}

export function useReceipts(
  params: { search?: string; limit?: number; offset?: number },
  enabled = true,
) {
  return useQuery({
    queryKey: ['purchases', 'receipts', params],
    queryFn: () => fetchReceipts(params),
    enabled,
  });
}

export function useReceipt(receiptId: string | null) {
  return useQuery({
    queryKey: ['purchases', 'receipt', receiptId],
    queryFn: () => fetchReceipt(receiptId as string),
    enabled: Boolean(receiptId),
  });
}
