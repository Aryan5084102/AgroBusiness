'use client';

import { useRouter } from 'next/navigation';
import { useEffect, type ReactNode } from 'react';
import { useMe } from './useAuth';

/**
 * Client-side guard for authenticated areas. Redirects to the landing/login page
 * when there is no valid session. Server-side enforcement still lives on every
 * API route — this only controls what the browser renders.
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { data, isLoading, isError } = useMe();

  useEffect(() => {
    if (!isLoading && (isError || !data)) {
      router.replace('/');
    }
  }, [isLoading, isError, data, router]);

  if (isLoading) {
    return <div style={{ padding: 24 }}>Loading…</div>;
  }
  if (isError || !data) {
    return null;
  }
  return <>{children}</>;
}
