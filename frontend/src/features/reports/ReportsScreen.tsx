'use client';

import { useState } from 'react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { DataTable } from '@/components/ui/DataTable';
import { Input } from '@/components/ui/Field';
import { QueryState } from '@/components/feedback/QueryState';
import { StatCard, StatGrid } from '@/components/ui/StatCard';
import { Tabs } from '@/components/ui/Tabs';
import { Toolbar, ToolbarSpacer } from '@/components/ui/Toolbar';
import { useToast } from '@/components/ui/Toast';
import { formatCurrency, formatPercent } from '@/lib/formatting/currency';
import { formatDate, formatQuantity } from '@/lib/formatting/dates';
import { downloadRegisterCsv, type RegisterRow, type StockValuationRow } from './api';
import {
  dateRange,
  useGstSummary,
  usePurchaseRegister,
  useSalesRegister,
  useStockValuation,
} from './useReports';
import styles from './ReportsScreen.module.scss';

type Tab = 'sales' | 'purchases' | 'gst' | 'stock';

/** Filterable registers with CSV export. The date range drives every tab, so a
 * user can switch views without re-entering the period. */
export function ReportsScreen() {
  const toast = useToast();
  const initial = dateRange(30);
  const [tab, setTab] = useState<Tab>('sales');
  const [from, setFrom] = useState(initial.from);
  const [to, setTo] = useState(initial.to);
  const [exporting, setExporting] = useState(false);

  const sales = useSalesRegister(from, to, tab === 'sales');
  const purchases = usePurchaseRegister(from, to, tab === 'purchases');
  const gst = useGstSummary(from, to, tab === 'gst');
  const valuation = useStockValuation(tab === 'stock');

  const exportCsv = async (register: 'sales' | 'purchases') => {
    setExporting(true);
    try {
      await downloadRegisterCsv(register, from, to);
      toast.success('Export ready', 'The CSV has been downloaded.');
    } catch {
      toast.error('Export failed', 'The register could not be generated.');
    } finally {
      setExporting(false);
    }
  };

  const dateFilters = (
    <>
      <Input
        label="From"
        type="date"
        value={from}
        max={to}
        onChange={(event) => setFrom(event.target.value)}
      />
      <Input
        label="To"
        type="date"
        value={to}
        min={from}
        onChange={(event) => setTo(event.target.value)}
      />
    </>
  );

  return (
    <>
      <Tabs<Tab>
        label="Report types"
        active={tab}
        onChange={setTab}
        items={[
          { id: 'sales', label: 'Sales register', icon: 'invoices' },
          { id: 'purchases', label: 'Purchase register', icon: 'purchases' },
          { id: 'gst', label: 'GST summary', icon: 'accounting' },
          { id: 'stock', label: 'Stock valuation', icon: 'inventory' },
        ]}
      />

      {tab === 'sales' ? (
        <Card>
          <CardHeader
            title="Sales register"
            description="Every invoice raised in the period, newest first."
            actions={
              <Button
                variant="secondary"
                size="sm"
                icon="download"
                isLoading={exporting}
                onClick={() => exportCsv('sales')}
              >
                Export CSV
              </Button>
            }
          />
          <Toolbar>
            {dateFilters}
            <ToolbarSpacer />
          </Toolbar>
          <QueryState
            isLoading={sales.isLoading}
            error={sales.error}
            onRetry={sales.refetch}
            loadingHeight={260}
          >
            <>
              <StatGrid>
                <StatCard
                  label="Taxable value"
                  value={formatCurrency(sales.data?.total_taxable ?? '0')}
                />
                <StatCard
                  label="GST"
                  value={formatCurrency(sales.data?.total_tax ?? '0')}
                />
                <StatCard
                  label="Invoiced"
                  tone="positive"
                  value={formatCurrency(sales.data?.grand_total ?? '0')}
                />
              </StatGrid>
              <DataTable<RegisterRow>
                rows={sales.data?.rows ?? []}
                rowKey={(row) => row.document_number}
                emptyTitle="No sales in this period"
                emptyDescription="Widen the date range to see more."
                columns={registerColumns}
              />
            </>
          </QueryState>
        </Card>
      ) : null}

      {tab === 'purchases' ? (
        <Card>
          <CardHeader
            title="Purchase register"
            description="Goods received from suppliers in the period."
            actions={
              <Button
                variant="secondary"
                size="sm"
                icon="download"
                isLoading={exporting}
                onClick={() => exportCsv('purchases')}
              >
                Export CSV
              </Button>
            }
          />
          <Toolbar>
            {dateFilters}
            <ToolbarSpacer />
          </Toolbar>
          <QueryState
            isLoading={purchases.isLoading}
            error={purchases.error}
            onRetry={purchases.refetch}
            loadingHeight={260}
          >
            <DataTable<RegisterRow>
              rows={purchases.data?.rows ?? []}
              rowKey={(row) => row.document_number}
              emptyTitle="No goods received in this period"
              emptyDescription="Receipts booked against suppliers appear here."
              columns={registerColumns}
            />
          </QueryState>
        </Card>
      ) : null}

      {tab === 'gst' ? (
        <Card>
          <CardHeader
            title="GST summary"
            description="Output tax grouped by rate — the basis for your return."
          />
          <Toolbar>
            {dateFilters}
            <ToolbarSpacer />
          </Toolbar>
          <QueryState
            isLoading={gst.isLoading}
            error={gst.error}
            onRetry={gst.refetch}
            loadingHeight={220}
          >
            <DataTable
              rows={gst.data?.buckets ?? []}
              rowKey={(row) => row.gst_rate}
              emptyTitle="No taxable sales in this period"
              columns={[
                {
                  key: 'rate',
                  header: 'GST rate',
                  render: (row) => (
                    <Badge tone="info">{formatPercent(row.gst_rate)}</Badge>
                  ),
                },
                {
                  key: 'taxable',
                  header: 'Taxable value',
                  numeric: true,
                  render: (row) => formatCurrency(row.taxable_value),
                },
                {
                  key: 'tax',
                  header: 'Tax',
                  numeric: true,
                  render: (row) => formatCurrency(row.tax_amount),
                },
              ]}
              footer={
                <tr>
                  <td>Total</td>
                  <td className="tabular-nums" style={{ textAlign: 'right' }}>
                    {formatCurrency(gst.data?.total_taxable ?? '0')}
                  </td>
                  <td className="tabular-nums" style={{ textAlign: 'right' }}>
                    {formatCurrency(gst.data?.total_tax ?? '0')}
                  </td>
                </tr>
              }
            />
          </QueryState>
        </Card>
      ) : null}

      {tab === 'stock' ? (
        <Card>
          <CardHeader
            title="Stock valuation"
            description="On-hand quantity valued at the current retail price."
          />
          <QueryState
            isLoading={valuation.isLoading}
            error={valuation.error}
            onRetry={valuation.refetch}
            loadingHeight={260}
          >
            <>
              <CardBody>
                <StatGrid>
                  <StatCard
                    label="Stock value"
                    tone="positive"
                    icon="warehouse"
                    value={formatCurrency(valuation.data?.total_value ?? '0')}
                    hint="At retail price across all warehouses"
                  />
                  <StatCard
                    label="Below minimum"
                    tone={
                      (valuation.data?.low_stock_count ?? 0) > 0 ? 'danger' : 'default'
                    }
                    icon="alert"
                    value={valuation.data?.low_stock_count ?? 0}
                    hint="Products needing a reorder"
                  />
                </StatGrid>
              </CardBody>
              <DataTable<StockValuationRow>
                rows={valuation.data?.rows ?? []}
                rowKey={(row) => row.product_id}
                emptyTitle="No active products"
                columns={[
                  {
                    key: 'product',
                    header: 'Product',
                    render: (row) => (
                      <span className={styles.primaryCell}>
                        <span>{row.product_name}</span>
                        <span className={styles.muted}>{row.sku}</span>
                      </span>
                    ),
                  },
                  {
                    key: 'onHand',
                    header: 'On hand',
                    numeric: true,
                    render: (row) =>
                      row.is_low ? (
                        <span className={styles.low}>{formatQuantity(row.on_hand)}</span>
                      ) : (
                        formatQuantity(row.on_hand)
                      ),
                  },
                  {
                    key: 'min',
                    header: 'Minimum',
                    numeric: true,
                    secondary: true,
                    render: (row) => formatQuantity(row.min_stock),
                  },
                  {
                    key: 'price',
                    header: 'Retail price',
                    numeric: true,
                    secondary: true,
                    render: (row) => formatCurrency(row.retail_price),
                  },
                  {
                    key: 'value',
                    header: 'Stock value',
                    numeric: true,
                    render: (row) => <strong>{formatCurrency(row.stock_value)}</strong>,
                  },
                ]}
              />
            </>
          </QueryState>
        </Card>
      ) : null}
    </>
  );
}

const registerColumns = [
  {
    key: 'date',
    header: 'Date',
    render: (row: RegisterRow) => formatDate(row.entry_date),
  },
  {
    key: 'doc',
    header: 'Document',
    render: (row: RegisterRow) => <strong>{row.document_number}</strong>,
  },
  { key: 'party', header: 'Party', render: (row: RegisterRow) => row.party },
  {
    key: 'category',
    header: 'Detail',
    secondary: true,
    render: (row: RegisterRow) => row.category,
  },
  {
    key: 'taxable',
    header: 'Taxable',
    numeric: true,
    secondary: true,
    render: (row: RegisterRow) => formatCurrency(row.taxable_value),
  },
  {
    key: 'tax',
    header: 'Tax',
    numeric: true,
    secondary: true,
    render: (row: RegisterRow) => formatCurrency(row.tax_amount),
  },
  {
    key: 'total',
    header: 'Total',
    numeric: true,
    render: (row: RegisterRow) => <strong>{formatCurrency(row.total)}</strong>,
  },
];
