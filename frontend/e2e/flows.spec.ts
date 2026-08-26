import { readFileSync } from 'node:fs';
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

/** The counter now names its buyer on every bill, so every sale starts here. */
async function enterCustomer(page: Page, name: string, mobile: string, address?: string) {
  await page.getByLabel('Customer name').fill(name);
  await page.getByLabel('Mobile number').fill(mobile);
  if (address) await page.getByLabel('Address').fill(address);
}

async function addProduct(page: Page, search: string, label: RegExp) {
  await page.getByPlaceholder('Search by name, SKU or barcode…').fill(search);
  const product = page.getByRole('button', { name: label });
  await expect(product).toBeVisible({ timeout: 10_000 });
  await product.click();
}

test('a counter sale prices, bills and lands in the invoice list', async ({ page }) => {
  await signIn(page, 'counter@agriflow.local');
  await page.goto('/sales');

  await enterCustomer(page, 'E2E Walk-in', '9000000001', 'Shirur');
  await addProduct(page, 'Urea', /Urea 50kg Bag/);

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

  // The cart and the customer both reset so the next person can be served.
  await expect(page.getByText('No items yet')).toBeVisible();
  await expect(page.getByLabel('Customer name')).toHaveValue('');
  await expect(page.getByLabel('Mobile number')).toHaveValue('');

  // And the sale is now history, under the name that was taken at the counter.
  await page.goto('/invoices');
  await expect(page.getByText(invoiceNumber as string).first()).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByText('E2E Walk-in').first()).toBeVisible();
});

test('taking payment refuses to bill nobody', async ({ page }) => {
  await signIn(page, 'counter@agriflow.local');
  await page.goto('/sales');

  await addProduct(page, 'Urea', /Urea 50kg Bag/);

  const payButton = page.getByRole('button', { name: /Take payment —/ });
  await expect(payButton).toBeEnabled({ timeout: 10_000 });
  await payButton.click();

  // Nothing is billed, and the counter is told exactly what is missing.
  await expect(
    page.getByText(/Fill in the customer name and mobile number/),
  ).toBeVisible();
  await expect(page.getByText('The bill needs a name to print.')).toBeVisible();
  await expect(page.getByText('A mobile number is required.')).toBeVisible();

  // A part-typed mobile is still no mobile.
  await enterCustomer(page, 'E2E Half Number', '98765');
  await payButton.click();
  await expect(page.getByText('Enter all 10 digits.')).toBeVisible();
});

test('a sale downloads the bill and leaves a printable copy behind', async ({ page }) => {
  await signIn(page, 'counter@agriflow.local');
  await page.goto('/sales');

  await enterCustomer(page, 'E2E Bill Taker', '9000000003', 'Market Road');
  await addProduct(page, 'Urea', /Urea 50kg Bag/);

  const payButton = page.getByRole('button', { name: /Take payment —/ });
  await expect(payButton).toBeEnabled({ timeout: 10_000 });
  await expect(payButton).not.toContainText('₹0.00');

  // The bill arrives on its own — the counter does not have to ask for it.
  const [download] = await Promise.all([
    page.waitForEvent('download', { timeout: 20_000 }),
    payButton.click(),
  ]);
  expect(download.suggestedFilename()).toMatch(/^(?:[A-Z0-9]+-)?INV-\d+\.pdf$/);

  const saved = await download.path();
  expect(saved).not.toBeNull();
  const bytes = readFileSync(saved as string);
  expect(bytes.subarray(0, 5).toString('latin1')).toBe('%PDF-');
  // The buyer the counter typed has to be in the file, not just on the screen.
  const text = bytes.toString('latin1');
  expect(text).toContain('(E2E Bill Taker)');
  expect(text).toContain('(Mobile 9000000003)');

  // And the same bill stays reachable as a printable page.
  await page.getByRole('link', { name: /Print bill/i }).click();

  const bill = page.getByRole('article', { name: /^Tax invoice/ });
  await expect(bill).toBeVisible({ timeout: 15_000 });
  await expect(page).toHaveURL(/\/invoices\/[0-9a-f-]{36}\/bill$/);

  // A tax invoice is only a tax invoice if it carries these.
  await expect(bill.getByText('Tax Invoice')).toBeVisible();
  await expect(bill.getByText(/^(?:[A-Z0-9]+-)?INV-\d+$/)).toBeVisible();
  await expect(bill.getByText('Billed to')).toBeVisible();
  await expect(bill.getByText('E2E Bill Taker')).toBeVisible();
  await expect(bill.getByText('Amount in words')).toBeVisible();
  await expect(bill.getByText(/^Rupees .+ Only$/)).toBeVisible();
  // CGST/SGST appear twice — in the rate-wise summary and in the totals.
  await expect(bill.getByText('CGST').first()).toBeVisible();
  await expect(bill.getByText('SGST').first()).toBeVisible();
  await expect(bill.getByText(/Authorised signatory/)).toBeVisible();

  // The saved-PDF filename comes from the document title.
  await expect(page).toHaveTitle(/^(?:[A-Z0-9]+-)?INV-\d+$/);

  // Nothing but the document reaches the printer.
  await expect(page.getByRole('navigation', { name: 'Primary navigation' })).toHaveCount(
    0,
  );
});

test('a mobile already on file is recognised, and its khata is the one charged', async ({
  page,
}) => {
  await signIn(page, 'counter@agriflow.local');
  await page.goto('/sales');
  await expect(page.getByPlaceholder('Search by name, SKU or barcode…')).toBeVisible({
    timeout: 15_000,
  });

  // Kisan Traders is seeded with this number, so the counter should not have to
  // type them in again — nor open a second account for them.
  await page.getByLabel('Mobile number').fill('9876500044');
  await expect(page.getByText('On file')).toBeVisible({ timeout: 15_000 });
  await expect(page.getByLabel('Customer name')).toHaveValue('Kisan Traders');

  await addProduct(page, 'DAP', /DAP 50kg Bag/);
  await page.getByLabel(/Sale on credit/).check();

  // Nothing is taken now, so the whole bill goes on the khata.
  const khata = page.getByRole('button', { name: /Put .+ on khata/ });
  await expect(khata).toBeEnabled({ timeout: 10_000 });

  const [download] = await Promise.all([
    page.waitForEvent('download', { timeout: 20_000 }),
    khata.click(),
  ]);
  expect(download.suggestedFilename()).toMatch(/\.pdf$/);

  const receipt = page.getByText(/^Invoice (?:[A-Z0-9]+-)?INV-\d+/);
  await expect(receipt).toBeVisible({ timeout: 15_000 });
  const invoiceNumber = (await receipt.textContent())?.match(
    /(?:[A-Z0-9]+-)?INV-\d+/,
  )?.[0];

  // The counter resets to cash and an empty customer for the next person.
  await expect(page.getByLabel(/Sale on credit/)).not.toBeChecked();
  await expect(page.getByLabel('Mobile number')).toHaveValue('');

  // And the sale really is on credit: its bill shows the customer, nothing
  // paid, and a balance still due.
  await page.getByRole('link', { name: /Print bill/i }).click();
  const bill = page.getByRole('article', { name: /^Tax invoice/ });
  await expect(bill).toBeVisible({ timeout: 15_000 });
  await expect(bill.getByText(invoiceNumber as string)).toBeVisible();
  await expect(bill.getByText('Kisan Traders')).toBeVisible();
  await expect(bill.getByText('On credit')).toBeVisible();
  await expect(bill.getByText('Balance due')).toBeVisible();
});

test('a stock correction is posted with its reason to the ledger', async ({ page }) => {
  await signIn(page, 'store@agriflow.local');
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
  await signIn(page, 'counter@agriflow.local');
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
