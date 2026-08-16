'use client';

import { useState } from 'react';
import { Icon } from '@/components/ui/Icon';
import { formatDateTime } from '@/lib/formatting/dates';
import {
  useMarkRead,
  useNotifications,
  useUnreadNotifications,
} from './useNotifications';
import styles from './NotificationBell.module.scss';

/** Header bell with an unread count and a dropdown of recent alerts. Silent on
 * error so a notification outage never blocks the rest of the app. */
export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const unread = useUnreadNotifications();
  const all = useNotifications(open);
  const markRead = useMarkRead();

  const count = unread.data?.length ?? 0;
  const items = all.data ?? unread.data ?? [];

  return (
    <div className={styles.wrap}>
      <button
        type="button"
        className={styles.bell}
        aria-label={`Notifications: ${count} unread`}
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <Icon name="bell" size={18} />
        {count > 0 ? (
          <span className={styles.badge} aria-hidden="true">
            {count > 9 ? '9+' : count}
          </span>
        ) : null}
      </button>

      {open ? (
        <>
          <button
            type="button"
            className={styles.scrim}
            aria-label="Close notifications"
            onClick={() => setOpen(false)}
          />
          <div className={styles.panel} role="dialog" aria-label="Notifications">
            <p className={styles.title}>Notifications</p>
            {items.length === 0 ? (
              <p className={styles.empty}>Nothing needs your attention right now.</p>
            ) : (
              <ul role="list" className={styles.list}>
                {items.slice(0, 8).map((notification) => (
                  <li
                    key={notification.id}
                    className={notification.is_read ? styles.read : styles.unread}
                  >
                    <span className={styles.itemTitle}>{notification.title}</span>
                    {notification.body ? (
                      <span className={styles.itemBody}>{notification.body}</span>
                    ) : null}
                    <span className={styles.itemMeta}>
                      {formatDateTime(notification.created_at)}
                      {notification.is_read ? null : (
                        <button
                          type="button"
                          className={styles.markRead}
                          onClick={() => markRead.mutate(notification.id)}
                        >
                          Mark read
                        </button>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      ) : null}
    </div>
  );
}
