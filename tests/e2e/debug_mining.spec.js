import { test, expect } from '@playwright/test';

test('Debug Mining Workflow with Example Data', async ({ page }) => {
  console.log('=== Starting Mining Workflow Debug Test ===');

  // Listen for console messages
  page.on('console', msg => console.log(`BROWSER: ${msg.text()}`));
  page.on('pageerror', err => console.log(`PAGE ERROR: ${err.message}`));

  // Navigate to the app
  await page.goto('http://localhost:3000', { waitUntil: 'domcontentloaded' });
  console.log('✓ Navigated to app');

  // Wait a bit for React to render
  await page.waitForTimeout(2000);

  // Take screenshot to see what loaded
  await page.screenshot({ path: 'debug/initial-load.png', fullPage: true });
  console.log('✓ Screenshot saved: initial-load.png');

  // Wait for the app to load - try different selectors
  try {
    await page.waitForSelector('.tab-navigation', { timeout: 10000 });
    console.log('✓ App loaded (tab-navigation found)');
  } catch (e) {
    console.log('⚠ tab-navigation not found, trying alternative selector');
    await page.waitForSelector('.app-container, #root > div', { timeout: 5000 });
    console.log('✓ App container found');
  }

  // Click on Mining tab
  await page.click('button:has-text("Mining")');
  console.log('✓ Clicked Mining tab');
  await page.waitForTimeout(1000);

  // Select an example file from the dropdown
  console.log('Selecting example file...');
  await page.selectOption('select#examples', 'mixed_requirements_example.md');
  console.log('✓ Selected mixed_requirements_example.md');

  // Wait for file to load
  await page.waitForTimeout(2000);

  // Check if Start Mining button is enabled
  const startButton = page.locator('button:has-text("Mining starten")');
  const isEnabled = await startButton.isEnabled();
  console.log(`Start Mining button enabled: ${isEnabled}`);

  // Take screenshot before starting
  await page.screenshot({ path: 'debug/before-mining.png', fullPage: true });
  console.log('✓ Screenshot saved: before-mining.png');

  // Click Start Mining
  await startButton.click();
  console.log('✓ Clicked Start Mining button');

  // Monitor the status bar
  const statusBar = page.locator('.status-bar');
  let statusText = await statusBar.textContent();
  console.log(`Initial status: ${statusText}`);

  // Wait and observe for 60 seconds
  console.log('⏳ Waiting 60 seconds to observe mining process...');

  for (let i = 1; i <= 12; i++) {
    await page.waitForTimeout(5000);

    // Check status
    statusText = await statusBar.textContent();
    console.log(`[${i * 5}s] Status: ${statusText}`);

    // Check logs
    const logs = await page.locator('.log-entry').allTextContents();
    if (logs.length > 0) {
      console.log(`[${i * 5}s] Logs (${logs.length}):`, logs.slice(-3));
    }

    // Check if requirements appeared
    const reqCount = await page.locator('.requirements-table tbody tr').count();
    if (reqCount > 0) {
      console.log(`[${i * 5}s] ✓ Requirements appeared: ${reqCount} rows`);
    }

    // Take periodic screenshots
    if (i === 2 || i === 6 || i === 12) {
      await page.screenshot({ path: `debug/mining-${i * 5}s.png`, fullPage: true });
      console.log(`✓ Screenshot saved: mining-${i * 5}s.png`);
    }
  }

  console.log('=== 60 Second Observation Complete ===');

  // Final state check
  const finalReqCount = await page.locator('.requirements-table tbody tr').count();
  console.log(`Final requirement count: ${finalReqCount}`);

  // Check if we're still on Mining tab or switched to Requirements tab
  const activeTab = await page.locator('.tab-btn.active').textContent();
  console.log(`Active tab: ${activeTab}`);

  // Take final screenshot
  await page.screenshot({ path: 'debug/final-state.png', fullPage: true });
  console.log('✓ Final screenshot saved: final-state.png');

  // Keep browser open for manual inspection
  await page.waitForTimeout(5000);
});
