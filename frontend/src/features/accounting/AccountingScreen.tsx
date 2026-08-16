'use client';

import { useState } from 'react';
import { Badge } from '@/components/ui/Badge';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { DataTable } from '@/components/ui/DataTable';
import { Select } from '@/components/ui/Field';
import { Pagination } from '@/components/ui/Pagination';
import { QueryState } from '@/components/feedback/QueryState';
import { StatCard, StatGrid } from '@/components/ui/StatCard';
import { Tabs } from '@/components/ui/Tabs';
import { Toolbar } from '@/components/ui/Toolbar';
import { useCustomers } from '@/features/customers/useCustomers';
import { formatCurrency } from '@/lib/formatting/currency';
import { formatDate } from '@/lib/formatting/dates';
import type { JournalEntry, LedgerRow, TrialBalanceRow } from './api';
import { useCustomerLedger, useJournals, useTrialBalance } from './useAccounting';
import styles from './AccountingScreen.module.scss';

type Tab = 'trial' | 'journals' | 'ledger';

const PAGE_SIZE = 25;

/** The books: a trial balance that must balance, the journal register behind
 * it, and a per-customer statement. Entries are posted automatically by sales
 * and collections — nothing here is hand-keyed. */
export function AccountingScreen() {
  const [tab, setTab] = useState<Tab>('trial');
  const [offset, setOffset] = useState(0);
  const [customerId, setCustomerId] = useState('');

  const trial = useTrialBalance(tab === 'trial');
  const journals = useJournals(offset, tab === 'journals');
  const customers = useCustomers({ enabled: tab === 'ledger' });
  const ledger = useCustomerLedger(tab === 'ledger' ? customerId || null : null);

  return (
    <>
      <Tabs<Tab>
        label="Accounting views"
        active={tab}
        onChange={(next) => {
          setTab(next);
          setOffset(0);
        }}
        items={[
          { id: 'trial', label: 'Trial balance', icon: 'accounting' },
          { id: 'journals', label: 'Journal register', icon: 'invoices' },
          { id: 'ledger', label: 'Customer statement', icon: 'customers' },
        ]}
      />

      {tab === 'trial' ? (
        <Card>
          <CardHeader
            title="Trial balance"
            description="Debits and credits per account. A balanced total is proof the ledger is internally consistent."
          />
          <QueryState
            isLoading={trial.isLoading}
            error={trial.error}
            onRetry={trial.refetch}
            loadingHeight={260}
          >
            <>
              <CardBody>
                <StatGrid>
                  <StatCard
                    label="Total debits"
                    value={formatCurrency(trial.data?.total_debit ?? '0')}
                  />
                  <StatCard
                    label="Total credits"
                    value={formatCurrency(trial.data?.total_credit ?? '0')}
                  />
                  <StatCard
                    label="Status"
                    tone={trial.data?.is_balanced ? 'positive' : 'danger'}
                    icon={trial.data?.is_balanced ? 'check' : 'alert'}
                    value={trial.data?.is_balanced ? 'Balanced' : 'Out of balance'}
                    hint="Debits must equal credits"
                  />
                </StatGrid>
              </CardBody>
              <DataTable<TrialBalanceRow>
                rows={trial.data?.rows ?? []}
                rowKey={(row) => row.account_code}
                emptyTitle="No postings yet"
                emptyDescription="Sales and collections post journals automatically."
                columns={[
                  {
                    key: 'account',
                    header: 'Account',
                    render: (row) => (
                      <span className={styles.primaryCell}>
                        <span>{row.account_name}</span>
                        <span className={styles.muted}>{row.account_code}</span>
                      </span>
                    ),
                  },
                  {
                    key: 'type',
                    header: 'Type',
                    secondary: true,
                    render: (row) => <Badge tone="neutral">{row.account_type}</Badge>,
                  },
                  {
                    key: 'debit',
                    header: 'Debit',
                    numeric: true,
                    render: (row) =>
                      Number(row.debit) > 0 ? formatCurrency(row.debit) : '—',
                  },
                  {
                    key: 'credit',
                    header: 'Credit',
                    numeric: true,
                    render: (row) =>
                      Number(row.credit) > 0 ? formatCurrency(row.credit) : '—',
                  },
                  {
                    key: 'balance',
                    header: 'Balance',
                    numeric: true,
                    render: (row) => <strong>{formatCurrency(row.balance)}</strong>,
                  },
                ]}
              />
            </>
          </QueryState>
        </Card>
      ) : null}

      {tab === 'journals' ? (
        <Card>
          <CardHeader
            title="Journal register"
            description="Every posting, newest first. Each entry balances on its own."
          />
          <QueryState
            isLoading={journals.isLoading}
            error={journals.error}
            onRetry={journals.refetch}
            loadingHeight={260}
          >
            <DataTable<JournalEntry>
              rows={journals.data?.items ?? []}
              rowKey={(row) => row.id}
              emptyTitle="No journal entries"
              emptyDescription="Finalize a sale or receive a payment to post the first entry."
              columns={[
                {
                  key: 'date',
                  header: 'Date',
                  render: (row) => formatDate(row.entry_date),
                },
                {
                  key: 'narration',
                  header: 'Narration',
                  render: (row) => (
                    <span className={styles.primaryCell}>
                      <span>{row.narration ?? 'Journal entry'}</span>
                      <span className={styles.muted}>
                        {row.source_document_type?.replace(/_/g, ' ') ?? 'manual'}
                      </span>
                    </span>
                  ),
                },
                {
                  key: 'lines',
                  header: 'Postings',
                  render: (row) => (
                    <ul className={styles.lines}>
                      {row.lines.map((line, index) => (
                        <li key={`${line.account_code}-${index}`}>
                          <span className={styles.lineAccount}>{line.account_name}</span>
                          <span className="tabular-nums">
                            {Number(line.debit) > 0
                              ? `Dr ${formatCurrency(line.debit)}`
                              : `Cr ${formatCurrency(line.credit)}`}
                          </span>
                        </li>
                      ))}
                    </ul>
                  ),
                },
                {
                  key: 'total',
                  header: 'Total',
                  numeric: true,
                  render: (row) => <strong>{formatCurrency(row.total)}</strong>,
                },
              ]}
            />
          </QueryState>
          <Pagination
            total={journals.data?.total ?? 0}
            limit={PAGE_SIZE}
            offset={offset}
            onOffsetChange={setOffset}
            noun="entries"
          />
        </Card>
      ) : null}

      {tab === 'ledger' ? (
        <Card>
          <CardHeader
            title="Customer statement"
            description="Invoices debit the customer, payments credit them, in date order."
          />
          <Toolbar>
            <Select
              label="Customer"
              value={customerId}
              onChange={(event) => setCustomerId(event.target.value)}
            >
              <option value="">Choose a customer…</option>
              {(customers.data ?? []).map((customer) => (
                <option key={customer.id} value={customer.id}>
                  {customer.name}
                </option>
              ))}
            </Select>
          </Toolbar>

          {!customerId ? (
            <CardBody>
              <p className={styles.muted}>
                Pick a customer to see their running balance.
              </p>
            </CardBody>
          ) : (
            <QueryState
              isLoading={ledger.isLoading}
              error={ledger.error}
              onRetry={ledger.refetch}
              loadingHeight={220}
            >
              <>
                <CardBody>
                  <StatGrid>
                    <StatCard
                      label="Closing balance"
                      tone={
                        Number(ledger.data?.closing_balance ?? 0) > 0
                          ? 'warning'
                          : 'positive'
                      }
                      value={formatCurrency(ledger.data?.closing_balance ?? '0')}
                      hint="What the customer owes today"
                    />
                    <StatCard
                      label="Credit limit"
                      value={formatCurrency(ledger.data?.credit_limit ?? '0')}
                    />
                    <StatCard
                      label="Credit available"
                      tone={
                        Number(ledger.data?.available_credit ?? 0) < 0
                          ? 'danger'
                          : 'default'
                      }
                      value={formatCurrency(ledger.data?.available_credit ?? '0')}
                      hint="Limit minus balance"
                    />
                  </StatGrid>
                </CardBody>
                <DataTable<LedgerRow>
                  rows={ledger.data?.rows ?? []}
                  rowKey={(row) => `${row.entry_date}-${row.reference}-${row.kind}`}
                  emptyTitle="No transactions"
                  emptyDescription="This customer has no invoices or payments yet."
                  columns={[
                    {
                      key: 'date',
                      header: 'Date',
                      render: (row) => formatDate(row.entry_date),
                    },
                    {
                      key: 'reference',
                      header: 'Reference',
                      render: (row) => (
                        <span className={styles.primaryCell}>
                          <span>{row.reference}</span>
                          <span className={styles.muted}>{row.kind}</span>
                        </span>
                      ),
                    },
                    {
                      key: 'debit',
                      header: 'Debit',
                      numeric: true,
                      render: (row) =>
                        Number(row.debit) > 0 ? formatCurrency(row.debit) : '—',
                    },
                    {
                      key: 'credit',
                      header: 'Credit',
                      numeric: true,
                      render: (row) =>
                        Number(row.credit) > 0 ? formatCurrency(row.credit) : '—',
                    },
                    {
                      key: 'balance',
                      header: 'Balance',
                      numeric: true,
                      render: (row) => (
                        <strong>{formatCurrency(row.running_balance)}</strong>
                      ),
                    },
                  ]}
                />
              </>
            </QueryState>
          )}
        </Card>
      ) : null}
    </>
  );
}
