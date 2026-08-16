'use client';

import { useState } from 'react';
import { Badge, StatusBadge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader } from '@/components/ui/Card';
import { DataTable } from '@/components/ui/DataTable';
import { Select } from '@/components/ui/Field';
import { Pagination } from '@/components/ui/Pagination';
import { QueryState } from '@/components/feedback/QueryState';
import { SearchInput, Toolbar, ToolbarSpacer } from '@/components/ui/Toolbar';
import { StatCard, StatGrid } from '@/components/ui/StatCard';
import { formatCurrency } from '@/lib/formatting/currency';
import { formatDate } from '@/lib/formatting/dates';
import { humanize } from '@/components/ui/Badge';
import { JobDetailDialog } from './JobDetailDialog';
import { NewJobDialog } from './NewJobDialog';
import { REPAIR_STATUSES, type RepairJob, type RepairStatus } from './api';
import { useJobs } from './useService';
import styles from './ServiceScreen.module.scss';

const PAGE_SIZE = 25;

/** The workshop's screen: book a machine in, track it through the bench, put
 * spare parts on the job (which deducts stock), and bill it out. */
export function ServiceScreen() {
  const [status, setStatus] = useState<RepairStatus | ''>('');
  const [search, setSearch] = useState('');
  const [offset, setOffset] = useState(0);
  const [creating, setCreating] = useState(false);
  const [openJobId, setOpenJobId] = useState<string | null>(null);

  const jobs = useJobs({
    status: status || undefined,
    search: search || undefined,
    limit: PAGE_SIZE,
    offset,
  });

  const rows = jobs.data?.items ?? [];
  const warrantyCount = rows.filter((job) => job.is_warranty_covered).length;
  const billable = rows.reduce((total, job) => total + Number(job.customer_payable), 0);

  return (
    <>
      <StatGrid>
        <StatCard
          label="Open jobs"
          icon="service"
          tone="warning"
          isLoading={jobs.isLoading}
          value={jobs.data?.open_count ?? 0}
          hint="Still on the bench or awaiting parts"
        />
        <StatCard
          label="Jobs in view"
          icon="dashboard"
          isLoading={jobs.isLoading}
          value={jobs.data?.total ?? 0}
          hint="Matching the current filter"
        />
        <StatCard
          label="Under warranty"
          icon="check"
          tone="positive"
          isLoading={jobs.isLoading}
          value={warrantyCount}
          hint="Parts waived on these jobs"
        />
        <StatCard
          label="Billable on this page"
          icon="collections"
          isLoading={jobs.isLoading}
          value={formatCurrency(billable)}
          hint="Labour plus chargeable parts"
        />
      </StatGrid>

      <Card>
        <CardHeader
          title="Repair jobs"
          description="Newest first. Open a job to add parts, set labour and mark it ready."
          actions={
            <Button size="sm" icon="plus" onClick={() => setCreating(true)}>
              Book a machine in
            </Button>
          }
        />
        <Toolbar>
          <SearchInput
            value={search}
            onChange={(value) => {
              setSearch(value);
              setOffset(0);
            }}
            placeholder="Search by job number…"
          />
          <Select
            label="Status"
            hideLabel
            value={status}
            onChange={(event) => {
              setStatus(event.target.value as RepairStatus | '');
              setOffset(0);
            }}
          >
            <option value="">All statuses</option>
            {REPAIR_STATUSES.map((value) => (
              <option key={value} value={value}>
                {humanize(value)}
              </option>
            ))}
          </Select>
          <ToolbarSpacer />
        </Toolbar>

        <QueryState
          isLoading={jobs.isLoading}
          error={jobs.error}
          onRetry={jobs.refetch}
          loadingHeight={280}
        >
          <DataTable<RepairJob>
            rows={rows}
            rowKey={(row) => row.id}
            onRowClick={(row) => setOpenJobId(row.id)}
            emptyTitle="No repair jobs"
            emptyDescription="Book a machine in when a customer drops it off for service."
            emptyAction={
              <Button size="sm" icon="plus" onClick={() => setCreating(true)}>
                Book a machine in
              </Button>
            }
            columns={[
              {
                key: 'job',
                header: 'Job',
                render: (row) => (
                  <span className={styles.primaryCell}>
                    <span>{row.job_number}</span>
                    <span className={styles.muted}>
                      {row.product_name ?? 'Unspecified machine'}
                    </span>
                  </span>
                ),
              },
              {
                key: 'customer',
                header: 'Customer',
                render: (row) => row.customer_name ?? '—',
              },
              {
                key: 'received',
                header: 'Received',
                secondary: true,
                render: (row) => formatDate(row.received_date),
              },
              {
                key: 'warranty',
                header: 'Cover',
                secondary: true,
                render: (row) =>
                  row.is_warranty_covered ? (
                    <Badge tone="success">Warranty</Badge>
                  ) : (
                    <Badge tone="neutral">Chargeable</Badge>
                  ),
              },
              {
                key: 'status',
                header: 'Status',
                render: (row) => <StatusBadge status={row.status} />,
              },
              {
                key: 'payable',
                header: 'Customer pays',
                numeric: true,
                render: (row) => formatCurrency(row.customer_payable),
              },
            ]}
          />
        </QueryState>

        <Pagination
          total={jobs.data?.total ?? 0}
          limit={PAGE_SIZE}
          offset={offset}
          onOffsetChange={setOffset}
          noun="jobs"
        />
      </Card>

      <NewJobDialog
        open={creating}
        onClose={() => setCreating(false)}
        onCreated={(jobId) => setOpenJobId(jobId)}
      />
      <JobDetailDialog jobId={openJobId} onClose={() => setOpenJobId(null)} />
    </>
  );
}
