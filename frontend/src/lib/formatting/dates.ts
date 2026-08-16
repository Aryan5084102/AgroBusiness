// Date/quantity display helpers. The backend sends ISO dates and decimal
// strings; nothing here does arithmetic on money.

const dayMonth = new Intl.DateTimeFormat('en-IN', { day: '2-digit', month: 'short' });
const fullDate = new Intl.DateTimeFormat('en-IN', {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
});
const dateTime = new Intl.DateTimeFormat('en-IN', {
  day: '2-digit',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
});

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? '—' : fullDate.format(date);
}

export function formatShortDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? '—' : dayMonth.format(date);
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? '—' : dateTime.format(date);
}

/** Today as `YYYY-MM-DD`, for date inputs and report ranges. */
export function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

/**
 * Trims the trailing zeros the database returns on numeric columns
 * (`120.000` → `120`) so quantity columns stay readable.
 */
export function formatQuantity(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return '—';
  const numeric = typeof value === 'string' ? Number(value) : value;
  if (Number.isNaN(numeric)) return String(value);
  return numeric.toLocaleString('en-IN', { maximumFractionDigits: 3 });
}
