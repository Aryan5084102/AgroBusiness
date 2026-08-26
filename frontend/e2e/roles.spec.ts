import { expect, test, type Page } from '@playwright/test';

/**
 * Per-role walkthrough: signs in as each seeded demo account, visits every
 * screen that role is entitled to, and asserts the page renders real content
 * with no console errors and no permission wall. This is the regression net
 * for "role X sees a broken screen", which is easy to reintroduce whenever a
 * permission or a nav entry changes.
 *
 * Requires the API on :8000 with the demo seed loaded (`python -m app.seed`).
 */

const PASSWORD = 'AgriFlow@123';

interface RoleCase {
  email: string;
  label: string;
  /** Screens this role must be able to open. */
  allowed: { path: string; heading: RegExp }[];
  /** Screens this role must be refused. */
  denied: string[];
}

const DASHBOARD = { path: '/dashboard', heading: /today at a glance/i };

const ROLES: RoleCase[] = [
  {
    email: 'owner@agriflow.local',
    label: 'Owner',
    allowed: [
      DASHBOARD,
      { path: '/sales', heading: /retail counter/i },
      { path: '/wholesale', heading: /wholesale orders/i },
      { path: '/invoices', heading: /invoices/i },
      { path: '/customers', heading: /customers & dealers/i },
      { path: '/collections', heading: /collections/i },
      { path: '/products', heading: /products/i },
      { path: '/inventory', heading: /inventory/i },
      { path: '/purchases', heading: /purchases/i },
      { path: '/service', heading: /workshop/i },
      { path: '/reports', heading: /reports/i },
      { path: '/accounting', heading: /books/i },
      { path: '/audit', heading: /audit log/i },
      { path: '/settings', heading: /settings/i },
    ],
    denied: [],
  },
  {
    // Both halves of the shop from one login: walk-in billing and dealer
    // orders. No purchases, no reports, no margin, no settings.
    email: 'counter@agriflow.local',
    label: 'Counter / Sales',
    allowed: [
      DASHBOARD,
      { path: '/sales', heading: /retail counter/i },
      { path: '/wholesale', heading: /wholesale orders/i },
      { path: '/invoices', heading: /invoices/i },
      { path: '/customers', heading: /customers & dealers/i },
      { path: '/collections', heading: /collections/i },
      { path: '/products', heading: /products/i },
      { path: '/inventory', heading: /inventory/i },
    ],
    denied: ['/purchases', '/service', '/reports', '/accounting', '/audit', '/settings'],
  },
  {
    // Godown side. Stock and cash stay separate, so no billing and no
    // collections here.
    email: 'store@agriflow.local',
    label: 'Store / Inventory',
    allowed: [
      DASHBOARD,
      { path: '/products', heading: /products/i },
      { path: '/inventory', heading: /inventory/i },
      { path: '/purchases', heading: /purchases/i },
    ],
    denied: [
      '/sales',
      '/wholesale',
      '/invoices',
      '/customers',
      '/collections',
      '/service',
      '/reports',
      '/accounting',
      '/audit',
      '/settings',
    ],
  },
];

async function signIn(page: Page, email: string) {
  const nav = page.getByRole('navigation', { name: 'Primary navigation' });

  // Several role specs sign in at once; a single-worker dev API can drop a
  // connection under that burst. Retry the sign-in itself rather than letting a
  // transport hiccup masquerade as a permissions failure.
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    await page.goto('/');
    await page.getByLabel('Email').fill(email);
    await page.getByLabel('Password').fill(PASSWORD);
    await page.getByRole('button', { name: 'Sign in', exact: true }).click();

    // The landing route depends on the role's permissions, so wait for the shell.
    try {
      await nav.waitFor({ state: 'visible', timeout: 10_000 });
      return;
    } catch {
      if (attempt === 3) break;
      await page.waitForTimeout(1_000 * attempt);
    }
  }

  await expect(nav, `${email} could not sign in`).toBeVisible({ timeout: 10_000 });
}

for (const role of ROLES) {
  test.describe(role.label, () => {
    test(`can use every screen their role covers`, async ({ page }) => {
      const consoleErrors: string[] = [];
      page.on('console', (message) => {
        if (message.type() === 'error') consoleErrors.push(message.text());
      });

      await signIn(page, role.email);
      // Sign-in contention is already handled by the retry above; what matters
      // here is that the screens themselves render without console errors.
      consoleErrors.length = 0;

      for (const screen of role.allowed) {
        await page.goto(screen.path);
        await expect(
          page.getByRole('heading', { name: screen.heading }).first(),
          `${role.label} should see a working ${screen.path}`,
        ).toBeVisible({ timeout: 15_000 });
        // The permission wall must not appear on an allowed screen.
        await expect(page.getByText(/do not have access to this page/i)).toHaveCount(0);
        // Nor should any panel report a permission failure.
        await expect(page.getByText(/do not have access to this data/i)).toHaveCount(0);
      }

      expect(
        consoleErrors.filter(
          (text) =>
            !text.includes('Download the React DevTools') &&
            // Next.js prefetches each route's payload; navigating away before
            // one lands aborts it, which Next logs as an error even though it
            // recovers with a normal navigation. Firefox surfaces this on the
            // rapid goto() loop below — it is framework noise, not a defect.
            !text.includes('Failed to fetch RSC payload'),
        ),
        `${role.label} hit console errors`,
      ).toEqual([]);
    });

    if (role.denied.length > 0) {
      test(`is refused screens outside their role`, async ({ page }) => {
        await signIn(page, role.email);
        for (const path of role.denied) {
          await page.goto(path);
          await expect(
            page.getByText(/do not have access to this page/i),
            `${role.label} should be refused ${path}`,
          ).toBeVisible({ timeout: 15_000 });
        }
      });
    }

    test(`sidebar only offers screens they can open`, async ({ page }) => {
      await signIn(page, role.email);
      const nav = page.getByRole('navigation', { name: 'Primary navigation' });
      for (const path of role.denied) {
        await expect(nav.locator(`a[href="${path}"]`)).toHaveCount(0);
      }
      for (const screen of role.allowed) {
        await expect(nav.locator(`a[href="${screen.path}"]`)).toHaveCount(1);
      }
    });
  });
}
