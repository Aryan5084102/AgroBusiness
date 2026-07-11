'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { navItems } from '@/components/layout/navItems';
import { createTranslator } from '@/lib/i18n';
import { useAppSelector } from '@/store/hooks';
import styles from './Sidebar.module.scss';

// Collapsible primary navigation. Active route is derived from the pathname.
export function Sidebar() {
  const pathname = usePathname();
  const { locale, sidebarCollapsed } = useAppSelector((state) => state.ui);
  const t = createTranslator(locale);

  return (
    <aside
      className={`${styles.sidebar} ${sidebarCollapsed ? styles.collapsed : ''}`}
      aria-label="Primary"
    >
      <div className={styles.brand}>{sidebarCollapsed ? 'AF' : 'AgriFlow'}</div>
      <nav>
        <ul role="list" className={styles.list}>
          {navItems.map((item) => {
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={`${styles.link} ${active ? styles.active : ''}`}
                  aria-current={active ? 'page' : undefined}
                >
                  {sidebarCollapsed ? t(item.labelKey).charAt(0) : t(item.labelKey)}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </aside>
  );
}
