'use client';

import { useUnreadNotifications } from './useNotifications';
import styles from './NotificationBell.module.scss';

// Header bell showing the unread notification count. Silent on error/loading.
export function NotificationBell() {
  const { data } = useUnreadNotifications();
  const count = data?.length ?? 0;

  return (
    <span
      className={styles.bell}
      aria-label={`${count} unread notifications`}
      title={`${count} unread notifications`}
    >
      🔔
      {count > 0 ? (
        <span className={styles.badge} aria-hidden="true">
          {count > 9 ? '9+' : count}
        </span>
      ) : null}
    </span>
  );
}
