import { expect, test, type Page } from '@playwright/test';

/**
 * The write paths that touch money and stock, driven through the real UI:
 * ringing up a sale, correcting stock, and receiving a payment. These are the
 * flows a shop runs all day, so they get an end-to-end check rather than only
 * service-layer coverage.
 *
 * Requires the API on :8000 with the demo seed loaded (`python -m app.seed`).
 */

const PASSWORD = 'AgriFlow@123';

async function signIn(page: Page, email: string) {
  await page.goto('/');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(PASSWORD);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('navigation', { name: 'Primary navigation' })).toBeVisible({
    timeout: 15_000,
  });
}

test('a counter sale prices, bills and lands in the invoice list', async ({ page }) => {
  await signIn(page, 'billing@agriflow.local');
  await page.goto('/sales');

  await page.getByPlaceholder('Search by name, SKU or barcode…').fill('Urea');
  const product = page.getByRole('button', { name: /Urea 50kg Bag/ });
  await expect(product).toBeVisible({ timeout: 10_000 });
  await product.click();

  // The bill total is quoted by the server, so wait for a non-zero amount.
  const payButton = page.getByRole('button', { name: /Take payment —/ });
  await expect(payButton).toBeEnabled({ timeout: 10_000 });
  await expect(payButton).not.toContainText('₹0.00');

  await payButton.click();

  // The toast names the invoice the server created. Numbers are branch-scoped,
  // so they carry the branch code (e.g. "MAIN-INV-00016").
  const toast = page.getByText(/^Invoice (?:[A-Z0-9]+-)?INV-\d+$/);
  await expect(toast).toBeVisible({ timeout: 15_000 });
  const invoiceNumber = (await toast.textContent())?.replace('Invoice ', '').trim();
  expect(invoiceNumber).toMatch(/INV-\d+$/);

  // The cart resets so the next customer can be served immediately.
  await expect(page.getByText('No items yet')).toBeVisible();

  // And the sale is now history.
  await page.goto('/invoices');
  await expect(page.getByText(invoiceNumber as string).first()).toBeVisible({
    timeout: 15_000,
  });
});

test('a stock correction is posted with its reason to the ledger', async ({ page }) => {
  await signIn(page, 'inventory@agriflow.local');
  await page.goto('/inventory');

  await page.getByRole('button', { name: 'Adjust stock' }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();

  await dialog.getByLabel(/^Warehouse/).selectOption({ label: 'Main Shop' });
  await dialog.getByLabel(/^Product/).selectOption({ index: 1 });
  await dialog.getByLabel(/^Quantity/).fill('-1');
  await dialog
    .getByRole('textbox', { name: 'Reason' })
    .fill('Bag torn in the store room');
  await dialog.getByRole('button', { name: 'Post adjustment' }).click();

  await expect(page.getByText('Stock adjusted')).toBeVisible({ timeout: 15_000 });

  // The ledger records it with the reason attached.
  await page.getByRole('tab', { name: /Movement ledger/ }).click();
  await expect(page.getByText('Bag torn in the store room').first()).toBeVisible({
    timeout: 15_000,
  });
});

test('a collection settles a dealer invoice and shows on the statement', async ({
  page,
}) => {
  await signIn(page, 'accountant@agriflow.local');
  await page.goto('/collections');

  await page
    .getByLabel('Customer', { exact: true })
    .selectOption({ label: 'Kisan Traders (DLR-KISAN)' });
  const amount = page.getByLabel(/Amount received/);
  await expect(amount).not.toHaveValue('0.00', { timeout: 10_000 });
  await amount.fill('500');
  await page.getByLabel('Reference').fill('E2E-TEST-RECEIPT');
  await page.getByRole('button', { name: 'Record payment' }).click();

  await expect(page.getByText(/^Received ₹/)).toBeVisible({ timeout: 15_000 });

  // It appears in the payment history with the reference we typed.
  await page.getByRole('tab', { name: /Payment history/ }).click();
  await expect(page.getByText('E2E-TEST-RECEIPT').first()).toBeVisible({
    timeout: 15_000,
  });
});

test('dialogs open centred in the viewport', async ({ page }) => {
  // The global reset zeroes every margin, which also clears the <dialog> user
  // agent's `margin: auto`. That pinned every dialog to the top-left corner —
  // easy to reintroduce, so assert the geometry rather than trusting the CSS.
  await signIn(page, 'owner@agriflow.local');
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto('/inventory');
  await page.getByRole('button', { name: 'Adjust stock' }).click();

  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  const box = await dialog.boundingBox();
  expect(box).not.toBeNull();

  const centreX =
    (box as { x: number; width: number }).x + (box as { width: number }).width / 2;
  const centreY =
    (box as { y: number; height: number }).y + (box as { height: number }).height / 2;
  // Within 40px of the viewport centre on both axes.
  expect(Math.abs(centreX - 640)).toBeLessThan(40);
  expect(Math.abs(centreY - 450)).toBeLessThan(40);
});
