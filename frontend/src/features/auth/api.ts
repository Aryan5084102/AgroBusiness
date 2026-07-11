// Auth feature API. Talks to the backend cookie-based auth endpoints.
import { apiFetch } from '@/lib/api/client';

export interface AuthUser {
  id: string;
  email: string;
  full_name: string;
  organization_id: string;
  is_owner: boolean;
  permissions: string[];
  branch_ids: string[];
}

export interface LoginResponse {
  user: AuthUser;
  access_expires_in: number;
}

export function login(email: string, password: string): Promise<LoginResponse> {
  return apiFetch<LoginResponse>('/api/v1/auth/login', {
    method: 'POST',
    body: { email, password },
  });
}

export function fetchMe(): Promise<AuthUser> {
  return apiFetch<AuthUser>('/api/v1/auth/me');
}

export function logout(): Promise<void> {
  return apiFetch<void>('/api/v1/auth/logout', { method: 'POST' });
}
