import type { ReactNode } from 'react';
import styles from './Card.module.scss';

interface CardProps {
  children: ReactNode;
  className?: string;
}

/**
 * Surface container: white panel, hairline border, subtle elevation.
 *
 * Content that needs padding goes in a <CardBody>; a table placed directly in
 * the card sits flush against its edges, which is what list screens want.
 */
export function Card({ children, className }: CardProps) {
  return (
    <section className={[styles.card, className ?? ''].filter(Boolean).join(' ')}>
      {children}
    </section>
  );
}

interface CardHeaderProps {
  title: string;
  description?: string;
  actions?: ReactNode;
}

export function CardHeader({ title, description, actions }: CardHeaderProps) {
  return (
    <header className={styles.header}>
      <div className={styles.headings}>
        <h3 className={styles.title}>{title}</h3>
        {description ? <p className={styles.description}>{description}</p> : null}
      </div>
      {actions ? <div className={styles.actions}>{actions}</div> : null}
    </header>
  );
}

export function CardBody({ children }: { children: ReactNode }) {
  return <div className={styles.body}>{children}</div>;
}

export function CardFooter({ children }: { children: ReactNode }) {
  return <footer className={styles.footer}>{children}</footer>;
}
