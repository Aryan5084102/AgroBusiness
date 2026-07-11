// Notifications feature API.
import { apiFetch } from '@/lib/api/client';

export interface Notification {
  id: string;
  type: string;
  title: string;
  body: string | null;
  is_read: boolean;
  created_at: string;
}

export function fetchNotifications(unreadOnly = false): Promise<Notification[]> {
  const params = unreadOnly ? '?unread_only=true' : '';
  return apiFetch<Notification[]>(`/api/v1/notifications${params}`);
}
