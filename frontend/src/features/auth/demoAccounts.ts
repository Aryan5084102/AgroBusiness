// Demo accounts shown on the login page for quick testing. These mirror the
// backend seed (app/seed.py), which itself refuses to run against a production
// database — so these users only exist where demo data was deliberately seeded.

export const DEMO_PASSWORD = 'AgriFlow@123';

export interface DemoAccount {
  email: string;
  label: string;
}

export const DEMO_ACCOUNTS: DemoAccount[] = [
  { email: 'owner@agriflow.local', label: 'Owner (full access)' },
  { email: 'counter@agriflow.local', label: 'Counter / Sales' },
  { email: 'store@agriflow.local', label: 'Store / Inventory' },
];

// Hosted demos are production builds, so NODE_ENV alone can never reveal the
// panel there — next.config.mjs resolves NEXT_PUBLIC_SHOW_DEMO_ACCOUNTS to an
// explicit 'true'/'false' at build time, defaulting to the build type so local
// `next dev` still works with no configuration.
//
// Reads process.env directly rather than the validated `env` object on purpose:
// Next inlines the literal, so this folds to a constant and the credentials
// above are stripped from the bundle when the panel is off. Going through `env`
// would defer the check to runtime and ship the account list to every visitor.
// The value is still validated in config/env.ts, which loads on any page that
// talks to the API, so a typo like 'TRUE' fails loudly rather than silently
// hiding the panel.
export const showDemoAccounts = process.env.NEXT_PUBLIC_SHOW_DEMO_ACCOUNTS === 'true';
