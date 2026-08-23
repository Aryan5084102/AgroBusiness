import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Resolve the demo-panel flag to a concrete value at build time. Next only
// inlines NEXT_PUBLIC_* literals that actually exist, so leaving this unset
// would keep the check at runtime and ship the demo credentials in the bundle
// even with the panel hidden. Defaulting it here keeps the comparison in
// features/auth/demoAccounts.ts constant-foldable, so the account list is
// stripped from production builds unless the flag is explicitly on.
const showDemoAccounts =
  process.env.NEXT_PUBLIC_SHOW_DEMO_ACCOUNTS ??
  (process.env.NODE_ENV === 'production' ? 'false' : 'true');

// The browser talks to /api/* on this same origin and Next proxies it to the
// backend server-side. Two problems disappear as a result, both of which used to
// need backend configuration to be exactly right:
//
//   1. CORS. The browser never makes a cross-origin request, so there is no
//      preflight to reject. A wrong CORS_ORIGINS could otherwise block every
//      request with nothing in the server log to show for it.
//   2. Cookie SameSite. Auth travels in HTTP-only cookies; cross-site delivery
//      needs SameSite=None, and getting it wrong fails quietly — login returns
//      200 and the browser silently discards the cookie. Same-origin requests
//      have no such requirement.
//
// API_PROXY_TARGET is the upstream. NEXT_PUBLIC_API_BASE_URL is accepted as a
// fallback so existing deployments keep working without a variable rename;
// it is read here at build time and no longer reaches the browser.
const apiProxyTarget = (
  process.env.API_PROXY_TARGET ??
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  'http://localhost:8000'
).replace(/\/$/, '');

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  env: { NEXT_PUBLIC_SHOW_DEMO_ACCOUNTS: showDemoAccounts },
  // Pin the tracing root to this app (avoids picking up a stray parent lockfile).
  outputFileTracingRoot: __dirname,
  sassOptions: {
    // Make design-token partials importable without long relative paths.
    includePaths: [path.join(__dirname, 'src/styles')],
  },
  async rewrites() {
    return [{ source: '/api/:path*', destination: `${apiProxyTarget}/api/:path*` }];
  },
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'X-Frame-Options', value: 'DENY' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
        ],
      },
    ];
  },
};

export default nextConfig;
