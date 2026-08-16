'use client';

import { useQuery } from '@tanstack/react-query';
import { fetchDashboard } from './api';

/** Owner metrics. Only queried when the role holds `report.view`, so roles
 * without it get a dashboard built from the panels they can see instead. */
export function useDashboard(enabled = true) {
  return useQuery({
    queryKey: ['dashboard'],
    queryFn: fetchDashboard,
    refetchInterval: 60_000,
    enabled,
  });
}
