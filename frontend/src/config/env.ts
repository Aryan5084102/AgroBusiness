// Validated, typed access to public environment variables. Only NEXT_PUBLIC_*
// values are exposed to the browser; secrets never live here.
import { z } from 'zod';

// NEXT_PUBLIC_API_BASE_URL is deliberately absent. The browser calls /api/* on
// its own origin and next.config.mjs proxies to the backend, so the API's
// address is a build-time server concern (API_PROXY_TARGET) rather than
// something shipped to the client.
const schema = z.object({
  // Opt-in for the login page's demo-account panel. Unset means "follow the
  // build type" — visible in dev, hidden in a production build. Deployed demo
  // environments set it to 'true' explicitly, since a hosted build is always a
  // production build and could otherwise never show the panel.
  NEXT_PUBLIC_SHOW_DEMO_ACCOUNTS: z.preprocess(
    (value) => (value === '' ? undefined : value),
    z.enum(['true', 'false']).optional(),
  ),
});

// Next inlines NEXT_PUBLIC_* only at literal references, so each one is listed.
const parsed = schema.safeParse({
  NEXT_PUBLIC_SHOW_DEMO_ACCOUNTS: process.env.NEXT_PUBLIC_SHOW_DEMO_ACCOUNTS,
});

if (!parsed.success) {
  // Fail fast with a readable message rather than obscure runtime errors.
  throw new Error(`Invalid public environment configuration: ${parsed.error.message}`);
}

export const env = parsed.data;
