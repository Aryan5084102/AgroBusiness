// Products feature API.
import { apiFetch } from '@/lib/api/client';

export interface Product {
  id: string;
  name: string;
  sku: string;
  barcode: string | null;
  retail_price: string;
  wholesale_price: string;
  mrp: string;
  gst_rate: string;
  tracks_batches: boolean;
  is_active: boolean;
}

export interface ProductPage {
  items: Product[];
  total: number;
  limit: number;
  offset: number;
}

export interface ProductQuery {
  search?: string;
  limit?: number;
  offset?: number;
}

export function fetchProducts(query: ProductQuery = {}): Promise<ProductPage> {
  const params = new URLSearchParams();
  if (query.search) params.set('search', query.search);
  params.set('limit', String(query.limit ?? 25));
  params.set('offset', String(query.offset ?? 0));
  return apiFetch<ProductPage>(`/api/v1/products?${params.toString()}`);
}
