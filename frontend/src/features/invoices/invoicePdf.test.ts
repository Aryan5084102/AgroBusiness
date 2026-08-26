import { describe, expect, it } from 'vitest';
import { sanitize, textWidth, wrapText } from '@/lib/pdf/pdfDocument';
import type { InvoiceDetail, InvoiceItem } from './api';
import { buildInvoicePdf } from './invoicePdf';
import { splitGst, summariseByRate } from './gst';

function item(overrides: Partial<InvoiceItem> = {}): InvoiceItem {
  return {
    product_id: '11111111-1111-1111-1111-111111111111',
    product_name: 'Urea 50kg Bag',
    sku: 'FERT-UREA-50',
    hsn_code: '3102',
    unit_code: 'BAG',
    base_quantity: '2',
    unit_price: '300.00',
    price_source: 'list',
    discount_amount: '0.00',
    taxable_value: '600.00',
    gst_rate: '5.00',
    tax_amount: '30.00',
    line_total: '630.00',
    ...overrides,
  };
}

function invoice(overrides: Partial<InvoiceDetail> = {}): InvoiceDetail {
  return {
    id: '22222222-2222-2222-2222-222222222222',
    invoice_number: 'MAIN-INV-00016',
    invoice_date: '2026-08-26',
    channel: 'retail',
    customer_name: 'Ramesh Patil',
    warehouse_name: 'Main Shop',
    grand_total: '630.00',
    paid_amount: '630.00',
    outstanding: '0.00',
    payment_status: 'paid',
    created_by_name: 'Counter Staff',
    subtotal: '600.00',
    discount_total: '0.00',
    tax_total: '30.00',
    customer_id: '33333333-3333-3333-3333-333333333333',
    customer_phone: '9876543210',
    customer_gstin: null,
    customer_address: 'Plot 4, Market Road',
    customer_village: 'Shirur',
    items: [item()],
    payments: [{ method: 'cash', amount: '630.00', reference: null }],
    ...overrides,
  };
}

function pdfText(bytes: Uint8Array): string {
  return new TextDecoder('latin1').decode(bytes);
}

describe('buildInvoicePdf', () => {
  it('produces a readable single-page PDF', () => {
    const raw = pdfText(buildInvoicePdf(invoice(), null));

    expect(raw.startsWith('%PDF-1.4')).toBe(true);
    expect(raw.trimEnd().endsWith('%%EOF')).toBe(true);
    expect(raw).toContain('/Type /Catalog');
    expect(raw).toContain('/Count 1');
  });

  it('carries the customer, the items and the total', () => {
    const raw = pdfText(buildInvoicePdf(invoice(), null));

    expect(raw).toContain('(Ramesh Patil)');
    expect(raw).toContain('(Mobile 9876543210)');
    expect(raw).toContain('(Plot 4, Market Road)');
    expect(raw).toContain('(Urea 50kg Bag)');
    expect(raw).toContain('(MAIN-INV-00016)');
    expect(raw).toContain('(Rs. 630.00)');
    expect(raw).toContain('(Rupees Six Hundred Thirty Only)');
  });

  it('declares the byte length its content streams actually have', () => {
    const raw = pdfText(buildInvoicePdf(invoice(), null));

    for (const match of raw.matchAll(/<< \/Length (\d+) >>\nstream\n/g)) {
      const start = (match.index ?? 0) + match[0].length;
      const declared = Number(match[1]);
      expect(raw.slice(start + declared, start + declared + 10)).toBe('\nendstream');
    }
  });

  it('spills a long bill onto more pages rather than off the first one', () => {
    const many = Array.from({ length: 60 }, (_, i) =>
      item({ product_id: `p-${i}`, sku: `SKU-${i}` }),
    );
    const raw = pdfText(buildInvoicePdf(invoice({ items: many }), null));

    expect(raw).toMatch(/\/Count [2-9]/);
    expect(raw).toContain('(Page 1 of ');
  });

  it('escapes parentheses and backslashes in a customer name', () => {
    const raw = pdfText(
      buildInvoicePdf(invoice({ customer_name: 'R. Patil (Krishi\\Seva)' }), null),
    );

    expect(raw).toContain('(R. Patil \\(Krishi\\\\Seva\\))');
  });

  it('prints the seller when the org profile is known', () => {
    const raw = pdfText(
      buildInvoicePdf(invoice(), {
        name: 'AgriFlow Demo Traders',
        legal_name: 'AgriFlow Demo Traders LLP',
        gstin: '27AAAAA0000A1Z5',
        address: 'Market Yard, Pune',
      }),
    );

    expect(raw).toContain('(AgriFlow Demo Traders)');
    expect(raw).toContain('(GSTIN 27AAAAA0000A1Z5)');
    expect(raw).toContain('(For AgriFlow Demo Traders)');
  });
});

describe('pdf text handling', () => {
  it('folds the rupee sign the base-14 fonts cannot draw', () => {
    expect(sanitize('₹1,200.00')).toBe('Rs. 1,200.00');
    expect(sanitize('Cash ₹120 · UPI ₹80')).toBe('Cash Rs. 120 - UPI Rs. 80');
  });

  it('keeps Latin-1 names and replaces what it cannot render', () => {
    expect(sanitize('José Fernández')).toBe('José Fernández');
    expect(sanitize('रमेश')).toBe('????');
  });

  it('wraps to the width it was given', () => {
    const lines = wrapText(
      'Knapsack Sprayer 16L Heavy Duty Brass Nozzle',
      'bold',
      8.5,
      80,
    );

    expect(lines.length).toBeGreaterThan(1);
    for (const line of lines)
      expect(textWidth(line, 'bold', 8.5)).toBeLessThanOrEqual(80);
  });
});

describe('gst helpers', () => {
  it('splits an odd paise tax so the halves add back to the whole', () => {
    const { cgst, sgst } = splitGst(30.01);

    expect(cgst + sgst).toBeCloseTo(30.01, 2);
  });

  it('groups lines by rate', () => {
    const groups = summariseByRate([
      item({ gst_rate: '18.00', taxable_value: '100.00', tax_amount: '18.00' }),
      item({ gst_rate: '5.00', taxable_value: '200.00', tax_amount: '10.00' }),
      item({ gst_rate: '18.00', taxable_value: '300.00', tax_amount: '54.00' }),
    ]);

    expect(groups.map((g) => g.rate)).toEqual(['5.00', '18.00']);
    expect(groups[1]?.taxable).toBe(400);
    expect(groups[1]?.cgst).toBe(36);
  });
});
