'use client';

import { useRouter } from 'next/navigation';
import { useEffect } from 'react';
import { Button } from '@/components/ui/Button';
import { QueryState } from '@/components/feedback/QueryState';
import { useOrgProfile } from '@/features/settings/useSettings';
import { InvoiceBill } from './InvoiceBill';
import { useInvoice } from './useInvoices';
import styles from './BillScreen.module.scss';

interface BillScreenProps {
  invoiceId: string;
}

/**
 * Standalone page for one printable bill.
 *
 * Deliberately outside `AppShell`: the sidebar and header would have to be
 * hidden for print anyway, and a bill on its own URL can be reopened, shared or
 * reprinted long after the sale. The toolbar carries `.no-print`, so what the
 * printer receives is exactly the document and nothing else.
 */
export function BillScreen({ invoiceId }: BillScreenProps) {
  const router = useRouter();
  const invoice = useInvoice(invoiceId);
  const org = useOrgProfile();
  const invoiceNumber = invoice.data?.invoice_number;

  // Browsers name the "Save as PDF" file after the document title, so a bill
  // saves as MAIN-INV-00016.pdf rather than the app's title.
  useEffect(() => {
    if (!invoiceNumber) return;
    const previous = document.title;
    document.title = invoiceNumber;
    return () => {
      document.title = previous;
    };
  }, [invoiceNumber]);

  return (
    <div className={styles.page}>
      <div className={`${styles.toolbar} no-print`}>
        <Button variant="ghost" icon="chevronLeft" onClick={() => router.back()}>
          Back
        </Button>
        <div className={styles.actions}>
          <Button
            variant="secondary"
            icon="download"
            onClick={() => window.print()}
            disabled={!invoice.data}
          >
            Download PDF
          </Button>
          <Button
            variant="primary"
            icon="print"
            onClick={() => window.print()}
            disabled={!invoice.data}
          >
            Print
          </Button>
        </div>
      </div>

      <div className={styles.sheet}>
        <QueryState
          isLoading={invoice.isLoading}
          error={invoice.error}
          onRetry={invoice.refetch}
          loadingHeight={420}
        >
          {invoice.data ? (
            <InvoiceBill invoice={invoice.data} seller={org.data ?? null} />
          ) : null}
        </QueryState>
      </div>

      <p className={`${styles.hint} no-print`}>
        Both buttons open your browser&apos;s print dialog — choose{' '}
        <strong>Save as PDF</strong> as the destination to download the bill.
      </p>
    </div>
  );
}
