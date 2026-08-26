// Renders a finalized invoice as a downloadable A4 tax invoice PDF.
//
// The counter needs the customer's bill in their hand the moment the payment is
// taken, so this draws the document client-side from the invoice the API just
// returned rather than routing the sale through a print dialog.
//
// It is the same document as `InvoiceBill.tsx` — the shared helpers in `gst.ts`
// keep the tax split and the payment strip identical in both.
import { amountInWords } from '@/lib/formatting/amountInWords';
import { formatDate } from '@/lib/formatting/dates';
import { PdfDocument, wrapText } from '@/lib/pdf/pdfDocument';
import type { InvoiceDetail } from './api';
import type { BillSeller } from './InvoiceBill';
import { describePayments, splitGst, summariseByRate } from './gst';

const LEFT = 36;
const RIGHT = 559.28;
/** Rows stop here; the footer strip owns everything below. */
const BODY_BOTTOM = 742;

// Right edge of every numeric column, plus the left edge of the two text ones.
const COL = {
  index: LEFT + 4,
  item: LEFT + 18,
  itemWidth: 155,
  hsn: 228,
  qty: 320,
  rate: 380,
  taxable: 440,
  gstRate: 466,
  gst: 508,
  amount: RIGHT - 4,
} as const;

// Plain grouped digits, not `formatCurrency`: the base-14 fonts have no ₹
// glyph, so the columns are headed "INR" once and the rows stay uncluttered.
const decimal = new Intl.NumberFormat('en-IN', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function money(amount: string | number): string {
  const value = typeof amount === 'string' ? Number(amount) : amount;
  return Number.isFinite(value) ? decimal.format(value) : '-';
}

function rupees(amount: string | number): string {
  return `Rs. ${money(amount)}`;
}

function quantity(value: string): string {
  const numeric = Number(value);
  return Number.isFinite(numeric)
    ? numeric.toLocaleString('en-IN', { maximumFractionDigits: 3 })
    : value;
}

const STATUS_LABELS: Record<string, string> = {
  paid: 'Paid',
  partial: 'Part paid',
  credit: 'On credit',
};

/** Header band above the item rows, repeated at the top of every page. */
function drawTableHead(doc: PdfDocument, y: number): number {
  doc.rect(LEFT, y, RIGHT - LEFT, 17, { fill: 0.93 });
  const opts = { font: 'bold', size: 7, gray: 0.3 } as const;
  const baseline = y + 5;
  doc.text('#', COL.index, baseline, opts);
  doc.text('ITEM', COL.item, baseline, opts);
  doc.text('HSN', COL.hsn, baseline, opts);
  doc.text('QTY', COL.qty, baseline, { ...opts, align: 'right' });
  doc.text('RATE', COL.rate, baseline, { ...opts, align: 'right' });
  doc.text('TAXABLE', COL.taxable, baseline, { ...opts, align: 'right' });
  doc.text('GST%', COL.gstRate, baseline, { ...opts, align: 'right' });
  doc.text('GST', COL.gst, baseline, { ...opts, align: 'right' });
  doc.text('AMOUNT', COL.amount, baseline, { ...opts, align: 'right' });
  return y + 17;
}

function drawMasthead(
  doc: PdfDocument,
  invoice: InvoiceDetail,
  seller: BillSeller | null,
): number {
  const sellerName = seller?.name ?? 'AgriFlow';
  doc.text(sellerName, LEFT, 38, { font: 'bold', size: 15 });

  let y = 58;
  if (seller?.legal_name && seller.legal_name !== seller.name) {
    doc.text(seller.legal_name, LEFT, y, { size: 8.5, gray: 0.35 });
    y += 11;
  }
  for (const line of wrapText(seller?.address ?? '', 'regular', 8.5, 250)) {
    doc.text(line, LEFT, y, { size: 8.5, gray: 0.35 });
    y += 11;
  }
  if (seller?.gstin) {
    doc.text(`GSTIN ${seller.gstin}`, LEFT, y, { font: 'bold', size: 8.5, gray: 0.2 });
    y += 11;
  }

  doc.text('TAX INVOICE', RIGHT, 38, { font: 'bold', size: 13, align: 'right' });
  doc.text(invoice.invoice_number, RIGHT, 57, { font: 'bold', size: 11, align: 'right' });

  const meta: [string, string][] = [
    ['Date', formatDate(invoice.invoice_date)],
    ['Type', invoice.channel === 'wholesale' ? 'Wholesale' : 'Retail'],
    ['Status', STATUS_LABELS[invoice.payment_status] ?? invoice.payment_status],
  ];
  let metaY = 75;
  for (const [label, value] of meta) {
    doc.text(label, RIGHT - 108, metaY, { size: 8.5, gray: 0.45 });
    doc.text(value, RIGHT, metaY, { font: 'bold', size: 8.5, align: 'right' });
    metaY += 12;
  }

  const bottom = Math.max(y, metaY) + 4;
  doc.line(LEFT, bottom, RIGHT, bottom, { width: 1, gray: 0.45 });
  return bottom;
}

function drawParties(doc: PdfDocument, invoice: InvoiceDetail, top: number): number {
  const columns: { x: number; label: string; name: string; lines: string[] }[] = [
    {
      x: LEFT,
      label: 'BILLED TO',
      name: invoice.customer_name ?? 'Walk-in customer',
      // Phone first: it is what the counter identifies a returning customer by.
      lines: [
        invoice.customer_phone ? `Mobile ${invoice.customer_phone}` : '',
        ...wrapText(invoice.customer_address ?? '', 'regular', 8.5, 230),
        invoice.customer_village ?? '',
        invoice.customer_gstin ? `GSTIN ${invoice.customer_gstin}` : '',
      ].filter(Boolean),
    },
    {
      x: LEFT + 280,
      label: 'SUPPLIED FROM',
      name: invoice.warehouse_name,
      lines: [
        invoice.created_by_name ? `Billed by ${invoice.created_by_name}` : '',
      ].filter(Boolean),
    },
  ];

  let deepest = top;
  for (const column of columns) {
    doc.text(column.label, column.x, top + 12, { font: 'bold', size: 7, gray: 0.45 });
    doc.text(column.name, column.x, top + 25, { font: 'bold', size: 10.5 });
    let y = top + 41;
    for (const line of column.lines) {
      doc.text(line, column.x, y, { size: 8.5, gray: 0.3 });
      y += 11;
    }
    deepest = Math.max(deepest, y);
  }
  return deepest + 6;
}

function drawItems(doc: PdfDocument, invoice: InvoiceDetail, top: number): number {
  let y = drawTableHead(doc, top);

  invoice.items.forEach((item, index) => {
    if (y + 21 > BODY_BOTTOM) {
      doc.addPage();
      y = drawTableHead(doc, 40);
    }
    // Two lines is all a row can spare; a name longer than that is elided
    // rather than silently cut, so nobody reads a truncated product as whole.
    const wrapped = wrapText(item.product_name, 'bold', 8.5, COL.itemWidth);
    const nameLines = wrapped.slice(0, 2);
    if (wrapped.length > 2 && nameLines[1]) nameLines[1] = `${nameLines[1]}...`;
    const height = nameLines.length > 1 ? 32 : 21;

    doc.text(String(index + 1), COL.index, y + 5, { size: 8, gray: 0.45 });
    nameLines.forEach((line, lineIndex) => {
      doc.text(line, COL.item, y + 4 + lineIndex * 10, { font: 'bold', size: 8.5 });
    });
    doc.text(item.sku, COL.item, y + 4 + nameLines.length * 10, { size: 7, gray: 0.5 });
    doc.text(item.hsn_code ?? '-', COL.hsn, y + 5, { size: 8, gray: 0.35 });
    doc.text(`${quantity(item.base_quantity)} ${item.unit_code}`, COL.qty, y + 5, {
      size: 8,
      align: 'right',
    });
    doc.text(money(item.unit_price), COL.rate, y + 5, { size: 8, align: 'right' });
    doc.text(money(item.taxable_value), COL.taxable, y + 5, { size: 8, align: 'right' });
    doc.text(`${Number(item.gst_rate)}%`, COL.gstRate, y + 5, {
      size: 8,
      align: 'right',
    });
    doc.text(money(item.tax_amount), COL.gst, y + 5, { size: 8, align: 'right' });
    doc.text(money(item.line_total), COL.amount, y + 5, {
      font: 'bold',
      size: 8.5,
      align: 'right',
    });

    y += height;
    doc.line(LEFT, y, RIGHT, y, { gray: 0.85 });
  });

  return y;
}

function drawSummary(doc: PdfDocument, invoice: InvoiceDetail, top: number): number {
  const groups = summariseByRate(invoice.items);
  const totalTax = splitGst(Number(invoice.tax_total));
  const discount = Number(invoice.discount_total);
  const outstanding = Number(invoice.outstanding);

  const totals: [string, string][] = [
    ['Taxable value', money(invoice.subtotal)],
    ...(discount > 0
      ? ([['Discount', `- ${money(discount)}`]] as [string, string][])
      : []),
    ['CGST', money(totalTax.cgst)],
    ['SGST', money(totalTax.sgst)],
  ];

  // Both halves are drawn from the same top edge; the taller one sets the
  // block height so the amount-in-words line never lands on top of either.
  let leftY = top + 16;
  doc.text('TAX SUMMARY', LEFT, leftY, { font: 'bold', size: 7, gray: 0.45 });
  leftY += 14;
  const head = { font: 'bold', size: 7, gray: 0.4 } as const;
  doc.text('RATE', LEFT, leftY, head);
  doc.text('TAXABLE', 160, leftY, { ...head, align: 'right' });
  doc.text('CGST', 240, leftY, { ...head, align: 'right' });
  doc.text('SGST', 316, leftY, { ...head, align: 'right' });
  leftY += 10;
  doc.line(LEFT, leftY, 316, leftY, { gray: 0.85 });
  for (const group of groups) {
    leftY += 12;
    doc.text(`${Number(group.rate)}%`, LEFT, leftY, { size: 8 });
    doc.text(money(group.taxable), 160, leftY, { size: 8, align: 'right' });
    doc.text(money(group.cgst), 240, leftY, { size: 8, align: 'right' });
    doc.text(money(group.sgst), 316, leftY, { size: 8, align: 'right' });
  }
  leftY += 12;

  let rightY = top + 16;
  for (const [label, value] of totals) {
    doc.text(label, 360, rightY, { size: 8.5, gray: 0.35 });
    doc.text(value, RIGHT, rightY, { size: 8.5, align: 'right' });
    rightY += 13;
  }
  doc.line(360, rightY, RIGHT, rightY, { gray: 0.5 });
  rightY += 6;
  doc.text('TOTAL', 360, rightY, { font: 'bold', size: 11 });
  doc.text(rupees(invoice.grand_total), RIGHT, rightY, {
    font: 'bold',
    size: 11,
    align: 'right',
  });
  rightY += 18;
  doc.text('Paid', 360, rightY, { size: 8.5, gray: 0.35 });
  doc.text(money(invoice.paid_amount), RIGHT, rightY, { size: 8.5, align: 'right' });
  rightY += 13;
  if (outstanding > 0) {
    doc.text('Balance due', 360, rightY, { font: 'bold', size: 9 });
    doc.text(rupees(outstanding), RIGHT, rightY, {
      font: 'bold',
      size: 9,
      align: 'right',
    });
    rightY += 13;
  }

  return Math.max(leftY, rightY);
}

function drawClosing(
  doc: PdfDocument,
  invoice: InvoiceDetail,
  seller: BillSeller | null,
  top: number,
): void {
  const sellerName = seller?.name ?? 'AgriFlow';
  let y = top + 10;

  doc.rect(LEFT, y, RIGHT - LEFT, 26, { fill: 0.96 });
  doc.text('AMOUNT IN WORDS', LEFT + 8, y + 6, { font: 'bold', size: 6.5, gray: 0.45 });
  doc.text(amountInWords(invoice.grand_total), LEFT + 8, y + 15, { size: 8.5 });
  y += 34;

  if (invoice.payments.length > 0) {
    doc.text('Paid by', LEFT, y, { font: 'bold', size: 8, gray: 0.45 });
    doc.text(describePayments(invoice.payments, money), LEFT + 42, y, { size: 8.5 });
    y += 16;
  }

  for (const line of wrapText(
    'Goods once sold are taken back only as per shop policy. Seeds, fertilizers and pesticides must be stored as labelled and used before their expiry date.',
    'regular',
    7.5,
    300,
  )) {
    doc.text(line, LEFT, y, { size: 7.5, gray: 0.45 });
    y += 10;
  }

  const signTop = Math.max(y, top + 74);
  doc.text(`For ${sellerName}`, RIGHT, signTop, {
    font: 'bold',
    size: 8.5,
    align: 'right',
  });
  doc.line(RIGHT - 150, signTop + 34, RIGHT, signTop + 34, { gray: 0.5 });
  doc.text('Authorised signatory', RIGHT, signTop + 40, {
    size: 7.5,
    gray: 0.45,
    align: 'right',
  });
}

/** Builds the printable tax invoice. Pure — safe to call in a test. */
export function buildInvoicePdf(
  invoice: InvoiceDetail,
  seller: BillSeller | null,
): Uint8Array<ArrayBuffer> {
  const doc = new PdfDocument();

  const afterMasthead = drawMasthead(doc, invoice, seller);
  const afterParties = drawParties(doc, invoice, afterMasthead);
  let y = drawItems(doc, invoice, afterParties + 6);

  // The summary and the signature belong together; push both to a fresh page
  // rather than let a page break fall between the total and who signed for it.
  const closingHeight = 150 + summariseByRate(invoice.items).length * 12;
  if (y + closingHeight > BODY_BOTTOM) {
    doc.addPage();
    y = 40;
  }
  drawClosing(doc, invoice, seller, drawSummary(doc, invoice, y));

  doc.stampPages((sheet, page, total) => {
    const note = total > 1 ? `Page ${page} of ${total}` : 'Computer-generated invoice';
    sheet.line(LEFT, 790, RIGHT, 790, { gray: 0.85 });
    sheet.text(invoice.invoice_number, LEFT, 796, { size: 7, gray: 0.5 });
    sheet.text(note, RIGHT, 796, { size: 7, gray: 0.5, align: 'right' });
  });

  return doc.toBytes();
}

/** Filenames must survive a file system: keep letters, digits, dot and dash. */
function safeFileName(invoiceNumber: string): string {
  const base = invoiceNumber.replace(/[^A-Za-z0-9._-]+/g, '-').replace(/^-+|-+$/g, '');
  return `${base || 'invoice'}.pdf`;
}

/**
 * Hands the browser the finished bill as a download.
 *
 * Returns false when the document could not be produced or the browser refused
 * the download, so the caller can fall back to the printable bill page instead
 * of telling the counter a file arrived when none did.
 */
export function downloadInvoicePdf(
  invoice: InvoiceDetail,
  seller: BillSeller | null,
): boolean {
  if (typeof window === 'undefined') return false;
  try {
    const pdf = new Blob([buildInvoicePdf(invoice, seller)], {
      type: 'application/pdf',
    });
    const url = URL.createObjectURL(pdf);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = safeFileName(invoice.invoice_number);
    anchor.rel = 'noopener';
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    // Revoking immediately can cancel the download in some browsers; one turn
    // of the event loop is enough for the fetch of the blob to have started.
    window.setTimeout(() => URL.revokeObjectURL(url), 30_000);
    return true;
  } catch {
    return false;
  }
}
