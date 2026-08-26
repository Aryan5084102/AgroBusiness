// "Amount in words" for printed tax invoices, in the Indian numbering system
// (thousand → lakh → crore), which Intl does not provide.
//
// Presentation only: the value is parsed from the backend's decimal string and
// never fed back into any calculation.

const ONES = [
  '',
  'One',
  'Two',
  'Three',
  'Four',
  'Five',
  'Six',
  'Seven',
  'Eight',
  'Nine',
  'Ten',
  'Eleven',
  'Twelve',
  'Thirteen',
  'Fourteen',
  'Fifteen',
  'Sixteen',
  'Seventeen',
  'Eighteen',
  'Nineteen',
];

const TENS = [
  '',
  '',
  'Twenty',
  'Thirty',
  'Forty',
  'Fifty',
  'Sixty',
  'Seventy',
  'Eighty',
  'Ninety',
];

// `noUncheckedIndexedAccess` types every lookup as possibly undefined; the
// callers below already bound n to the table, so an empty string is the right
// (unreachable) fallback.
function word(table: readonly string[], index: number): string {
  return table[index] ?? '';
}

/** 0–99 as words. */
function twoDigits(n: number): string {
  if (n < 20) return word(ONES, n);
  const tens = word(TENS, Math.floor(n / 10));
  const ones = word(ONES, n % 10);
  return ones ? `${tens} ${ones}` : tens;
}

/** 0–999 as words. */
function threeDigits(n: number): string {
  const hundreds = Math.floor(n / 100);
  const rest = n % 100;
  const parts: string[] = [];
  if (hundreds) parts.push(`${word(ONES, hundreds)} Hundred`);
  if (rest) parts.push(twoDigits(rest));
  return parts.join(' ');
}

/**
 * Whole number as words, grouped the Indian way: the lowest three digits, then
 * pairs of two (thousand, lakh, crore). Anything at or above 100 crore is
 * grouped into the crore bucket rather than inventing a larger unit.
 */
function wholeNumber(n: number): string {
  if (n === 0) return 'Zero';

  const parts: string[] = [];
  const crore = Math.floor(n / 10_000_000);
  const lakh = Math.floor((n % 10_000_000) / 100_000);
  const thousand = Math.floor((n % 100_000) / 1_000);
  const rest = n % 1_000;

  if (crore) parts.push(`${crore > 99 ? wholeNumber(crore) : twoDigits(crore)} Crore`);
  if (lakh) parts.push(`${twoDigits(lakh)} Lakh`);
  if (thousand) parts.push(`${twoDigits(thousand)} Thousand`);
  if (rest) parts.push(threeDigits(rest));

  return parts.join(' ');
}

/**
 * Rupee amount in words, e.g. `"826.50"` → `"Rupees Eight Hundred Twenty Six
 * and Fifty Paise Only"`. Returns an em dash for anything unparseable so a bill
 * never prints "NaN".
 */
export function amountInWords(amount: string | number): string {
  const value = typeof amount === 'string' ? Number(amount) : amount;
  if (!Number.isFinite(value) || value < 0) return '—';

  // Round to paise first: 826.999 must read as 827, not "826 and 100 Paise".
  const paiseTotal = Math.round(value * 100);
  const rupees = Math.floor(paiseTotal / 100);
  const paise = paiseTotal % 100;

  const head = `Rupees ${wholeNumber(rupees)}`;
  return paise > 0 ? `${head} and ${twoDigits(paise)} Paise Only` : `${head} Only`;
}
