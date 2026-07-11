// Typed fetch wrapper that mirrors the backend error envelope
// ({ error: { code, message, field_errors, correlation_id } }) and sends
// credentials so HTTP-only auth cookies flow. A code-generated OpenAPI client
// replaces the hand-written endpoint calls in a later phase; this thin layer
// establishes the error contract now.
import { env } from '@/config/env';

export interface ApiErrorBody {
  code: string;
  message: string;
  field_errors: Record<string, string[]>;
  correlation_id: string | null;
}

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly fieldErrors: Record<string, string[]>;
  readonly correlationId: string | null;

  constructor(status: number, body: ApiErrorBody) {
    super(body.message);
    this.name = 'ApiError';
    this.status = status;
    this.code = body.code;
    this.fieldErrors = body.field_errors ?? {};
    this.correlationId = body.correlation_id ?? null;
  }
}

export interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown;
}

export async function apiFetch<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { body, headers, ...rest } = options;
  const response = await fetch(`${env.NEXT_PUBLIC_API_BASE_URL}${path}`, {
    ...rest,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...headers,
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (!response.ok) {
    let parsed: { error?: ApiErrorBody } = {};
    try {
      parsed = await response.json();
    } catch {
      // Non-JSON error (e.g. gateway failure) — fall through to a generic error.
    }
    throw new ApiError(
      response.status,
      parsed.error ?? {
        code: 'network_error',
        message: 'Unable to reach the server. Check your connection and try again.',
        field_errors: {},
        correlation_id: null,
      },
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}
