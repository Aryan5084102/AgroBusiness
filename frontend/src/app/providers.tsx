'use client';

import type { ReactNode } from 'react';
import { QueryProvider } from '@/lib/query/QueryProvider';
import { StoreProvider } from '@/store/StoreProvider';

// Client provider tree: Redux (UI/session state) + TanStack Query (server state).
export function Providers({ children }: { children: ReactNode }) {
  return (
    <StoreProvider>
      <QueryProvider>{children}</QueryProvider>
    </StoreProvider>
  );
}
