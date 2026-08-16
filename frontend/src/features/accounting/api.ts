// Accounting API: trial balance, journal register, customer statement.
import { apiFetch } from '@/lib/api/client';

export type AccountType = 'asset' | 'liability' | 'income' | 'expense' | 'equity';

export interface TrialBalanceRow {
  account_code: string;
  account_name: string;
  account_type: AccountType;
  debit: string;
  credit: string;
  balance: string;
}

export interface TrialBalance {
  rows: TrialBalanceRow[];
  total_debit: string;
  total_credit: string;
  is_balanced: boolean;
}

export interface JournalLine {
  account_code: string;
  account_name: string;
  debit: string;
  credit: string;
}

export interface JournalEntry {
  id: string;
  entry_date: string;
  narration: string | null;
  source_document_type: string | null;
  source_document_id: string | null;
  total: string;
  lines: JournalLine[];
}

export interface JournalPage {
  items: JournalEntry[];
  total: number;
  limit: number;
  offset: number;
}

export interface LedgerRow {
  entry_date: string;
  kind: string;
  reference: string;
  debit: string;
  credit: string;
  running_balance: string;
}

export interface CustomerLedger {
  customer_id: string;
  customer_name: string;
  opening_balance: string;
  rows: LedgerRow[];
  closing_balance: string;
  credit_limit: string;
  available_credit: string;
}

export function fetchTrialBalance(): Promise<TrialBalance> {
  return apiFetch<TrialBalance>('/api/v1/accounting/trial-balance');
}

export function fetchJournals(limit = 25, offset = 0): Promise<JournalPage> {
  return apiFetch<JournalPage>(
    `/api/v1/accounting/journals?limit=${limit}&offset=${offset}`,
  );
}

export function fetchCustomerLedger(customerId: string): Promise<CustomerLedger> {
  return apiFetch<CustomerLedger>(`/api/v1/accounting/customers/${customerId}/ledger`);
}
