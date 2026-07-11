'use client';

import type { ReactNode } from 'react';
import { Header } from '@/components/layout/Header/Header';
import { Sidebar } from '@/components/layout/Sidebar/Sidebar';
import styles from './AppShell.module.scss';

interface AppShellProps {
  title: string;
  children: ReactNode;
}

// Authenticated application shell: sidebar + sticky header + scrollable content.
export function AppShell({ title, children }: AppShellProps) {
  return (
    <div className={styles.shell}>
      <Sidebar />
      <div className={styles.main}>
        <Header title={title} />
        <main className={styles.content}>{children}</main>
      </div>
    </div>
  );
}
