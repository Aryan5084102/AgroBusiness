'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, type ReactNode } from 'react';
import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { Skeleton } from '@/components/ui/Skeleton';
import { defaultRouteFor } from '@/components/layout/navItems';
import { usePermissions } from './usePermissions';
import { useMe } from './useAuth';
import styles from './RequireAuth.module.scss';

interface RequireAuthProps {
  children: ReactNode;
  /** The user needs at least one of these to see the page. */
  permissions?: string[];
}

/**
 * Client-side guard for authenticated areas. Redirects to the login page when
 * there is no session, and renders a clear "no access" screen — rather than a
 * failed request — when the role lacks the page's permission. Server-side
 * enforcement still lives on every API route; this only controls rendering.
 */
export function RequireAuth({ children, permissions = [] }: RequireAuthProps) {
  const router = useRouter();
  const { data, isLoading, isError } = useMe();
  const { can } = usePermissions();

  useEffect(() => {
    if (!isLoading && (isError || !data)) {
      router.replace('/');
    }
  }, [isLoading, isError, data, router]);

  if (isLoading) {
    return (
      <div className={styles.loading}>
        <Skeleton height={56} />
        <Skeleton height={180} />
        <Skeleton height={280} />
      </div>
    );
  }

  if (isError || !data) {
    return null;
  }

  const allowed = permissions.length === 0 || permissions.some(can);
  if (!allowed) {
    const fallback = defaultRouteFor(can);
    return (
      <div className={styles.denied}>
        <EmptyState
          tone="danger"
          icon="lock"
          title="You do not have access to this page"
          description="Your role does not include the permission this screen needs. Ask an administrator if you think this is wrong."
          action={
            <Link href={fallback}>
              <Button variant="secondary">Go to my start page</Button>
            </Link>
          }
        />
      </div>
    );
  }

  return <>{children}</>;
}
