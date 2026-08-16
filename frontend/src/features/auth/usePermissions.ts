'use client';

import { useMemo } from 'react';
import { useMe } from './useAuth';

export interface PermissionSet {
  /** True while the session is still being resolved. */
  isLoading: boolean;
  isOwner: boolean;
  can: (code: string) => boolean;
  canAny: (...codes: string[]) => boolean;
  canAll: (...codes: string[]) => boolean;
  permissions: ReadonlySet<string>;
}

/**
 * Reads the permission list off the current session. Owners implicitly hold
 * every permission, mirroring the backend rule, so new permissions never lock
 * the owner out of their own system.
 */
export function usePermissions(): PermissionSet {
  const { data, isLoading } = useMe();

  return useMemo(() => {
    const isOwner = data?.is_owner ?? false;
    const permissions = new Set(data?.permissions ?? []);
    const can = (code: string) => isOwner || permissions.has(code);
    return {
      isLoading,
      isOwner,
      permissions,
      can,
      canAny: (...codes: string[]) => codes.some(can),
      canAll: (...codes: string[]) => codes.every(can),
    };
  }, [data, isLoading]);
}
