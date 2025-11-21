import { test, expect } from '@playwright/test';

/**
 * Smoke Tests - Verify basic system functionality
 * These tests ensure all services are reachable and responding
 */

test.describe('Smoke Tests', () => {
  test('Frontend loads successfully', async ({ page }) => {
    // Navigate to React frontend
    await page.goto('http://localhost:3000');

    // Wait for DOM to load (faster than networkidle which waits for SSE streams)
    await page.waitForLoadState('domcontentloaded');

    // Wait for React root to render
    const root = page.locator('#root');
    await expect(root).toBeVisible({ timeout: 10000 });

    // Verify title
    await expect(page).toHaveTitle(/arch_team/i);

    // Verify no console errors (except known warnings)
    const errors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });

    await page.reload();
    await page.waitForLoadState('domcontentloaded');
    await expect(root).toBeVisible({ timeout: 10000 });

    // Allow React dev warnings and SSE connection errors (expected when no session active)
    const criticalErrors = errors.filter(e =>
      !e.includes('DevTools') &&
      !e.includes('Warning:') &&
      !e.includes('[HMR]') &&
      !e.includes('SSE error')
    );

    expect(criticalErrors).toHaveLength(0);
  });

  test('Backend health endpoint responds', async ({ request }) => {
    const response = await request.get('http://localhost:8000/health', {
      timeout: 5000
    });

    expect(response.status()).toBe(200);
    expect(response.ok()).toBeTruthy();
  });

  test('Qdrant vector DB is accessible', async ({ request }) => {
    const response = await request.get('http://localhost:6401/collections', {
      timeout: 5000
    });

    expect(response.status()).toBe(200);

    const data = await response.json();
    expect(data).toHaveProperty('result');
  });

  test('All major UI components render', async ({ page }) => {
    await page.goto('http://localhost:3000');
    await page.waitForLoadState('domcontentloaded');

    // Wait for root to be visible
    const root = page.locator('#root');
    await expect(root).toBeVisible({ timeout: 10000 });

    // Check for main sections
    // Note: Actual selectors depend on your React component structure
    // Adjust these based on your App.jsx implementation

    // Configuration section
    const configSection = page.getByText(/configuration|konfiguration/i).first();
    await expect(configSection).toBeVisible({ timeout: 10000 });

    // Agent cards section (check for agents grid container)
    const agentsGrid = page.locator('.agents-grid');
    await expect(agentsGrid).toBeVisible({ timeout: 10000 });

    // Requirements section (may be empty initially)
    const reqSection = page.getByText(/requirements|anforderungen/i).first();
    await expect(reqSection).toBeVisible({ timeout: 10000 });
  });

  test('File upload component is present', async ({ page }) => {
    await page.goto('http://localhost:3000');
    await page.waitForLoadState('domcontentloaded');

    // Wait for root to be visible
    const root = page.locator('#root');
    await expect(root).toBeVisible({ timeout: 10000 });

    // Look for file input
    const fileInput = page.locator('input[type="file"]');
    await expect(fileInput).toBeVisible({ timeout: 10000 });
  });

  test('Start Mining button is present', async ({ page }) => {
    await page.goto('http://localhost:3000');
    await page.waitForLoadState('domcontentloaded');

    // Wait for root to be visible
    const root = page.locator('#root');
    await expect(root).toBeVisible({ timeout: 10000 });

    // Look for Start Mining button
    const startButton = page.getByRole('button', { name: /start.*mining|mining.*starten/i });
    await expect(startButton).toBeVisible({ timeout: 10000 });
  });
});
