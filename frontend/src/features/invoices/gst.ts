// GST presentation maths shared by the on-screen bill and the downloaded PDF.
// Both documents are the same invoice, so they must split and group tax
// identically — keeping this in one place is what guarantees that.
import type { InvoiceItem } from './api';

/**
 * Halve a GST amount into CGST and SGST.
 *
 * The backend stores one `tax_amount` per line; an intra-state supply is
 * presented as an equal CGST/SGST pair. The remainder from an odd paise value
 * goes to SGST so the two halves always add back to the stored total — a bill
 * whose parts do not sum to its own tax line is worse than useless.
 */
export function splitGst(tax: number): { cgst: number; sgst: number } {
  const cgst = Math.round((tax / 2) * 100) / 100;
  return { cgst, sgst: Math.round((tax - cgst) * 100) / 100 };
}

export interface RateGroup {
  rate: string;
  taxable: number;
  cgst: number;
  sgst: number;
}

/** Rate-wise tax summary, the block a GST invoice is expected to carry. */
export function summariseByRate(items: InvoiceItem[]): RateGroup[] {
  const byRate = new Map<string, { taxable: number; tax: number }>();
  for (const item of items) {
    const key = item.gst_rate;
    const bucket = byRate.get(key) ?? { taxable: 0, tax: 0 };
    bucket.taxable += Number(item.taxable_value);
    bucket.tax += Number(item.tax_amount);
    byRate.set(key, bucket);
  }
  return [...byRate.entries()]
    .sort((a, b) => Number(a[0]) - Number(b[0]))
    .map(([rate, bucket]) => {
      const { cgst, sgst } = splitGst(bucket.tax);
      return { rate, taxable: bucket.taxable, cgst, sgst };
    });
}

export const PAYMENT_LABELS: Record<string, string> = {
  cash: 'Cash',
  upi: 'UPI',
  card: 'Card',
  cheque: 'Cheque',
  bank_transfer: 'Bank transfer',
  credit: 'On credit',
};

/** "Cash ₹120.00 (UPI-88231)" — the payment strip both bills print. */
export function describePayments(
  payments: { method: string; amount: string; reference: string | null }[],
  money: (amount: string) => string,
): string {
  return payments
    .map((payment) => {
      const label = PAYMENT_LABELS[payment.method] ?? payment.method;
      const amount = money(payment.amount);
      return payment.reference
        ? `${label} ${amount} (${payment.reference})`
        : `${label} ${amount}`;
    })
    .join(' · ');
}
