'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Icon } from '@/components/ui/Icon';
import { visibleGroups } from '@/components/layout/navItems';
import { useMe } from '@/features/auth/useAuth';
import { usePermissions } from '@/features/auth/usePermissions';
import { useOrgProfile } from '@/features/settings/useSettings';
import { setMobileNavOpen, toggleSidebar } from '@/store/uiSlice';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import styles from './Sidebar.module.scss';

/**
 * Primary navigation. Only shows the destinations the signed-in role can
 * actually use, grouped by task. On phones it becomes an overlay drawer driven
 * by `ui.mobileNavOpen`; on desktop it collapses to an icon rail.
 */
export function Sidebar() {
  const pathname = usePathname();
  const dispatch = useAppDispatch();
  const { sidebarCollapsed, mobileNavOpen } = useAppSelector((state) => state.ui);
  const { can } = usePermissions();
  const { data: user } = useMe();
  const { data: org } = useOrgProfile();

  const groups = visibleGroups(can);
  const initials = (org?.name ?? 'AgriFlow')
    .split(' ')
    .slice(0, 2)
    .map((word) => word.charAt(0).toUpperCase())
    .join('');

  return (
    <>
      {/* Tapping outside the drawer closes it — expected on touch devices. */}
      {mobileNavOpen ? (
        <button
          type="button"
          className={styles.scrim}
          aria-label="Close navigation"
          onClick={() => dispatch(setMobileNavOpen(false))}
        />
      ) : null}

      <aside
        className={[
          styles.sidebar,
          sidebarCollapsed ? styles.collapsed : '',
          mobileNavOpen ? styles.mobileOpen : '',
        ]
          .filter(Boolean)
          .join(' ')}
        aria-label="Sidebar"
      >
        <div className={styles.brand}>
          <span className={styles.mark} aria-hidden="true">
            {initials}
          </span>
          {sidebarCollapsed ? null : (
            <span className={styles.brandText}>
              <span className={styles.brandName}>{org?.name ?? 'AgriFlow ERP'}</span>
              <span className={styles.brandMeta}>Wholesale &amp; retail</span>
            </span>
          )}
        </div>

        <nav className={styles.nav} aria-label="Primary navigation">
          {groups.map((group) => (
            <div key={group.id} className={styles.group}>
              {sidebarCollapsed ? (
                <span className={styles.groupRule} aria-hidden="true" />
              ) : (
                <p className={styles.groupLabel}>{group.label}</p>
              )}
              <ul role="list" className={styles.list}>
                {group.items.map((item) => {
                  const active =
                    pathname === item.href || pathname.startsWith(`${item.href}/`);
                  return (
                    <li key={item.href}>
                      <Link
                        href={item.href}
                        className={`${styles.link} ${active ? styles.active : ''}`}
                        aria-current={active ? 'page' : undefined}
                        title={sidebarCollapsed ? item.label : undefined}
                        onClick={() => dispatch(setMobileNavOpen(false))}
                      >
                        <Icon name={item.icon} size={18} />
                        {sidebarCollapsed ? null : <span>{item.label}</span>}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>

        <div className={styles.footer}>
          {sidebarCollapsed ? null : (
            <div className={styles.identity}>
              <span className={styles.avatar} aria-hidden="true">
                {(user?.full_name ?? '?').charAt(0).toUpperCase()}
              </span>
              <span className={styles.identityText}>
                <span className={styles.identityName}>{user?.full_name}</span>
                <span className={styles.identityRole}>
                  {user?.is_owner
                    ? 'Owner'
                    : `${user?.permissions.length ?? 0} permissions`}
                </span>
              </span>
            </div>
          )}
          <button
            type="button"
            className={styles.collapse}
            onClick={() => dispatch(toggleSidebar())}
            aria-label={sidebarCollapsed ? 'Expand navigation' : 'Collapse navigation'}
          >
            <Icon name={sidebarCollapsed ? 'chevronRight' : 'chevronLeft'} size={16} />
          </button>
        </div>
      </aside>
    </>
  );
}
