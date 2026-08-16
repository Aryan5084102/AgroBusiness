'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createBranch,
  createUser,
  createWarehouse,
  fetchBranches,
  fetchOrgProfile,
  fetchRoles,
  fetchUsers,
  fetchWarehouses,
  updateOrgProfile,
  updateUser,
  type CreateUserInput,
  type OrgProfile,
  type UpdateUserInput,
} from './api';

/** Org identity — used by the sidebar brand as well as the settings screen, so
 * it is cached generously. */
export function useOrgProfile() {
  return useQuery({
    queryKey: ['org', 'profile'],
    queryFn: fetchOrgProfile,
    staleTime: 5 * 60_000,
    retry: false,
  });
}

export function useUpdateOrgProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: Partial<OrgProfile>) => updateOrgProfile(input),
    onSuccess: (data) => {
      queryClient.setQueryData(['org', 'profile'], data);
    },
  });
}

export function useBranches(enabled = true) {
  return useQuery({ queryKey: ['org', 'branches'], queryFn: fetchBranches, enabled });
}

export function useCreateBranch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createBranch,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['org', 'branches'] }),
  });
}

export function useWarehouses(enabled = true) {
  return useQuery({ queryKey: ['warehouses'], queryFn: fetchWarehouses, enabled });
}

export function useCreateWarehouse() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createWarehouse,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['warehouses'] });
      queryClient.invalidateQueries({ queryKey: ['org', 'branches'] });
    },
  });
}

export function useUsers(enabled = true) {
  return useQuery({ queryKey: ['users'], queryFn: fetchUsers, enabled });
}

export function useRoles(enabled = true) {
  return useQuery({ queryKey: ['users', 'roles'], queryFn: fetchRoles, enabled });
}

export function useCreateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateUserInput) => createUser(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
    },
  });
}

export function useUpdateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, input }: { userId: string; input: UpdateUserInput }) =>
      updateUser(userId, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
    },
  });
}
