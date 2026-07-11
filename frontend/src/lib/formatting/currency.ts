// Indian-rupee currency formatting. Amounts arrive as decimal strings from the
// backend (never float) — we format for display only and never do math here.
const inr = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function formatCurrency(amount: string | number): string {
  const value = typeof amount === 'string' ? Number(amount) : amount;
  if (Number.isNaN(value)) return '—';
  return inr.format(value);
}

export function formatPercent(rate: string | number): string {
  const value = typeof rate === 'string' ? Number(rate) : rate;
  if (Number.isNaN(value)) return '—';
  return `${value}%`;
}
