'use client';

import { useMemo } from 'react';
import { amountInWords } from '@/lib/formatting/amountInWords';
import { formatCurrency } from '@/lib/formatting/currency';
import { formatDate, formatQuantity } from '@/lib/formatting/dates';
import type { InvoiceDetail } from './api';
import { describePayments, splitGst, summariseByRate } from './gst';
import styles from './InvoiceBill.module.scss';

export interface BillSeller {
  name: string;
  legal_name: string | null;
  gstin: string | null;
  address: string | null;
}

interface InvoiceBillProps {
  invoice: InvoiceDetail;
  seller: BillSeller | null;
}

/**
 * The printable tax invoice — the document a customer takes home.
 *
 * Laid out for A4 and styled to survive the browser's print pipeline (no
 * shadows, no background-dependent contrast), so "Save as PDF" produces the
 * same thing that appears on screen.
 */
export function InvoiceBill({ invoice, seller }: InvoiceBillProps) {
  const rateGroups = useMemo(() => summariseByRate(invoice.items), [invoice.items]);
  const totalTax = splitGst(Number(invoice.tax_total));
  const outstanding = Number(invoice.outstanding);
  const discount = Number(invoice.discount_total);

  const sellerName = seller?.name ?? 'AgriFlow';
  const buyerName = invoice.customer_name ?? 'Walk-in customer';
  // Address first, then the village the counter knows them by, then a number
  // to call. Anything unrecorded simply drops out rather than printing a blank.
  const buyerLines = [
    invoice.customer_address,
    invoice.customer_village,
    invoice.customer_phone,
  ].filter(Boolean);

  return (
    <article className={styles.bill} aria-label={`Tax invoice ${invoice.invoice_number}`}>
      <header className={styles.masthead}>
        <div className={styles.seller}>
          <p className={styles.sellerName}>{sellerName}</p>
          {seller?.legal_name && seller.legal_name !== seller.name ? (
            <p className={styles.sellerLine}>{seller.legal_name}</p>
          ) : null}
          {seller?.address ? <p className={styles.sellerLine}>{seller.address}</p> : null}
          {seller?.gstin ? (
            <p className={styles.sellerGstin}>
              GSTIN <strong>{seller.gstin}</strong>
            </p>
          ) : null}
        </div>

        <div className={styles.docMeta}>
          <p className={styles.docType}>Tax Invoice</p>
          <p className={styles.docNumber}>{invoice.invoice_number}</p>
          <dl className={styles.metaList}>
            <div>
              <dt>Date</dt>
              <dd>{formatDate(invoice.invoice_date)}</dd>
            </div>
            <div>
              <dt>Type</dt>
              <dd className={styles.capitalize}>{invoice.channel}</dd>
            </div>
            <div>
              <dt>Status</dt>
              <dd>
                <span
                  className={`${styles.status} ${
                    invoice.payment_status === 'paid'
                      ? styles.statusPaid
                      : styles.statusDue
                  }`}
                >
                  {invoice.payment_status === 'paid'
                    ? 'Paid'
                    : invoice.payment_status === 'partial'
                      ? 'Part paid'
                      : 'On credit'}
                </span>
              </dd>
            </div>
          </dl>
        </div>
      </header>

      <section className={styles.parties}>
        <div className={styles.party}>
          <p className={styles.partyLabel}>Billed to</p>
          <p className={styles.partyName}>{buyerName}</p>
          {buyerLines.map((line) => (
            <p key={line} className={styles.partyLine}>
              {line}
            </p>
          ))}
          {invoice.customer_gstin ? (
            <p className={styles.partyLine}>GSTIN {invoice.customer_gstin}</p>
          ) : null}
        </div>
        <div className={styles.party}>
          <p className={styles.partyLabel}>Supplied from</p>
          <p className={styles.partyName}>{invoice.warehouse_name}</p>
          {invoice.created_by_name ? (
            <p className={styles.partyLine}>Billed by {invoice.created_by_name}</p>
          ) : null}
        </div>
      </section>

      <table className={styles.lines}>
        <thead>
          <tr>
            <th scope="col" className={styles.colIndex}>
              #
            </th>
            <th scope="col">Item</th>
            <th scope="col" className={styles.colHsn}>
              HSN
            </th>
            <th scope="col" className={styles.num}>
              Qty
            </th>
            <th scope="col" className={styles.num}>
              Rate
            </th>
            <th scope="col" className={styles.num}>
              Taxable
            </th>
            <th scope="col" className={styles.num}>
              GST
            </th>
            <th scope="col" className={styles.num}>
              Amount
            </th>
          </tr>
        </thead>
        <tbody>
          {invoice.items.map((item, index) => (
            <tr key={`${item.product_id}-${index}`}>
              <td className={styles.colIndex}>{index + 1}</td>
              <td>
                <span className={styles.itemName}>{item.product_name}</span>
                <span className={styles.itemSku}>{item.sku}</span>
              </td>
              <td className={styles.colHsn}>{item.hsn_code ?? '—'}</td>
              <td className={styles.num}>
                {formatQuantity(item.base_quantity)}
                <span className={styles.unit}> {item.unit_code}</span>
              </td>
              <td className={styles.num}>{formatCurrency(item.unit_price)}</td>
              <td className={styles.num}>{formatCurrency(item.taxable_value)}</td>
              <td className={styles.num}>
                {formatCurrency(item.tax_amount)}
                <span className={styles.unit}> ({Number(item.gst_rate)}%)</span>
              </td>
              <td className={`${styles.num} ${styles.lineTotal}`}>
                {formatCurrency(item.line_total)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <section className={styles.summary}>
        <div className={styles.taxTable}>
          <p className={styles.blockLabel}>Tax summary</p>
          <table className={styles.rates}>
            <thead>
              <tr>
                <th scope="col">Rate</th>
                <th scope="col" className={styles.num}>
                  Taxable
                </th>
                <th scope="col" className={styles.num}>
                  CGST
                </th>
                <th scope="col" className={styles.num}>
                  SGST
                </th>
              </tr>
            </thead>
            <tbody>
              {rateGroups.map((group) => (
                <tr key={group.rate}>
                  <td>{Number(group.rate)}%</td>
                  <td className={styles.num}>{formatCurrency(group.taxable)}</td>
                  <td className={styles.num}>{formatCurrency(group.cgst)}</td>
                  <td className={styles.num}>{formatCurrency(group.sgst)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <dl className={styles.totals}>
          <div>
            <dt>Taxable value</dt>
            <dd>{formatCurrency(invoice.subtotal)}</dd>
          </div>
          {discount > 0 ? (
            <div>
              <dt>Discount</dt>
              <dd>−{formatCurrency(discount)}</dd>
            </div>
          ) : null}
          <div>
            <dt>CGST</dt>
            <dd>{formatCurrency(totalTax.cgst)}</dd>
          </div>
          <div>
            <dt>SGST</dt>
            <dd>{formatCurrency(totalTax.sgst)}</dd>
          </div>
          <div className={styles.grand}>
            <dt>Total</dt>
            <dd>{formatCurrency(invoice.grand_total)}</dd>
          </div>
          <div>
            <dt>Paid</dt>
            <dd>{formatCurrency(invoice.paid_amount)}</dd>
          </div>
          {outstanding > 0 ? (
            <div className={styles.due}>
              <dt>Balance due</dt>
              <dd>{formatCurrency(outstanding)}</dd>
            </div>
          ) : null}
        </dl>
      </section>

      <p className={styles.words}>
        <span className={styles.blockLabel}>Amount in words</span>
        <span className={styles.wordsValue}>{amountInWords(invoice.grand_total)}</span>
      </p>

      {invoice.payments.length > 0 ? (
        <p className={styles.paidBy}>
          <span className={styles.paidByLabel}>Paid by</span>
          {describePayments(invoice.payments, formatCurrency)}
        </p>
      ) : null}

      <footer className={styles.foot}>
        <p className={styles.terms}>
          Goods once sold are taken back only as per shop policy. Seeds, fertilizers and
          pesticides must be stored as labelled and used before their expiry date.
        </p>
        <div className={styles.sign}>
          <p className={styles.signFor}>For {sellerName}</p>
          <p className={styles.signLine}>Authorised signatory</p>
        </div>
      </footer>
    </article>
  );
}
