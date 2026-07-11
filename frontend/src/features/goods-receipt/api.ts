// Goods-receipt feature API.
import { apiFetch } from '@/lib/api/client';

export interface ReceiptLineInput {
  product_id: string;
  received_base_quantity: string;
  unit_rate: string;
  batch_number?: string;
  expiry_date?: string;
}

export interface GoodsReceiptInput {
  warehouseId: string;
  supplierId: string;
  freight: string;
  lines: ReceiptLineInput[];
}

export interface GoodsReceiptResult {
  goods_receipt_id: string;
  grn_number: string;
  landed_unit_costs: { product_id: string; landed_unit_cost: string }[];
}

export function createGoodsReceipt(
  input: GoodsReceiptInput,
): Promise<GoodsReceiptResult> {
  return apiFetch<GoodsReceiptResult>('/api/v1/purchases/goods-receipts', {
    method: 'POST',
    body: {
      warehouse_id: input.warehouseId,
      supplier_id: input.supplierId,
      freight: input.freight || '0',
      lines: input.lines,
    },
  });
}
