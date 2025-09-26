import { defineConfig } from '@playwright/test';

const BASE: string = (globalThis as any)?.process?.env?.PLAYWRIGHT_BASE_URL ?? 'http://localhost:4173';

export default defineConfig({
  testDir: 'tests/ui',
  timeout: 60_000,
  expect: { timeout: 5_000 },
  fullyParallel: true,
  reporter: 'list',
  use: {
    baseURL: BASE,
    trace: 'on-first-retry',
  },
  webServer: {
    // Serve static frontend for tests. Uses npx to avoid adding a dep.
    command: 'npx -y http-server ./frontend -p 4173 -c-1',
    url: BASE,
    timeout: 120_000,
    reuseExistingServer: true,
  },
});