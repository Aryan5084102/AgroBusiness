// System-status feature API. Talks to the backend aggregate health endpoint.
import { apiFetch } from '@/lib/api/client';

export interface ComponentStatus {
  name: string;
  status: 'up' | 'down';
  detail?: string | null;
}

export interface HealthResponse {
  status: 'ok' | 'degraded';
  environment: string;
  version: string;
  components: ComponentStatus[];
}

export function fetchHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>('/api/v1/health');
}
