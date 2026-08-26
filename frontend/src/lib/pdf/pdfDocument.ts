// A very small PDF writer — just enough to lay out a printed tax invoice.
//
// A bill is text, rules and a few filled boxes, all of it in the base-14
// Helvetica faces every PDF reader already has, so the file is assembled by
// hand rather than pulling a PDF library (and its fonts) into the bundle.
//
// Limitation: base-14 fonts are Latin-1 only, so a name in Devanagari cannot be
// drawn here. The browser-print bill at `/invoices/[id]/bill` renders any
// script and stays the fallback for those.

const A4_WIDTH = 595.28;
const A4_HEIGHT = 841.89;

export type FontKey = 'regular' | 'bold';

/**
 * Advance widths (per 1000 units) for printable ASCII, taken from the Adobe
 * Helvetica metrics. Only used to align right-hand columns and wrap long
 * names — a wrong width would misalign a column, never corrupt the file.
 */
const HELVETICA: readonly number[] = [
  278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278, 556,
  556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556, 1015, 667,
  667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778, 667, 778, 722,
  667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556, 333, 556, 556, 500,
  556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556, 556, 556, 333, 500, 278,
  556, 500, 722, 500, 500, 500, 334, 260, 334, 584,
];

const HELVETICA_BOLD: readonly number[] = [
  278, 333, 474, 556, 556, 889, 722, 238, 333, 333, 389, 584, 278, 333, 278, 278, 556,
  556, 556, 556, 556, 556, 556, 556, 556, 556, 333, 333, 584, 584, 584, 611, 975, 722,
  722, 722, 722, 667, 611, 778, 722, 278, 556, 722, 611, 833, 722, 778, 667, 778, 722,
  667, 611, 722, 667, 944, 667, 667, 611, 333, 278, 333, 584, 556, 333, 556, 611, 556,
  611, 556, 333, 611, 611, 278, 278, 556, 278, 889, 611, 611, 611, 611, 389, 556, 333,
  611, 556, 778, 556, 556, 500, 389, 280, 389, 584,
];

const WIDTHS: Record<FontKey, readonly number[]> = {
  regular: HELVETICA,
  bold: HELVETICA_BOLD,
};

const FALLBACK_WIDTH = 556;

// Punctuation the app renders that WinAnsiEncoding has no glyph for, mapped to
// the nearest ASCII so a bill never prints a stray box.
const REPLACEMENTS: readonly (readonly [RegExp, string])[] = [
  [/₹/g, 'Rs. '], // ₹
  [/[‒-―−]/g, '-'], // – — −
  [/[‘’‛]/g, "'"],
  [/[“”]/g, '"'],
  [/[·•]/g, '-'], // · •
  [/…/g, '...'],
  [/×/g, 'x'],
  [/ /g, ' '],
];

/** Folds text down to what the base-14 fonts can actually draw. */
export function sanitize(value: string): string {
  let out = value;
  for (const [pattern, replacement] of REPLACEMENTS)
    out = out.replace(pattern, replacement);
  // 0x80–0x9f are control codes in Latin-1 and differ in WinAnsi; drop anything
  // outside the ranges both encodings agree on rather than draw the wrong glyph.
  return out.replace(/[^ -~¡-ÿ]/g, '?');
}

function charWidth(code: number, font: FontKey): number {
  if (code >= 32 && code <= 126) return WIDTHS[font][code - 32] ?? FALLBACK_WIDTH;
  return FALLBACK_WIDTH;
}

/** Width of already-sanitized text at a given size, in points. */
export function textWidth(value: string, font: FontKey, size: number): number {
  let total = 0;
  for (let i = 0; i < value.length; i += 1) total += charWidth(value.charCodeAt(i), font);
  return (total * size) / 1000;
}

/** Greedy word wrap. Words longer than `maxWidth` are hard-split. */
export function wrapText(
  value: string,
  font: FontKey,
  size: number,
  maxWidth: number,
): string[] {
  const clean = sanitize(value).trim();
  if (!clean) return [];
  const lines: string[] = [];
  let line = '';
  for (const word of clean.split(/\s+/)) {
    const candidate = line ? `${line} ${word}` : word;
    if (textWidth(candidate, font, size) <= maxWidth) {
      line = candidate;
      continue;
    }
    if (line) lines.push(line);
    line = word;
    while (textWidth(line, font, size) > maxWidth && line.length > 1) {
      let cut = line.length - 1;
      while (cut > 1 && textWidth(line.slice(0, cut), font, size) > maxWidth) cut -= 1;
      lines.push(line.slice(0, cut));
      line = line.slice(cut);
    }
  }
  if (line) lines.push(line);
  return lines;
}

function escapeText(value: string): string {
  return value.replace(/[\\()]/g, (match) => `\\${match}`);
}

/** Two decimals is plenty for page geometry, and keeps the stream small. */
function num(value: number): string {
  return String(Math.round(value * 100) / 100);
}

export interface TextOptions {
  font?: FontKey;
  size?: number;
  align?: 'left' | 'right' | 'center';
  /** 0 is black, 1 is white. */
  gray?: number;
}

/**
 * One A4 document. Coordinates are top-left based (y grows downward, the way
 * the layout code reads); the conversion to PDF's bottom-left space happens
 * here so no caller has to think about it.
 */
export class PdfDocument {
  readonly width = A4_WIDTH;
  readonly height = A4_HEIGHT;

  private readonly pages: string[][] = [];
  private current: string[] = [];

  constructor() {
    this.addPage();
  }

  addPage(): void {
    this.current = [];
    this.pages.push(this.current);
  }

  get pageCount(): number {
    return this.pages.length;
  }

  /** Runs `draw` once per page — for footers that need the final page count. */
  stampPages(draw: (doc: PdfDocument, page: number, total: number) => void): void {
    const total = this.pages.length;
    const active = this.current;
    this.pages.forEach((ops, index) => {
      this.current = ops;
      draw(this, index + 1, total);
    });
    this.current = active;
  }

  text(value: string, x: number, y: number, options: TextOptions = {}): void {
    const { font = 'regular', size = 9, align = 'left', gray = 0 } = options;
    const clean = sanitize(value);
    if (!clean) return;
    const offset =
      align === 'left' ? 0 : textWidth(clean, font, size) / (align === 'center' ? 2 : 1);
    this.current.push(
      `${num(gray)} g`,
      'BT',
      `/${font === 'bold' ? 'F2' : 'F1'} ${num(size)} Tf`,
      `1 0 0 1 ${num(x - offset)} ${num(this.height - y - size * 0.78)} Tm`,
      `(${escapeText(clean)}) Tj`,
      'ET',
    );
  }

  line(
    x1: number,
    y1: number,
    x2: number,
    y2: number,
    options: { width?: number; gray?: number } = {},
  ): void {
    const { width = 0.5, gray = 0.72 } = options;
    this.current.push(
      `${num(gray)} G`,
      `${num(width)} w`,
      `${num(x1)} ${num(this.height - y1)} m`,
      `${num(x2)} ${num(this.height - y2)} l`,
      'S',
    );
  }

  rect(
    x: number,
    y: number,
    width: number,
    height: number,
    options: { fill?: number; stroke?: number; lineWidth?: number } = {},
  ): void {
    const { fill, stroke, lineWidth = 0.5 } = options;
    if (fill === undefined && stroke === undefined) return;
    const ops: string[] = [];
    if (fill !== undefined) ops.push(`${num(fill)} g`);
    if (stroke !== undefined) ops.push(`${num(stroke)} G`, `${num(lineWidth)} w`);
    ops.push(
      `${num(x)} ${num(this.height - y - height)} ${num(width)} ${num(height)} re`,
      fill !== undefined && stroke !== undefined ? 'B' : fill !== undefined ? 'f' : 'S',
    );
    this.current.push(...ops);
  }

  /**
   * Serialises the document. Every byte is Latin-1, so a string index is also
   * a byte offset — which is what makes the hand-built xref table correct.
   */
  toBytes(): Uint8Array<ArrayBuffer> {
    const objects: string[] = [];
    const firstPageId = 5; // 1 catalog, 2 pages, 3–4 fonts
    const pageIds = this.pages.map((_, index) => firstPageId + index * 2);

    objects.push('<< /Type /Catalog /Pages 2 0 R >>');
    objects.push(
      `<< /Type /Pages /Kids [${pageIds
        .map((id) => `${id} 0 R`)
        .join(' ')}] /Count ${this.pages.length} >>`,
    );
    objects.push(
      '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>',
    );
    objects.push(
      '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>',
    );

    this.pages.forEach((ops, index) => {
      const contentId = firstPageId + index * 2 + 1;
      objects.push(
        `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${num(this.width)} ${num(
          this.height,
        )}] /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents ${contentId} 0 R >>`,
      );
      const stream = ops.join('\n');
      objects.push(`<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`);
    });

    let file = '%PDF-1.4\n';
    const offsets: number[] = [];
    objects.forEach((body, index) => {
      offsets.push(file.length);
      file += `${index + 1} 0 obj\n${body}\nendobj\n`;
    });

    const xrefStart = file.length;
    file += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
    for (const offset of offsets)
      file += `${String(offset).padStart(10, '0')} 00000 n \n`;
    file += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xrefStart}\n%%EOF\n`;

    const bytes = new Uint8Array(file.length);
    for (let i = 0; i < file.length; i += 1) bytes[i] = file.charCodeAt(i) & 0xff;
    return bytes;
  }
}
