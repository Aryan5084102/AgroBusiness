'use client';

import { useEffect, useMemo, useState } from 'react';
import { Badge, StatusBadge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { DataTable } from '@/components/ui/DataTable';
import { EmptyState } from '@/components/ui/EmptyState';
import { Icon } from '@/components/ui/Icon';
import { Select } from '@/components/ui/Field';
import { Pagination } from '@/components/ui/Pagination';
import { QueryState } from '@/components/feedback/QueryState';
import { SearchInput, Toolbar, ToolbarSpacer } from '@/components/ui/Toolbar';
import { Tabs } from '@/components/ui/Tabs';
import { useToast } from '@/components/ui/Toast';
import { usePermissions } from '@/features/auth/usePermissions';
import { useCustomers } from '@/features/customers/useCustomers';
import { ProductPicker } from '@/features/pos/ProductPicker';
import { useCart } from '@/features/pos/useCart';
import { useWarehouses } from '@/features/settings/useSettings';
import { useDispatchOrder, useOrders } from '@/features/invoices/useInvoices';
import type { OrderListItem, OrderStatus } from '@/features/invoices/api';
import { ApiError } from '@/lib/api/client';
import { formatCurrency } from '@/lib/formatting/currency';
import { formatDate } from '@/lib/formatting/dates';
import { OrderDetailDialog } from './OrderDetailDialog';
import type { OrderResult } from './api';
import { useCreateOrder } from './useWholesale';
import styles from './WholesaleScreen.module.scss';

type Tab = 'new' | 'orders';

const PAGE_SIZE = 25;

/** Dealer sales: build an order (credit-checked, stock reserved), then track it
 * through the pipeline and dispatch it into a credit invoice. */
export function WholesaleScreen() {
  const toast = useToast();
  const { can } = usePermissions();
  const [tab, setTab] = useState<Tab>('new');

  return (
    <>
      <Tabs<Tab>
        label="Wholesale sections"
        active={tab}
        onChange={setTab}
        items={[
          { id: 'new', label: 'New order', icon: 'plus' },
          { id: 'orders', label: 'Order pipeline', icon: 'wholesale' },
        ]}
      />
      {tab === 'new' ? (
        <OrderBuilder toast={toast} onCreated={() => setTab('orders')} />
      ) : (
        <OrderPipeline canDispatch={can('sales.finalize')} />
      )}
    </>
  );
}

function OrderBuilder({
  toast,
  onCreated,
}: {
  toast: ReturnType<typeof useToast>;
  onCreated: () => void;
}) {
  const warehouses = useWarehouses();
  const customers = useCustomers();
  const cart = useCart();
  const createOrder = useCreateOrder();

  const [warehouseId, setWarehouseId] = useState('');
  const [customerId, setCustomerId] = useState('');
  const [isQuotation, setIsQuotation] = useState(false);
  const [creditBlocked, setCreditBlocked] = useState(false);
  const [override, setOverride] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [order, setOrder] = useState<OrderResult | null>(null);

  useEffect(() => {
    if (!warehouseId && warehouses.data && warehouses.data.length > 0) {
      setWarehouseId(warehouses.data[0]!.id);
    }
  }, [warehouseId, warehouses.data]);

  const selectedCustomer = useMemo(
    () => customers.data?.find((customer) => customer.id === customerId) ?? null,
    [customers.data, customerId],
  );

  const onConfirm = async () => {
    if (!warehouseId || !customerId || cart.items.length === 0) return;
    setError(null);
    try {
      const result = await createOrder.mutateAsync({
        warehouseId,
        customerId,
        lines: cart.lines,
        isQuotation,
        creditOverrideApproved: override,
      });
      setOrder(result);
      setCreditBlocked(false);
      cart.clear();
      toast.success(
        `${isQuotation ? 'Quotation' : 'Order'} ${result.order_number} created`,
        isQuotation
          ? 'No stock reserved — convert it to an order when the dealer confirms.'
          : 'Stock is now reserved against this order.',
      );
      onCreated();
    } catch (err) {
      if (err instanceof ApiError && err.code === 'credit_limit_exceeded') {
        setCreditBlocked(true);
        setError(err.message);
      } else {
        const message =
          err instanceof ApiError ? err.message : 'The order could not be created.';
        setError(message);
        toast.error('Order not created', message);
      }
    }
  };

  return (
    <div className={styles.layout}>
      <div className={styles.left}>
        <Card>
          <CardBody>
            <div className={styles.contextRow}>
              <Select
                label="Dispatch from"
                value={warehouseId}
                onChange={(event) => setWarehouseId(event.target.value)}
              >
                {(warehouses.data ?? []).map((warehouse) => (
                  <option key={warehouse.id} value={warehouse.id}>
                    {warehouse.name} ({warehouse.code})
                  </option>
                ))}
              </Select>
              <Select
                label="Dealer"
                required
                value={customerId}
                onChange={(event) => {
                  setCustomerId(event.target.value);
                  setOrder(null);
                  setCreditBlocked(false);
                  setOverride(false);
                }}
              >
                <option value="">Select a dealer…</option>
                {(customers.data ?? []).map((customer) => (
                  <option key={customer.id} value={customer.id}>
                    {customer.name} ({customer.code})
                  </option>
                ))}
              </Select>
            </div>

            {selectedCustomer ? (
              <dl className={styles.credit}>
                <div>
                  <dt>Credit limit</dt>
                  <dd className="tabular-nums">
                    {formatCurrency(selectedCustomer.credit_limit)}
                  </dd>
                </div>
                <div>
                  <dt>Outstanding</dt>
                  <dd className="tabular-nums">
                    {formatCurrency(selectedCustomer.outstanding)}
                  </dd>
                </div>
                <div>
                  <dt>Credit available</dt>
                  <dd
                    className={`tabular-nums ${
                      Number(selectedCustomer.available_credit) < 0 ? styles.negative : ''
                    }`}
                  >
                    {formatCurrency(selectedCustomer.available_credit)}
                  </dd>
                </div>
              </dl>
            ) : null}
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Add items"
            description="Dealer pricing is applied automatically at wholesale rates."
          />
          <CardBody>
            <ProductPicker onAdd={cart.add} wholesale />
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader
          title="Order lines"
          actions={
            cart.items.length > 0 ? (
              <Button variant="ghost" size="sm" icon="trash" onClick={cart.clear}>
                Clear
              </Button>
            ) : null
          }
        />
        <CardBody>
          <div className={styles.panel}>
            {cart.items.length === 0 ? (
              <EmptyState
                icon="wholesale"
                title="No lines yet"
                description="Search the catalogue and pick products to build the order."
              />
            ) : (
              <ul role="list" className={styles.lines}>
                {cart.items.map((item) => (
                  <li key={item.productId} className={styles.line}>
                    <span className={styles.lineName}>{item.name}</span>
                    <input
                      type="number"
                      min={1}
                      value={item.quantity}
                      aria-label={`Quantity for ${item.name}`}
                      onChange={(event) =>
                        cart.setQuantity(item.productId, Number(event.target.value))
                      }
                    />
                    <button
                      type="button"
                      className={styles.remove}
                      aria-label={`Remove ${item.name}`}
                      onClick={() => cart.remove(item.productId)}
                    >
                      <Icon name="close" size={15} />
                    </button>
                  </li>
                ))}
              </ul>
            )}

            <label className={styles.checkbox}>
              <input
                type="checkbox"
                checked={isQuotation}
                onChange={(event) => setIsQuotation(event.target.checked)}
              />
              Save as a quotation (no credit check, no stock reserved)
            </label>

            {creditBlocked ? (
              <div className={styles.creditBlock}>
                <p>{error}</p>
                <label className={styles.checkbox}>
                  <input
                    type="checkbox"
                    checked={override}
                    onChange={(event) => setOverride(event.target.checked)}
                  />
                  I approve going over this dealer&apos;s credit limit
                </label>
              </div>
            ) : null}

            <Button
              size="lg"
              icon="check"
              onClick={onConfirm}
              isLoading={createOrder.isPending}
              disabled={!customerId || cart.items.length === 0}
            >
              {isQuotation ? 'Save quotation' : 'Confirm order'}
            </Button>

            {order ? (
              <p role="status" className={styles.success}>
                <Icon name="check" size={15} /> {order.order_number} ·{' '}
                {formatCurrency(order.grand_total)}
              </p>
            ) : null}
            {error && !creditBlocked ? (
              <p role="alert" className={styles.error}>
                {error}
              </p>
            ) : null}
          </div>
        </CardBody>
      </Card>
    </div>
  );
}

function OrderPipeline({ canDispatch }: { canDispatch: boolean }) {
  const toast = useToast();
  const [status, setStatus] = useState<OrderStatus | ''>('');
  const [search, setSearch] = useState('');
  const [offset, setOffset] = useState(0);
  const [openId, setOpenId] = useState<string | null>(null);

  const orders = useOrders({
    status: status || undefined,
    search: search || undefined,
    limit: PAGE_SIZE,
    offset,
  });
  const dispatchOrder = useDispatchOrder();

  const onDispatch = async (order: OrderListItem) => {
    try {
      const result = await dispatchOrder.mutateAsync(order.id);
      toast.success(
        `Dispatched ${order.order_number}`,
        `Credit invoice ${result.invoice_number} raised for ${formatCurrency(result.grand_total)}.`,
      );
    } catch (err) {
      toast.error(
        'Could not dispatch',
        err instanceof ApiError ? err.message : 'Please try again.',
      );
    }
  };

  return (
    <>
      <Card>
        <CardHeader
          title="Order pipeline"
          description="Confirmed orders hold reserved stock. Dispatching deducts it and raises a credit invoice."
        />
        <Toolbar>
          <SearchInput
            value={search}
            onChange={(value) => {
              setSearch(value);
              setOffset(0);
            }}
            placeholder="Search by order number…"
          />
          <Select
            label="Status"
            hideLabel
            value={status}
            onChange={(event) => {
              setStatus(event.target.value as OrderStatus | '');
              setOffset(0);
            }}
          >
            <option value="">All statuses</option>
            <option value="quotation">Quotation</option>
            <option value="confirmed">Confirmed</option>
            <option value="invoiced">Invoiced</option>
            <option value="cancelled">Cancelled</option>
          </Select>
          <ToolbarSpacer />
        </Toolbar>

        <QueryState
          isLoading={orders.isLoading}
          error={orders.error}
          onRetry={orders.refetch}
          loadingHeight={260}
        >
          <DataTable<OrderListItem>
            rows={orders.data?.items ?? []}
            rowKey={(row) => row.id}
            onRowClick={(row) => setOpenId(row.id)}
            emptyTitle="No orders yet"
            emptyDescription="Create a dealer order to see it here."
            columns={[
              {
                key: 'order',
                header: 'Order',
                render: (row) => (
                  <span className={styles.primaryCell}>
                    <span>{row.order_number}</span>
                    <span className={styles.muted}>{formatDate(row.order_date)}</span>
                  </span>
                ),
              },
              { key: 'customer', header: 'Dealer', render: (row) => row.customer_name },
              {
                key: 'warehouse',
                header: 'From',
                secondary: true,
                render: (row) => row.warehouse_name,
              },
              {
                key: 'status',
                header: 'Status',
                render: (row) => (
                  <span className={styles.statusCell}>
                    <StatusBadge status={row.status} />
                    {row.credit_override_approved ? (
                      <Badge tone="warning">Override</Badge>
                    ) : null}
                  </span>
                ),
              },
              {
                key: 'total',
                header: 'Value',
                numeric: true,
                render: (row) => <strong>{formatCurrency(row.grand_total)}</strong>,
              },
              {
                key: 'action',
                header: '',
                render: (row) =>
                  row.status === 'confirmed' && canDispatch ? (
                    <Button
                      size="sm"
                      variant="secondary"
                      isLoading={
                        dispatchOrder.isPending && dispatchOrder.variables === row.id
                      }
                      onClick={(event) => {
                        event.stopPropagation();
                        onDispatch(row);
                      }}
                    >
                      Dispatch
                    </Button>
                  ) : null,
              },
            ]}
          />
        </QueryState>

        <Pagination
          total={orders.data?.total ?? 0}
          limit={PAGE_SIZE}
          offset={offset}
          onOffsetChange={setOffset}
          noun="orders"
        />
      </Card>

      <OrderDetailDialog orderId={openId} onClose={() => setOpenId(null)} />
    </>
  );
}
