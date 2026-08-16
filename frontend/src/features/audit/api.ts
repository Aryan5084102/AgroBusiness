// Audit-log API (read-only; requires the audit.view permission).
import { apiFetch } from '@/lib/api/client';

export interface AuditLog {
  id: string;
  created_at: string;
  action: string;
  actor_user_id: string | null;
  actor_name: string | null;
  entity_type: string | null;
  entity_id: string | null;
  reason: string | null;
  ip_address: string | null;
  correlation_id: string | null;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
}

export interface AuditLogPage {
  items: AuditLog[];
  total: number;
  limit: number;
  offset: number;
  actions: string[];
}

export function fetchAuditLogs(params: {
  action?: string;
  limit?: number;
  offset?: number;
}): Promise<AuditLogPage> {
  const search = new URLSearchParams();
  if (params.action) search.set('action', params.action);
  search.set('limit', String(params.limit ?? 50));
  search.set('offset', String(params.offset ?? 0));
  return apiFetch<AuditLogPage>(`/api/v1/audit/logs?${search.toString()}`);
}
