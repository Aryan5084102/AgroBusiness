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
