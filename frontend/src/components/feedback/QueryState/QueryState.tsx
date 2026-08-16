'use client';

import type { ReactNode } from 'react';
import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { Skeleton } from '@/components/ui/Skeleton';
import { ApiError } from '@/lib/api/client';

interface QueryStateProps {
  isLoading: boolean;
  error: unknown;
  onRetry?: () => void;
  children: ReactNode;
  /** Height of the loading placeholder block. */
  loadingHeight?: number;
}

/**
 * Wraps a TanStack Query result so every screen handles loading and failure the
 * same way: a sized skeleton, then a readable error with a retry — never a
 * blank panel and never a raw exception message.
 */
export function QueryState({
  isLoading,
  error,
  onRetry,
  children,
  loadingHeight = 180,
}: QueryStateProps) {
  if (isLoading) {
    return <Skeleton height={loadingHeight} />;
  }
  if (error) {
    const isPermission = error instanceof ApiError && error.status === 403;
    return (
      <EmptyState
        tone="danger"
        icon={isPermission ? 'lock' : 'alert'}
        title={
          isPermission ? 'You do not have access to this data' : 'Could not load this'
        }
        description={
          error instanceof ApiError
            ? error.message
            : 'The server could not be reached. Check your connection and try again.'
        }
        action={
          onRetry && !isPermission ? (
            <Button variant="secondary" size="sm" onClick={onRetry}>
              Try again
            </Button>
          ) : null
        }
      />
    );
  }
  return <>{children}</>;
}
