import { expect, test, type Page } from '@playwright/test';

/**
 * Captures a screenshot of every screen (and the tabs/dialogs inside them) as
 * the owner, at desktop and phone widths. Run with `PLAYWRIGHT_SCREENSHOTS=1` —
 * it is a visual-review aid, not an assertion suite, so it is skipped by default.
 */
const SCREENS = [
  { path: '/dashboard', name: 'dashboard' },
  { path: '/sales', name: 'retail-counter' },
  { path: '/wholesale', name: 'wholesale' },
  { path: '/invoices', name: 'invoices' },
  { path: '/customers', name: 'customers' },
  { path: '/collections', name: 'collections' },
  { path: '/products', name: 'products' },
  { path: '/inventory', name: 'inventory' },
  { path: '/purchases', name: 'purchases' },
  { path: '/service', name: 'service' },
  { path: '/reports', name: 'reports' },
  { path: '/accounting', name: 'accounting' },
  { path: '/audit', name: 'audit' },
  { path: '/settings', name: 'settings' },
];

/** Tabs worth capturing separately — each renders a different panel. */
const TABS: { path: string; tab: RegExp; name: string }[] = [
  { path: '/inventory', tab: /Batches & expiry/, name: 'inventory-batches' },
  { path: '/inventory', tab: /Movement ledger/, name: 'inventory-ledger' },
  { path: '/collections', tab: /Who owes what/, name: 'collections-receivables' },
  { path: '/collections', tab: /Payment history/, name: 'collections-history' },
  { path: '/reports', tab: /Purchase register/, name: 'reports-purchases' },
  { path: '/reports', tab: /GST summary/, name: 'reports-gst' },
  { path: '/reports', tab: /Stock valuation/, name: 'reports-stock' },
  { path: '/accounting', tab: /Journal register/, name: 'accounting-journals' },
  { path: '/accounting', tab: /Customer statement/, name: 'accounting-ledger' },
  { path: '/settings', tab: /People/, name: 'settings-people' },
  { path: '/settings', tab: /Roles & access/, name: 'settings-roles' },
  { path: '/settings', tab: /Branches & warehouses/, name: 'settings-locations' },
  { path: '/purchases', tab: /Receipt history/, name: 'purchases-history' },
  { path: '/purchases', tab: /Suppliers/, name: 'purchases-suppliers' },
  { path: '/wholesale', tab: /Order pipeline/, name: 'wholesale-pipeline' },
];

/** Row/button clicks that open a dialog. */
const DIALOGS: { path: string; open: (page: Page) => Promise<void>; name: string }[] = [
  {
    path: '/invoices',
    name: 'dialog-invoice',
    open: async (page) =>
      page
        .getByText(/INV-\d+/)
        .first()
        .click(),
  },
  {
    path: '/service',
    name: 'dialog-job',
    open: async (page) =>
      page
        .getByText(/JOB-\d+/)
        .first()
        .click(),
  },
  {
    path: '/inventory',
    name: 'dialog-adjust',
    open: async (page) => page.getByRole('button', { name: 'Adjust stock' }).click(),
  },
  {
    path: '/inventory',
    name: 'dialog-transfer',
    open: async (page) => page.getByRole('button', { name: 'Transfer' }).click(),
  },
  {
    path: '/products',
    name: 'dialog-product',
    open: async (page) => page.getByRole('button', { name: 'Add product' }).click(),
  },
  {
    path: '/customers',
    name: 'dialog-customer',
    open: async (page) => page.getByRole('button', { name: 'Add customer' }).click(),
  },
  {
    path: '/settings',
    name: 'dialog-user',
    open: async (page) => {
      await page.getByRole('tab', { name: /People/ }).click();
      await page.getByRole('button', { name: 'Add a person' }).click();
    },
  },
];

test.skip(!process.env.PLAYWRIGHT_SCREENSHOTS, 'visual capture run only');

test('capture every screen', async ({ page }) => {
  test.setTimeout(180_000);
  await page.goto('/');
  await page.getByLabel('Email').fill('owner@agriflow.local');
  await page.getByLabel('Password').fill('AgriFlow@123');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('navigation', { name: 'Primary navigation' })).toBeVisible({
    timeout: 15_000,
  });

  await page.setViewportSize({ width: 1440, height: 900 });
  for (const screen of SCREENS) {
    await page.goto(screen.path);
    await page.waitForTimeout(900); // let queries settle so panels have data
    await page.screenshot({
      path: `screenshots/desktop-${screen.name}.png`,
      fullPage: true,
    });
  }

  for (const item of TABS) {
    await page.goto(item.path);
    await page.getByRole('tab', { name: item.tab }).click();
    await page.waitForTimeout(900);
    await page.screenshot({ path: `screenshots/tab-${item.name}.png`, fullPage: true });
  }

  for (const item of DIALOGS) {
    await page.goto(item.path);
    await page.waitForTimeout(700);
    await item.open(page);
    await page.waitForTimeout(700);
    await page.screenshot({ path: `screenshots/${item.name}.png` });
  }

  await page.setViewportSize({ width: 390, height: 844 });
  for (const screen of SCREENS) {
    await page.goto(screen.path);
    await page.waitForTimeout(900);
    await page.screenshot({
      path: `screenshots/mobile-${screen.name}.png`,
      fullPage: true,
    });
  }
});
