'use client';

import type { ReactNode } from 'react';
import { Icon } from '@/components/ui/Icon/Icon';
import { Input } from '@/components/ui/Field/Field';
import styles from './Toolbar.module.scss';

interface ToolbarProps {
  children: ReactNode;
}

/** Filter/action strip that sits above a table. Wraps cleanly on small screens. */
export function Toolbar({ children }: ToolbarProps) {
  return <div className={styles.toolbar}>{children}</div>;
}

export function ToolbarSpacer() {
  return <span className={styles.spacer} />;
}

interface SearchInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  label?: string;
}

export function SearchInput({
  value,
  onChange,
  placeholder = 'Search…',
  label = 'Search',
}: SearchInputProps) {
  return (
    <div className={styles.search}>
      <Input
        label={label}
        hideLabel
        type="search"
        value={value}
        placeholder={placeholder}
        prefix={<Icon name="search" size={16} />}
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  );
}
