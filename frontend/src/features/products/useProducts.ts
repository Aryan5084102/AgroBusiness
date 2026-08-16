'use client';

import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';
import {
  createProduct,
  fetchCategories,
  fetchProducts,
  fetchUnits,
  updateProduct,
  type CreateProductInput,
  type ProductQuery,
  type UpdateProductInput,
} from './api';

export function useProducts(query: ProductQuery, enabled = true) {
  return useQuery({
    queryKey: ['products', query],
    queryFn: () => fetchProducts(query),
    placeholderData: keepPreviousData,
    enabled,
  });
}

export function useCategories(enabled = true) {
  return useQuery({
    queryKey: ['products', 'categories'],
    queryFn: fetchCategories,
    staleTime: 5 * 60_000,
    enabled,
  });
}

export function useUnits(enabled = true) {
  return useQuery({
    queryKey: ['products', 'units'],
    queryFn: fetchUnits,
    staleTime: 5 * 60_000,
    enabled,
  });
}

export function useCreateProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateProductInput) => createProduct(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['products'] }),
  });
}

export function useUpdateProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      productId,
      input,
    }: {
      productId: string;
      input: UpdateProductInput;
    }) => updateProduct(productId, input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['products'] }),
  });
}
