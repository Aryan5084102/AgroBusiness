'use client';

import { formatCurrency } from '@/lib/formatting/currency';
import styles from './BarChart.module.scss';

export interface BarPoint {
  label: string;
  value: number;
  /** Longer text shown in the tooltip/title. */
  title?: string;
}

interface BarChartProps {
  points: BarPoint[];
  /** Formats the value in tooltips and the axis cap. Defaults to rupees. */
  format?: (value: number) => string;
  height?: number;
}

/**
 * Minimal CSS bar chart — no charting dependency for what is a single series of
 * daily totals. Bars carry an accessible label, and the data is also exposed as
 * a visually-hidden table so it is readable by screen readers.
 */
export function BarChart({
  points,
  format = formatCurrency,
  height = 140,
}: BarChartProps) {
  const max = Math.max(...points.map((p) => p.value), 1);
  // Thin the axis labels so they never collide or clip: with a fortnight of
  // data every other day is enough to read the shape, and the last day always
  // gets a tick so "today" is identifiable.
  const tickEvery = points.length > 10 ? 3 : points.length > 6 ? 2 : 1;

  return (
    <figure className={styles.chart}>
      <div className={styles.plot} style={{ height }}>
        {points.map((point, index) => {
          const ratio = point.value / max;
          const showTick = index % tickEvery === 0 || index === points.length - 1;
          return (
            <div key={point.label} className={styles.column}>
              <div
                className={styles.bar}
                // Keep a small stub for zero days so the axis reads as continuous.
                style={{ height: `${Math.max(ratio * 100, 1.5)}%` }}
                title={point.title ?? `${point.label}: ${format(point.value)}`}
              />
              <span className={styles.tick}>{showTick ? point.label : ' '}</span>
            </div>
          );
        })}
      </div>
      <figcaption className={styles.caption}>
        Peak <span className="tabular-nums">{format(max)}</span>
      </figcaption>
      <table className={styles.srOnly}>
        <caption>Daily totals</caption>
        <tbody>
          {points.map((point) => (
            <tr key={point.label}>
              <th scope="row">{point.label}</th>
              <td>{format(point.value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}
