import styles from './ComingSoon.module.scss';

interface ComingSoonProps {
  feature: string;
  note?: string;
}

// Placeholder for screens whose backend is ready but UI is not yet built.
export function ComingSoon({ feature, note }: ComingSoonProps) {
  return (
    <div className={styles.wrap}>
      <p className={styles.badge}>In progress</p>
      <h3 className={styles.title}>{feature}</h3>
      <p className={styles.note}>
        {note ??
          'The backend for this module is implemented and tested; the screen is being built.'}
      </p>
    </div>
  );
}
