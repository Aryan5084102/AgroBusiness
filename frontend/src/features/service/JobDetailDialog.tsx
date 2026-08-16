'use client';

import { useState } from 'react';
import { Badge, StatusBadge, humanize } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { DataTable } from '@/components/ui/DataTable';
import { Input, Select } from '@/components/ui/Field';
import { Modal } from '@/components/ui/Modal';
import { QueryState } from '@/components/feedback/QueryState';
import { useToast } from '@/components/ui/Toast';
import { useProducts } from '@/features/products/useProducts';
import { ApiError } from '@/lib/api/client';
import { formatCurrency } from '@/lib/formatting/currency';
import { formatDate, formatQuantity } from '@/lib/formatting/dates';
import { REPAIR_STATUSES, type JobPart, type RepairStatus } from './api';
import {
  useCompleteJob,
  useConsumePart,
  useJob,
  useReturnPart,
  useUpdateJobStatus,
} from './useService';
import styles from './ServiceScreen.module.scss';

interface JobDetailDialogProps {
  jobId: string | null;
  onClose: () => void;
}

/** The working view of a repair job: move it through statuses, consume spare
 * parts (which deducts stock via FEFO), return unused ones, and bill it. */
export function JobDetailDialog({ jobId, onClose }: JobDetailDialogProps) {
  const toast = useToast();
  const job = useJob(jobId);
  const products = useProducts({ limit: 100 }, Boolean(jobId));
  const updateStatus = useUpdateJobStatus();
  const consumePart = useConsumePart();
  const returnPart = useReturnPart();
  const completeJob = useCompleteJob();

  const [partId, setPartId] = useState('');
  const [partQty, setPartQty] = useState('1');
  const [labour, setLabour] = useState('');
  const [error, setError] = useState<string | null>(null);

  const detail = job.data;
  const closed = detail?.status === 'delivered' || detail?.status === 'cancelled';

  const run = async (action: () => Promise<unknown>, success: string) => {
    setError(null);
    try {
      await action();
      toast.success(success);
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : 'That action could not be completed.';
      setError(message);
      toast.error('Action failed', message);
    }
  };

  return (
    <Modal
      open={Boolean(jobId)}
      onClose={onClose}
      size="lg"
      title={detail ? `Job ${detail.job_number}` : 'Repair job'}
      description={detail?.complaint ?? undefined}
      footer={
        <Button variant="secondary" onClick={onClose}>
          Close
        </Button>
      }
    >
      <QueryState isLoading={job.isLoading} error={job.error} onRetry={job.refetch}>
        {detail ? (
          <div className={styles.detail}>
            <dl className={styles.facts}>
              <div>
                <dt>Status</dt>
                <dd>
                  <StatusBadge status={detail.status} />
                </dd>
              </div>
              <div>
                <dt>Customer</dt>
                <dd>{detail.customer_name ?? '—'}</dd>
              </div>
              <div>
                <dt>Machine</dt>
                <dd>{detail.product_name ?? '—'}</dd>
              </div>
              <div>
                <dt>Received</dt>
                <dd>{formatDate(detail.received_date)}</dd>
              </div>
              <div>
                <dt>Technician</dt>
                <dd>{detail.technician_name ?? '—'}</dd>
              </div>
              <div>
                <dt>Cover</dt>
                <dd>
                  {detail.is_warranty_covered ? (
                    <Badge tone="success">Warranty — parts waived</Badge>
                  ) : (
                    <Badge tone="neutral">Chargeable</Badge>
                  )}
                </dd>
              </div>
            </dl>

            <section className={styles.section}>
              <h4 className={styles.sectionTitle}>Move the job on</h4>
              <div className={styles.inline}>
                <Select
                  label="Set status"
                  hideLabel
                  value={detail.status}
                  disabled={closed || updateStatus.isPending}
                  onChange={(event) =>
                    run(
                      () =>
                        updateStatus.mutateAsync({
                          jobId: detail.id,
                          status: event.target.value as RepairStatus,
                        }),
                      'Status updated',
                    )
                  }
                >
                  {REPAIR_STATUSES.map((value) => (
                    <option key={value} value={value}>
                      {humanize(value)}
                    </option>
                  ))}
                </Select>
                {closed ? (
                  <p className={styles.note}>
                    This job is closed and can no longer change.
                  </p>
                ) : null}
              </div>
            </section>

            <section className={styles.section}>
              <h4 className={styles.sectionTitle}>Spare parts used</h4>
              <DataTable<JobPart>
                rows={detail.parts}
                rowKey={(row) => row.id}
                emptyTitle="No parts consumed yet"
                emptyDescription="Adding a part here deducts it from stock immediately."
                columns={[
                  { key: 'name', header: 'Part', render: (row) => row.product_name },
                  {
                    key: 'qty',
                    header: 'Qty',
                    numeric: true,
                    render: (row) => formatQuantity(row.base_quantity),
                  },
                  {
                    key: 'price',
                    header: 'Unit price',
                    numeric: true,
                    secondary: true,
                    render: (row) => formatCurrency(row.unit_price),
                  },
                  {
                    key: 'total',
                    header: 'Total',
                    numeric: true,
                    render: (row) =>
                      row.is_returned ? (
                        <span className={styles.struck}>
                          {formatCurrency(row.line_total)}
                        </span>
                      ) : (
                        formatCurrency(row.line_total)
                      ),
                  },
                  {
                    key: 'action',
                    header: '',
                    render: (row) =>
                      row.is_returned ? (
                        <Badge tone="neutral">Returned</Badge>
                      ) : (
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={closed || returnPart.isPending}
                          onClick={() =>
                            run(
                              () =>
                                returnPart.mutateAsync({
                                  jobId: detail.id,
                                  partId: row.id,
                                }),
                              'Part returned to stock',
                            )
                          }
                        >
                          Return
                        </Button>
                      ),
                  },
                ]}
              />

              {!closed ? (
                <div className={styles.inline}>
                  <Select
                    label="Part"
                    value={partId}
                    onChange={(event) => setPartId(event.target.value)}
                  >
                    <option value="">Choose a part…</option>
                    {(products.data?.items ?? []).map((product) => (
                      <option key={product.id} value={product.id}>
                        {product.name} ({product.sku})
                      </option>
                    ))}
                  </Select>
                  <Input
                    label="Quantity"
                    type="number"
                    min="0"
                    step="0.001"
                    value={partQty}
                    onChange={(event) => setPartQty(event.target.value)}
                  />
                  <Button
                    icon="plus"
                    isLoading={consumePart.isPending}
                    disabled={!partId || Number(partQty) <= 0}
                    onClick={() =>
                      run(async () => {
                        await consumePart.mutateAsync({
                          jobId: detail.id,
                          productId: partId,
                          baseQuantity: partQty,
                        });
                        setPartId('');
                        setPartQty('1');
                      }, 'Part added and stock deducted')
                    }
                  >
                    Add part
                  </Button>
                </div>
              ) : null}
            </section>

            <section className={styles.section}>
              <h4 className={styles.sectionTitle}>Billing</h4>
              <dl className={styles.totals}>
                <div>
                  <dt>Parts</dt>
                  <dd className="tabular-nums">{formatCurrency(detail.parts_total)}</dd>
                </div>
                <div>
                  <dt>Labour</dt>
                  <dd className="tabular-nums">
                    {formatCurrency(detail.labour_charges)}
                  </dd>
                </div>
                <div className={styles.grand}>
                  <dt>Customer pays</dt>
                  <dd className="tabular-nums">
                    {formatCurrency(detail.customer_payable)}
                  </dd>
                </div>
              </dl>
              {detail.is_warranty_covered ? (
                <p className={styles.note}>
                  Parts are waived because this machine is under warranty — only labour is
                  billed.
                </p>
              ) : null}

              {!closed ? (
                <div className={styles.inline}>
                  <Input
                    label="Labour charges"
                    type="number"
                    min="0"
                    step="0.01"
                    value={labour}
                    placeholder={detail.labour_charges}
                    onChange={(event) => setLabour(event.target.value)}
                  />
                  <Button
                    icon="check"
                    isLoading={completeJob.isPending}
                    onClick={() =>
                      run(
                        () =>
                          completeJob.mutateAsync({
                            jobId: detail.id,
                            labourCharges: labour || detail.labour_charges,
                          }),
                        'Job marked ready for collection',
                      )
                    }
                  >
                    Set labour &amp; mark ready
                  </Button>
                </div>
              ) : null}
            </section>

            {error ? (
              <p role="alert" className={styles.error}>
                {error}
              </p>
            ) : null}
          </div>
        ) : null}
      </QueryState>
    </Modal>
  );
}
