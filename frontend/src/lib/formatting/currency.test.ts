import { describe, expect, it } from 'vitest';
import { formatCurrency, formatPercent } from './currency';

describe('formatCurrency', () => {
  it('formats a decimal string as INR (₹ + grouped 2dp)', () => {
    const out = formatCurrency('1234.5');
    expect(out).toContain('₹');
    expect(out).toContain('1,234.50');
  });

  it('returns an em dash for invalid input', () => {
    expect(formatCurrency('not-a-number')).toBe('—');
  });
});

describe('formatPercent', () => {
  it('appends a percent sign', () => {
    expect(formatPercent('18')).toBe('18%');
  });
});
