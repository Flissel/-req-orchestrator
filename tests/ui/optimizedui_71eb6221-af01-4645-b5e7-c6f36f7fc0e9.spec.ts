
import { test } from '@playwright/test';
import { expect } from '@playwright/test';

test.skip('OptimizedUI_2025-08-14', async ({ page, context }) => {
  
    // Navigate to URL
    await page.goto('http://localhost:5173/', { waitUntil: 'domcontentloaded' });

    // Navigate to URL
    await page.goto('http://localhost:8081', { waitUntil: 'domcontentloaded' });

    // Click element
    await page.click('#load-btn');

    // Navigate to URL
    await page.goto('http://localhost:8081/index_optimized.html', { waitUntil: 'domcontentloaded' });

    // Click element
    await page.click('#load-btn');

    // Click element
    await page.click('#process-btn');
});