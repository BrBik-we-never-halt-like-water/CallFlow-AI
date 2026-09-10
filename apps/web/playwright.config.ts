import { defineConfig, devices } from '@playwright/test';

/**
 * Scaffold only for now. The first real end-to-end flow (login -> upload ->
 * run -> leads -> export) lands with Y8 once /app/leads and /app/reports
 * exist - forcing a full journey test before there is a journey to test
 * would just be a test of today's escalations page under a different name.
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: 'list',
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:3000',
    trace: 'on-first-retry',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
