'use client';

import type { ReactNode } from 'react';
import { ToastProvider } from '@/components/ui/Toast';
import { QueryProvider } from '@/lib/query/QueryProvider';
import { StoreProvider } from '@/store/StoreProvider';

// Client provider tree: Redux (UI state) + TanStack Query (server state) +
// toasts, so any screen can report the outcome of a mutation consistently.
export function Providers({ children }: { children: ReactNode }) {
  return (
    <StoreProvider>
      <QueryProvider>
        <ToastProvider>{children}</ToastProvider>
      </QueryProvider>
    </StoreProvider>
  );
}
