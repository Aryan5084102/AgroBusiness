'use client';

import { useState } from 'react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader } from '@/components/ui/Card';
import { DataTable } from '@/components/ui/DataTable';
import { Select } from '@/components/ui/Field';
import { Pagination } from '@/components/ui/Pagination';
import { QueryState } from '@/components/feedback/QueryState';
import { SearchInput, Toolbar, ToolbarSpacer } from '@/components/ui/Toolbar';
import { Tabs } from '@/components/ui/Tabs';
import { usePermissions } from '@/features/auth/usePermissions';
import { useWarehouses } from '@/features/settings/useSettings';
import { formatDateTime, formatQuantity } from '@/lib/formatting/dates';
import { humanize } from '@/components/ui/Badge';
import { AdjustStockDialog } from './AdjustStockDialog';
import { TransferStockDialog } from './TransferStockDialog';
import { useBatches, useMovements, useStock } from './useInventory';
import type { BatchRow, Movement, StockRow } from './api';
import styles from './InventoryScreen.module.scss';

type Tab = 'stock' | 'batches' | 'ledger';

const PAGE_SIZE = 25;

/** Stock levels, batch/expiry tracking and the append-only movement ledger,
 * plus the two write actions (adjust, transfer) gated by their permissions. */
export function InventoryScreen() {
  const { can } = usePermissions();
  const [tab, setTab] = useState<Tab>('stock');
  const [search, setSearch] = useState('');
  const [warehouseId, setWarehouseId] = useState('');
  const [lowOnly, setLowOnly] = useState(false);
  const [offset, setOffset] = useState(0);
  const [adjusting, setAdjusting] = useState(false);
  const [transferring, setTransferring] = useState(false);

  const warehouses = useWarehouses();
  const stock = useStock(
    {
      search: search || undefined,
      warehouseId: warehouseId || undefined,
      lowOnly,
      limit: PAGE_SIZE,
      offset,
    },
    tab === 'stock',
  );
  const batches = useBatches(
    { warehouseId: warehouseId || undefined },
    tab === 'batches',
  );
  const movements = useMovements(
    { warehouseId: warehouseId || undefined, limit: PAGE_SIZE, offset },
    tab === 'ledger',
  );

  const changeTab = (next: Tab) => {
    setTab(next);
    setOffset(0);
  };

  const warehouseFilter = (
    <Select
      label="Warehouse"
      hideLabel
      value={warehouseId}
      onChange={(event) => {
        setWarehouseId(event.target.value);
        setOffset(0);
      }}
    >
      <option value="">All warehouses</option>
      {(warehouses.data ?? []).map((warehouse) => (
        <option key={warehouse.id} value={warehouse.id}>
          {warehouse.name}
        </option>
      ))}
    </Select>
  );

  return (
    <>
      <Tabs<Tab>
        label="Inventory sections"
        active={tab}
        onChange={changeTab}
        items={[
          { id: 'stock', label: 'Stock on hand', icon: 'inventory' },
          { id: 'batches', label: 'Batches & expiry', icon: 'alert' },
          { id: 'ledger', label: 'Movement ledger', icon: 'audit' },
        ]}
      />

      {tab === 'stock' ? (
        <Card>
          <CardHeader
            title="Stock on hand"
            description="Live balances per product and warehouse. Reserved stock is committed to confirmed wholesale orders."
            actions={
              <>
                {can('stock.transfer') ? (
                  <Button
                    variant="secondary"
                    size="sm"
                    icon="refresh"
                    onClick={() => setTransferring(true)}
                  >
                    Transfer
                  </Button>
                ) : null}
                {can('inventory.adjust') ? (
                  <Button size="sm" icon="edit" onClick={() => setAdjusting(true)}>
                    Adjust stock
                  </Button>
                ) : null}
              </>
            }
          />
          <Toolbar>
            <SearchInput
              value={search}
              onChange={(value) => {
                setSearch(value);
                setOffset(0);
              }}
              placeholder="Search by product name or SKU…"
            />
            {warehouseFilter}
            <ToolbarSpacer />
            <Button
              variant={lowOnly ? 'subtle' : 'ghost'}
              size="sm"
              icon="alert"
              aria-pressed={lowOnly}
              onClick={() => {
                setLowOnly((value) => !value);
                setOffset(0);
              }}
            >
              Low stock only
            </Button>
          </Toolbar>
          <QueryState
            isLoading={stock.isLoading}
            error={stock.error}
            onRetry={stock.refetch}
            loadingHeight={260}
          >
            <DataTable<StockRow>
              rows={stock.data?.items ?? []}
              rowKey={(row) => `${row.product_id}-${row.warehouse_id}`}
              emptyTitle={lowOnly ? 'Nothing is running low' : 'No stock found'}
              emptyDescription={
                lowOnly
                  ? 'Every product is above its reorder level.'
                  : 'Receive goods from a supplier to build up stock.'
              }
              columns={[
                {
                  key: 'product',
                  header: 'Product',
                  render: (row) => (
                    <span className={styles.primaryCell}>
                      <span>{row.product_name}</span>
                      {/* The warehouse column is hidden on phones, but it is
                          what tells two rows of the same product apart. */}
                      <span className={styles.muted}>
                        {row.sku} · {row.warehouse_name}
                      </span>
                    </span>
                  ),
                },
                {
                  key: 'warehouse',
                  header: 'Warehouse',
                  secondary: true,
                  render: (row) => row.warehouse_name,
                },
                {
                  key: 'onHand',
                  header: 'On hand',
                  numeric: true,
                  render: (row) => `${formatQuantity(row.on_hand)} ${row.unit_code}`,
                },
                {
                  key: 'reserved',
                  header: 'Reserved',
                  numeric: true,
                  secondary: true,
                  render: (row) =>
                    Number(row.reserved) > 0 ? formatQuantity(row.reserved) : '—',
                },
                {
                  key: 'available',
                  header: 'Available',
                  numeric: true,
                  render: (row) => <strong>{formatQuantity(row.available)}</strong>,
                },
                {
                  key: 'status',
                  header: 'Status',
                  render: (row) =>
                    row.is_low ? (
                      <Badge tone="danger" dot>
                        Below minimum
                      </Badge>
                    ) : (
                      <Badge tone="success" dot>
                        Healthy
                      </Badge>
                    ),
                },
              ]}
            />
          </QueryState>
          <Pagination
            total={stock.data?.total ?? 0}
            limit={PAGE_SIZE}
            offset={offset}
            onOffsetChange={setOffset}
            noun="stock rows"
          />
        </Card>
      ) : null}

      {tab === 'batches' ? (
        <Card>
          <CardHeader
            title="Batches & expiry"
            description="Earliest expiry first — the order stock is issued in (FEFO). Expired batches are never allocated to a sale."
          />
          <Toolbar>{warehouseFilter}</Toolbar>
          <QueryState
            isLoading={batches.isLoading}
            error={batches.error}
            onRetry={batches.refetch}
            loadingHeight={260}
          >
            <DataTable<BatchRow>
              rows={batches.data ?? []}
              rowKey={(row) => `${row.batch_id}-${row.warehouse_id}`}
              emptyTitle="No batch-tracked stock"
              emptyDescription="Batches are created when you receive goods with a batch number."
              columns={[
                {
                  key: 'batch',
                  header: 'Batch',
                  render: (row) => (
                    <span className={styles.primaryCell}>
                      <span>{row.batch_number}</span>
                      <span className={styles.muted}>{row.product_name}</span>
                    </span>
                  ),
                },
                {
                  key: 'warehouse',
                  header: 'Warehouse',
                  secondary: true,
                  render: (row) => row.warehouse_name,
                },
                {
                  key: 'expiry',
                  header: 'Expiry',
                  render: (row) => <ExpiryCell row={row} />,
                },
                {
                  key: 'onHand',
                  header: 'On hand',
                  numeric: true,
                  render: (row) => formatQuantity(row.on_hand),
                },
                {
                  key: 'available',
                  header: 'Available',
                  numeric: true,
                  render: (row) => formatQuantity(row.available),
                },
              ]}
            />
          </QueryState>
        </Card>
      ) : null}

      {tab === 'ledger' ? (
        <Card>
          <CardHeader
            title="Movement ledger"
            description="Every stock change, newest first. The ledger is append-only — corrections are new entries, never edits."
          />
          <Toolbar>{warehouseFilter}</Toolbar>
          <QueryState
            isLoading={movements.isLoading}
            error={movements.error}
            onRetry={movements.refetch}
            loadingHeight={260}
          >
            <DataTable<Movement>
              rows={movements.data?.items ?? []}
              rowKey={(row) => row.id}
              emptyTitle="No movements recorded"
              emptyDescription="Receipts, sales, transfers and adjustments all land here."
              columns={[
                {
                  key: 'when',
                  header: 'When',
                  render: (row) => formatDateTime(row.created_at),
                },
                {
                  key: 'product',
                  header: 'Product',
                  render: (row) => (
                    <span className={styles.primaryCell}>
                      <span>{row.product_name}</span>
                      <span className={styles.muted}>
                        {row.batch_number ? `Batch ${row.batch_number}` : row.sku}
                      </span>
                    </span>
                  ),
                },
                {
                  key: 'type',
                  header: 'Reason',
                  render: (row) => (
                    <span className={styles.primaryCell}>
                      <span>{humanize(row.movement_type)}</span>
                      {row.reason ? (
                        <span className={styles.muted}>{row.reason}</span>
                      ) : null}
                    </span>
                  ),
                },
                {
                  key: 'warehouse',
                  header: 'Warehouse',
                  secondary: true,
                  render: (row) => row.warehouse_name,
                },
                {
                  key: 'by',
                  header: 'By',
                  secondary: true,
                  render: (row) => row.actor_name ?? 'System',
                },
                {
                  key: 'qty',
                  header: 'Quantity',
                  numeric: true,
                  render: (row) => (
                    <span
                      className={
                        Number(row.base_quantity) < 0 ? styles.negative : styles.positive
                      }
                    >
                      {Number(row.base_quantity) > 0 ? '+' : ''}
                      {formatQuantity(row.base_quantity)}
                    </span>
                  ),
                },
              ]}
            />
          </QueryState>
          <Pagination
            total={movements.data?.total ?? 0}
            limit={PAGE_SIZE}
            offset={offset}
            onOffsetChange={setOffset}
            noun="movements"
          />
        </Card>
      ) : null}

      <AdjustStockDialog open={adjusting} onClose={() => setAdjusting(false)} />
      <TransferStockDialog open={transferring} onClose={() => setTransferring(false)} />
    </>
  );
}

function ExpiryCell({ row }: { row: BatchRow }) {
  if (!row.expiry_date) return <span className={styles.muted}>No expiry</span>;
  if (row.is_expired) {
    return (
      <Badge tone="danger" dot>
        Expired {Math.abs(row.days_to_expiry ?? 0)}d ago
      </Badge>
    );
  }
  const days = row.days_to_expiry ?? 0;
  if (days <= 30) {
    return (
      <Badge tone="warning" dot>
        {days} days left
      </Badge>
    );
  }
  return (
    <Badge tone="success" dot>
      {days} days left
    </Badge>
  );
}
