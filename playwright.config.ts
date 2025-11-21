import { defineConfig } from '@playwright/test';

const BASE: string = (globalThis as any)?.process?.env?.PLAYWRIGHT_BASE_URL ?? 'http://localhost:4173';

export default defineConfig({
  testDir: 'tests/e2e',
  timeout: 90_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  reporter: 'list',
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
  },
});