'use client';

import { useQuery } from '@tanstack/react-query';
import { fetchHealth } from './api';

export function useHealth() {
  return useQuery({
    queryKey: ['system-health'],
    queryFn: fetchHealth,
    refetchInterval: 15_000,
    retry: 1,
  });
}
