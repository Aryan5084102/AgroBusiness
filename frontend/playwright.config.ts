import { defineConfig, devices } from '@playwright/test';

/**
 * E2E runs against a locally started dev server by default. Set
 * `PLAYWRIGHT_BASE_URL` to point at an already-running server instead — that is
 * how the suite is run against a production build (`pnpm build && next start`),
 * which is the faithful check before a release.
 *
 * Critical flows run on all three engines; browsers install via
 * `npx playwright install`.
 */
const externalBaseUrl = process.env.PLAYWRIGHT_BASE_URL;

export default defineConfig({
  testDir: './e2e',
  // The per-role sweep opens fourteen screens in one test; against `next dev`
  // each route compiles on first hit, which puts it right on Playwright's 30s
  // default. Sixty gives it room without masking a genuinely hung page.
  timeout: 60_000,
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: 'list',
  use: {
    baseURL: externalBaseUrl ?? 'http://localhost:3000',
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
    { name: 'webkit', use: { ...devices['Desktop Safari'] } },
  ],
  // Only manage a dev server when we are not pointed at an external one.
  ...(externalBaseUrl
    ? {}
    : {
        webServer: {
          command: 'pnpm dev',
          url: 'http://localhost:3000',
          reuseExistingServer: !process.env.CI,
          timeout: 120_000,
        },
      }),
});
