'use client';

import { useState } from 'react';
import { Badge, humanize } from '@/components/ui/Badge';
import { Card, CardHeader } from '@/components/ui/Card';
import { DataTable } from '@/components/ui/DataTable';
import { Select } from '@/components/ui/Field';
import { Pagination } from '@/components/ui/Pagination';
import { QueryState } from '@/components/feedback/QueryState';
import { Toolbar, ToolbarSpacer } from '@/components/ui/Toolbar';
import { formatDateTime } from '@/lib/formatting/dates';
import type { AuditLog } from './api';
import { useAuditLogs } from './useAudit';
import styles from './AuditScreen.module.scss';

const PAGE_SIZE = 50;

/** The append-only audit trail. Read-only for everyone — including the owner —
 * so the record of who did what cannot be quietly rewritten. */
export function AuditScreen() {
  const [action, setAction] = useState('');
  const [offset, setOffset] = useState(0);

  const logs = useAuditLogs({
    action: action || undefined,
    limit: PAGE_SIZE,
    offset,
  });

  return (
    <Card>
      <CardHeader
        title="Audit log"
        description="Every security-relevant action, newest first. Entries can never be edited or deleted."
      />
      <Toolbar>
        <Select
          label="Action"
          hideLabel
          value={action}
          onChange={(event) => {
            setAction(event.target.value);
            setOffset(0);
          }}
        >
          <option value="">All actions</option>
          {(logs.data?.actions ?? []).map((value) => (
            <option key={value} value={value}>
              {humanize(value.replace(/\./g, ' · '))}
            </option>
          ))}
        </Select>
        <ToolbarSpacer />
      </Toolbar>

      <QueryState
        isLoading={logs.isLoading}
        error={logs.error}
        onRetry={logs.refetch}
        loadingHeight={300}
      >
        <DataTable<AuditLog>
          rows={logs.data?.items ?? []}
          rowKey={(row) => row.id}
          emptyTitle="No audit entries"
          emptyDescription="Sign-ins and privileged actions are recorded here as they happen."
          columns={[
            {
              key: 'when',
              header: 'When',
              render: (row) => formatDateTime(row.created_at),
            },
            {
              key: 'action',
              header: 'Action',
              render: (row) => (
                <Badge tone={toneFor(row.action)} dot>
                  {row.action}
                </Badge>
              ),
            },
            {
              key: 'actor',
              header: 'By',
              render: (row) => (
                <span className={styles.primaryCell}>
                  <span>{row.actor_name ?? 'System'}</span>
                  {row.ip_address ? (
                    <span className={styles.muted}>{row.ip_address}</span>
                  ) : null}
                </span>
              ),
            },
            {
              key: 'entity',
              header: 'Target',
              secondary: true,
              render: (row) =>
                row.entity_type ? (
                  <span className={styles.primaryCell}>
                    <span>{humanize(row.entity_type)}</span>
                    {row.entity_id ? (
                      <span className={styles.muted}>{row.entity_id}</span>
                    ) : null}
                  </span>
                ) : (
                  '—'
                ),
            },
            {
              key: 'reason',
              header: 'Detail',
              secondary: true,
              render: (row) => row.reason ?? '—',
            },
          ]}
        />
      </QueryState>

      <Pagination
        total={logs.data?.total ?? 0}
        limit={PAGE_SIZE}
        offset={offset}
        onOffsetChange={setOffset}
        noun="entries"
      />
    </Card>
  );
}

/** Failures and lockouts should stand out from routine successes. */
function toneFor(action: string): 'danger' | 'warning' | 'success' | 'neutral' {
  if (action.includes('failed') || action.includes('denied')) return 'danger';
  if (action.includes('locked') || action.includes('reuse')) return 'warning';
  if (action.includes('success') || action.includes('created')) return 'success';
  return 'neutral';
}
