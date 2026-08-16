'use client';

import { useQuery } from '@tanstack/react-query';
import { fetchAuditLogs } from './api';

export function useAuditLogs(
  params: { action?: string; limit?: number; offset?: number },
  enabled = true,
) {
  return useQuery({
    queryKey: ['audit', 'logs', params],
    queryFn: () => fetchAuditLogs(params),
    enabled,
  });
}
