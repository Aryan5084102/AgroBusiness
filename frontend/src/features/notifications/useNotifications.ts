'use client';

import { useQuery } from '@tanstack/react-query';
import { fetchNotifications } from './api';

export function useUnreadNotifications() {
  return useQuery({
    queryKey: ['notifications', 'unread'],
    queryFn: () => fetchNotifications(true),
    refetchInterval: 60_000,
    retry: false,
  });
}
