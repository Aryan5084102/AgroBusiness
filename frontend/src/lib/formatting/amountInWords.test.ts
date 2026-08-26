import { describe, expect, it } from 'vitest';
import { amountInWords } from './amountInWords';

describe('amountInWords', () => {
  it('writes whole rupees', () => {
    expect(amountInWords('826.00')).toBe('Rupees Eight Hundred Twenty Six Only');
    expect(amountInWords('0')).toBe('Rupees Zero Only');
    expect(amountInWords('7')).toBe('Rupees Seven Only');
  });

  it('writes paise when there are any', () => {
    expect(amountInWords('826.50')).toBe(
      'Rupees Eight Hundred Twenty Six and Fifty Paise Only',
    );
    expect(amountInWords('1.05')).toBe('Rupees One and Five Paise Only');
  });

  it('groups the Indian way — thousand, lakh, crore', () => {
    expect(amountInWords('1000')).toBe('Rupees One Thousand Only');
    expect(amountInWords('125000')).toBe('Rupees One Lakh Twenty Five Thousand Only');
    expect(amountInWords('10000000')).toBe('Rupees One Crore Only');
    expect(amountInWords('12345678')).toBe(
      'Rupees One Crore Twenty Three Lakh Forty Five Thousand Six Hundred Seventy Eight Only',
    );
  });

  it('handles the teens, which are not tens-plus-ones', () => {
    expect(amountInWords('15')).toBe('Rupees Fifteen Only');
    expect(amountInWords('19000')).toBe('Rupees Nineteen Thousand Only');
  });

  // A bill must never print "and 100 Paise": rounding happens on the paise
  // total, so the rupee part carries the increment.
  it('rounds up into rupees rather than overflowing paise', () => {
    expect(amountInWords('826.999')).toBe('Rupees Eight Hundred Twenty Seven Only');
  });

  it('returns a dash for values it cannot render', () => {
    expect(amountInWords('not a number')).toBe('—');
    expect(amountInWords('-5')).toBe('—');
  });
});
