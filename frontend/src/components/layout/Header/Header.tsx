'use client';

import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { Icon } from '@/components/ui/Icon';
import { NotificationBell } from '@/features/notifications/NotificationBell';
import { useLogout, useMe } from '@/features/auth/useAuth';
import { locales } from '@/lib/i18n';
import { setLocale, setMobileNavOpen } from '@/store/uiSlice';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import styles from './Header.module.scss';

interface HeaderProps {
  title: string;
}

/** Sticky top bar: mobile nav trigger, page title, language, alerts, account. */
export function Header({ title }: HeaderProps) {
  const dispatch = useAppDispatch();
  const router = useRouter();
  const locale = useAppSelector((state) => state.ui.locale);
  const mobileNavOpen = useAppSelector((state) => state.ui.mobileNavOpen);
  const { data: user } = useMe();
  const logout = useLogout();
  const [menuOpen, setMenuOpen] = useState(false);

  const onLogout = async () => {
    await logout.mutateAsync();
    router.replace('/');
  };

  return (
    <header className={`${styles.header} no-print`}>
      <div className={styles.left}>
        <button
          type="button"
          className={styles.iconButton}
          aria-label="Open navigation"
          aria-expanded={mobileNavOpen}
          onClick={() => dispatch(setMobileNavOpen(!mobileNavOpen))}
        >
          <Icon name="menu" size={20} />
        </button>
        <h1 className={styles.title}>{title}</h1>
      </div>

      <div className={styles.right}>
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

        <NotificationBell />

        <div className={styles.account}>
          <button
            type="button"
            className={styles.accountButton}
            aria-expanded={menuOpen}
            aria-haspopup="menu"
            onClick={() => setMenuOpen((open) => !open)}
          >
            <span className={styles.avatar} aria-hidden="true">
              {(user?.full_name ?? '?').charAt(0).toUpperCase()}
            </span>
            <span className={styles.accountName}>{user?.full_name ?? 'Account'}</span>
            <Icon name="chevronDown" size={14} />
          </button>

          {menuOpen ? (
            <>
              <button
                type="button"
                className={styles.menuScrim}
                aria-label="Close account menu"
                onClick={() => setMenuOpen(false)}
              />
              <div className={styles.menu} role="menu">
                <div className={styles.menuHeader}>
                  <p className={styles.menuName}>{user?.full_name}</p>
                  <p className={styles.menuEmail}>{user?.email}</p>
                </div>
                <button
                  type="button"
                  role="menuitem"
                  className={styles.menuItem}
                  onClick={onLogout}
                  disabled={logout.isPending}
                >
                  <Icon name="logout" size={16} />
                  {logout.isPending ? 'Signing out…' : 'Sign out'}
                </button>
              </div>
            </>
          ) : null}
        </div>
      </div>
    </header>
  );
}
