'use client';

import { locales } from '@/lib/i18n';
import { setLocale, toggleSidebar } from '@/store/uiSlice';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import styles from './Header.module.scss';

interface HeaderProps {
  title: string;
}

// Sticky top header: sidebar toggle, page title, locale switch (EN/HI).
export function Header({ title }: HeaderProps) {
  const dispatch = useAppDispatch();
  const locale = useAppSelector((state) => state.ui.locale);

  return (
    <header className={styles.header}>
      <div className={styles.left}>
        <button
          type="button"
          className={styles.iconButton}
          aria-label="Toggle navigation"
          onClick={() => dispatch(toggleSidebar())}
        >
          ☰
        </button>
        <h1 className={styles.title}>{title}</h1>
      </div>

      <div className={styles.localeSwitch} role="group" aria-label="Language">
        {locales.map((code) => (
          <button
            key={code}
            type="button"
            className={`${styles.localeButton} ${locale === code ? styles.active : ''}`}
            aria-pressed={locale === code}
            onClick={() => dispatch(setLocale(code))}
          >
            {code.toUpperCase()}
          </button>
        ))}
      </div>
    </header>
  );
}
