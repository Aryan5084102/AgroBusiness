// Inventory feature API: stock levels, ledger, batches, adjustments, transfers.
import { apiFetch } from '@/lib/api/client';

export interface StockRow {
  product_id: string;
  product_name: string;
  sku: string;
  unit_code: string;
  warehouse_id: string;
  warehouse_name: string;
  on_hand: string;
  reserved: string;
  available: string;
  min_stock: string;
  is_low: boolean;
}

export interface StockPage {
  items: StockRow[];
  total: number;
  limit: number;
  offset: number;
}

export type MovementType =
  | 'opening'
  | 'purchase_receipt'
  | 'retail_sale'
  | 'wholesale_sale'
  | 'sales_return'
  | 'purchase_return'
  | 'transfer_out'
  | 'transfer_in'
  | 'damage'
  | 'expiry'
  | 'adjustment'
  | 'repair_consumption'
  | 'repair_return'
  | 'reconciliation';

export interface Movement {
  id: string;
  created_at: string;
  movement_type: MovementType;
  product_id: string;
  product_name: string;
  sku: string;
  warehouse_id: string;
  warehouse_name: string;
  base_quantity: string;
  batch_number: string | null;
  reason: string | null;
  source_document_type: string | null;
  actor_name: string | null;
}

export interface MovementPage {
  items: Movement[];
  total: number;
  limit: number;
  offset: number;
}

export interface BatchRow {
  batch_id: string;
  batch_number: string;
  product_id: string;
  product_name: string;
  warehouse_id: string;
  warehouse_name: string;
  expiry_date: string | null;
  days_to_expiry: number | null;
  on_hand: string;
  reserved: string;
  available: string;
  is_expired: boolean;
}

export interface StockQuery {
  warehouseId?: string;
  search?: string;
  lowOnly?: boolean;
  limit?: number;
  offset?: number;
}

function query(params: Record<string, string | number | boolean | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') search.set(key, String(value));
  }
  const encoded = search.toString();
  return encoded ? `?${encoded}` : '';
}

export function fetchStock(params: StockQuery): Promise<StockPage> {
  return apiFetch<StockPage>(
    `/api/v1/inventory/stock${query({
      warehouse_id: params.warehouseId,
      search: params.search,
      low_only: params.lowOnly,
      limit: params.limit ?? 50,
      offset: params.offset ?? 0,
    })}`,
  );
}

export interface MovementQuery {
  productId?: string;
  warehouseId?: string;
  movementType?: MovementType;
  limit?: number;
  offset?: number;
}

export function fetchMovements(params: MovementQuery): Promise<MovementPage> {
  return apiFetch<MovementPage>(
    `/api/v1/inventory/movements${query({
      product_id: params.productId,
      warehouse_id: params.warehouseId,
      movement_type: params.movementType,
      limit: params.limit ?? 50,
      offset: params.offset ?? 0,
    })}`,
  );
}

export function fetchBatches(params: {
  warehouseId?: string;
  expiringWithinDays?: number;
}): Promise<BatchRow[]> {
  return apiFetch<BatchRow[]>(
    `/api/v1/inventory/batches${query({
      warehouse_id: params.warehouseId,
      expiring_within_days: params.expiringWithinDays,
    })}`,
  );
}

export interface AdjustmentInput {
  warehouseId: string;
  productId: string;
  signedQuantity: string;
  reason: string;
  movementType: 'adjustment' | 'damage' | 'expiry' | 'reconciliation';
}

export function createAdjustment(input: AdjustmentInput): Promise<{
  movement_id: string;
  applied_quantity: string;
}> {
  return apiFetch('/api/v1/inventory/adjustments', {
    method: 'POST',
    body: {
      warehouse_id: input.warehouseId,
      product_id: input.productId,
      signed_quantity: input.signedQuantity,
      reason: input.reason,
      movement_type: input.movementType,
    },
  });
}

export interface TransferInput {
  fromWarehouseId: string;
  toWarehouseId: string;
  productId: string;
  baseQuantity: string;
}

export function createTransfer(input: TransferInput): Promise<{ transferred: string }> {
  return apiFetch('/api/v1/inventory/transfers', {
    method: 'POST',
    body: {
      from_warehouse_id: input.fromWarehouseId,
      to_warehouse_id: input.toWarehouseId,
      product_id: input.productId,
      base_quantity: input.baseQuantity,
    },
  });
}
