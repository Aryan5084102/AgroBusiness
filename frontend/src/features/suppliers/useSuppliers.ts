'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { createSupplier, fetchSuppliers, type CreateSupplierInput } from './api';

const KEY = ['suppliers'];

export function useSuppliers() {
  return useQuery({ queryKey: KEY, queryFn: fetchSuppliers });
}

export function useCreateSupplier() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateSupplierInput) => createSupplier(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEY }),
  });
}
