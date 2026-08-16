'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchNotifications, markNotificationRead } from './api';

export function useUnreadNotifications() {
  return useQuery({
    queryKey: ['notifications', 'unread'],
    queryFn: () => fetchNotifications(true),
    refetchInterval: 60_000,
    retry: false,
  });
}

export function useNotifications(enabled = true) {
  return useQuery({
    queryKey: ['notifications', 'all'],
    queryFn: () => fetchNotifications(false),
    retry: false,
    enabled,
  });
}

export function useMarkRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (notificationId: string) => markNotificationRead(notificationId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notifications'] }),
  });
}
