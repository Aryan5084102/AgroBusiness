'use client';

import type { ReactNode } from 'react';
import { Icon, type IconName } from '@/components/ui/Icon/Icon';
import styles from './Tabs.module.scss';

export interface TabItem<T extends string> {
  id: T;
  label: string;
  icon?: IconName;
  /** Small count shown after the label (e.g. open jobs). */
  count?: number;
}

interface TabsProps<T extends string> {
  items: TabItem<T>[];
  active: T;
  onChange: (id: T) => void;
  label: string;
  children?: ReactNode;
}

/** Segmented tab bar. Arrow keys move between tabs, as expected of a tablist. */
export function Tabs<T extends string>({
  items,
  active,
  onChange,
  label,
  children,
}: TabsProps<T>) {
  const move = (delta: number) => {
    const index = items.findIndex((item) => item.id === active);
    const next = items[(index + delta + items.length) % items.length];
    if (next) onChange(next.id);
  };

  return (
    <>
      <div className={styles.tabs} role="tablist" aria-label={label}>
        {items.map((item) => {
          const selected = item.id === active;
          return (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={selected}
              tabIndex={selected ? 0 : -1}
              className={`${styles.tab} ${selected ? styles.active : ''}`}
              onClick={() => onChange(item.id)}
              onKeyDown={(event) => {
                if (event.key === 'ArrowRight') move(1);
                if (event.key === 'ArrowLeft') move(-1);
              }}
            >
              {item.icon ? <Icon name={item.icon} size={16} /> : null}
              {item.label}
              {item.count !== undefined ? (
                <span className={styles.count}>{item.count}</span>
              ) : null}
            </button>
          );
        })}
      </div>
      {children}
    </>
  );
}
