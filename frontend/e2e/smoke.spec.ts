import { expect, test } from '@playwright/test';

// Phase 0 smoke test: the landing/login experience renders and links to status.
test('landing page shows sign-in and links to system status', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: /sign in/i })).toBeVisible();
  await expect(page.getByLabel(/email/i)).toBeVisible();
  await page.getByRole('link', { name: /system status/i }).click();
  await expect(page).toHaveURL(/\/status$/);
  await expect(page.getByRole('heading', { name: /system status/i })).toBeVisible();
});
