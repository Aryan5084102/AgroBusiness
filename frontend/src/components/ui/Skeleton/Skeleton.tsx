import styles from './Skeleton.module.scss';

interface SkeletonProps {
  height?: number;
  width?: string | number;
  radius?: number;
}

/** Loading placeholder. Sized to the content it replaces so the layout doesn't
 * jump when real data arrives. */
export function Skeleton({ height = 16, width = '100%', radius = 6 }: SkeletonProps) {
  return (
    <span
      className={styles.skeleton}
      style={{ height, width, borderRadius: radius }}
      aria-hidden="true"
    />
  );
}

export function SkeletonText({ lines = 3 }: { lines?: number }) {
  return (
    <span className={styles.stack}>
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton key={i} height={12} width={i === lines - 1 ? '60%' : '100%'} />
      ))}
    </span>
  );
}
