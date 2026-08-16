// Products feature API.
import { apiFetch } from '@/lib/api/client';

export interface Product {
  id: string;
  name: string;
  sku: string;
  barcode: string | null;
  category_id: string;
  category_name: string | null;
  base_unit_id: string;
  unit_code: string | null;
  hsn_code: string | null;
  retail_price: string;
  wholesale_price: string;
  mrp: string;
  gst_rate: string;
  min_stock: string;
  on_hand: string;
  tracks_batches: boolean;
  tracks_expiry: boolean;
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
  categoryId?: string;
  activeOnly?: boolean;
  limit?: number;
  offset?: number;
}

export interface Category {
  id: string;
  name: string;
  code: string;
  kind: string;
}

export interface Unit {
  id: string;
  code: string;
  name: string;
}

export function fetchProducts(query: ProductQuery = {}): Promise<ProductPage> {
  const params = new URLSearchParams();
  if (query.search) params.set('search', query.search);
  if (query.categoryId) params.set('category_id', query.categoryId);
  if (query.activeOnly) params.set('active_only', 'true');
  params.set('limit', String(query.limit ?? 25));
  params.set('offset', String(query.offset ?? 0));
  return apiFetch<ProductPage>(`/api/v1/products?${params.toString()}`);
}

export function fetchCategories(): Promise<Category[]> {
  return apiFetch<Category[]>('/api/v1/products/categories');
}

export function fetchUnits(): Promise<Unit[]> {
  return apiFetch<Unit[]>('/api/v1/products/units');
}

export interface CreateProductInput {
  name: string;
  sku: string;
  category_id: string;
  base_unit_id: string;
  barcode?: string | null;
  hsn_code?: string | null;
  retail_price: string;
  wholesale_price: string;
  mrp: string;
  gst_rate: string;
  min_stock: string;
  tracks_batches: boolean;
  tracks_expiry: boolean;
}

export function createProduct(input: CreateProductInput): Promise<Product> {
  return apiFetch<Product>('/api/v1/products', { method: 'POST', body: input });
}

export interface UpdateProductInput {
  name?: string;
  barcode?: string | null;
  hsn_code?: string | null;
  retail_price?: string;
  wholesale_price?: string;
  mrp?: string;
  gst_rate?: string;
  min_stock?: string;
  is_active?: boolean;
}

export function updateProduct(
  productId: string,
  input: UpdateProductInput,
): Promise<Product> {
  return apiFetch<Product>(`/api/v1/products/${productId}`, {
    method: 'PATCH',
    body: input,
  });
}
