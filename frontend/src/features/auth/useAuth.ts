'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchMe, login, logout } from './api';

const ME_KEY = ['auth', 'me'];

/** Current authenticated user (from the HTTP-only cookie session). */
export function useMe() {
  return useQuery({
    queryKey: ME_KEY,
    queryFn: fetchMe,
    retry: false,
    staleTime: 60_000,
  });
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) =>
      login(email, password),
    onSuccess: (data) => {
      queryClient.setQueryData(ME_KEY, data.user);
    },
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: logout,
    onSuccess: () => {
      queryClient.setQueryData(ME_KEY, null);
      queryClient.invalidateQueries({ queryKey: ME_KEY });
    },
  });
}
