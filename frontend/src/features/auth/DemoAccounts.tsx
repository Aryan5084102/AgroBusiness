'use client';

import { DEMO_ACCOUNTS, DEMO_PASSWORD, showDemoAccounts } from './demoAccounts';
import styles from './DemoAccounts.module.scss';

interface DemoAccountsProps {
  onPick: (email: string, password: string) => void;
  disabled?: boolean;
}

// Dev-only panel: one click fills + submits the login for a demo role.
export function DemoAccounts({ onPick, disabled }: DemoAccountsProps) {
  if (!showDemoAccounts) return null;

  return (
    <section className={styles.wrap} aria-label="Demo accounts">
      <p className={styles.heading}>
        Demo accounts <span className={styles.tag}>development</span>
      </p>
      <p className={styles.hint}>
        Click a role to sign in. Password for all: <code>{DEMO_PASSWORD}</code>
      </p>
      <div className={styles.grid}>
        {DEMO_ACCOUNTS.map((acc) => (
          <button
            key={acc.email}
            type="button"
            className={styles.account}
            disabled={disabled}
            onClick={() => onPick(acc.email, DEMO_PASSWORD)}
          >
            <span className={styles.label}>{acc.label}</span>
            <span className={styles.email}>{acc.email}</span>
          </button>
        ))}
      </div>
    </section>
  );
}
