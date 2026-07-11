'use client';

import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { fetchProducts, type ProductQuery } from './api';

export function useProducts(query: ProductQuery) {
  return useQuery({
    queryKey: ['products', query],
    queryFn: () => fetchProducts(query),
    placeholderData: keepPreviousData,
  });
}
