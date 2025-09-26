
import { test } from '@playwright/test';
import { expect } from '@playwright/test';

test('MiningDemo_2025-09-04', async ({ page, context }) => {
  
    // Navigate to URL
    await page.goto('http://localhost:5173/mining_demo.html');

    // Navigate to URL
    await page.goto('http://localhost:8081/mining_demo.html');

    // Take screenshot
    await page.screenshot({ path: 'mining_demo_initial.png', { fullPage: true } });

    // Click element
    await page.click('#btnLoadCfg');

    // Take screenshot
    await page.screenshot({ path: 'after_load_config.png', { fullPage: true } });

    // Click element
    await page.click('#btnPreviewCfg');

    // Take screenshot
    await page.screenshot({ path: 'after_config_preview.png', { fullPage: true } });

    // Click element
    await page.click('#btnLoadReports');

    // Take screenshot
    await page.screenshot({ path: 'after_load_reports.png', { fullPage: true } });

    // Select option
    await page.selectOption('#reportSelect', 'lx_6199020fb8_1756992263');

    // Click element
    await page.click('#btnShowReport');
});