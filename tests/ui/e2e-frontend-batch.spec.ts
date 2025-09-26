import { test, expect } from '@playwright/test';
/* @ts-ignore - Node-Typen sind im Editor evtl. nicht vorhanden; zur Laufzeit über Playwright/Node verfügbar */
import { execSync } from 'node:child_process';

test('frontend batch flow – real backend', async ({ page }) => {
  test.setTimeout(60000);
  // ENV-Zugriff ohne Abhängigkeit von @types/node
  const __env: any = (globalThis as any)?.process?.env || {};
  const BASE = __env.BASE_URL || 'http://localhost:8083';
  const events: { type: string; data: any }[] = [];

  page.on('console', (msg) => {
    try {
      events.push({ type: 'console', data: { level: msg.type(), text: msg.text() } });
    } catch {}
  });

  let batchStatus: number | null = null;
  let batchFailed: any = null;

  page.on('requestfailed', (req) => {
    if (req.url().includes('/api/v1/validate/batch')) {
      batchFailed = { url: req.url(), failure: req.failure() };
    }
  });

  page.on('response', async (resp) => {
    if (resp.url().includes('/api/v1/validate/batch')) {
      try {
        batchStatus = resp.status();
      } catch {}
    }
  });

  await page.goto(`${BASE}/`, { waitUntil: 'domcontentloaded' });
  await page.click('#load-btn');
  await expect(page.locator('#requirements-section')).toBeVisible();

  const batchRespPromise = page.waitForResponse((r) => r.url().includes('/api/v1/validate/batch') && r.request().method() === 'POST', { timeout: 45000 });
  await page.click('#process-btn');

  const master = page.locator('.results-master');
  await expect(master).toBeVisible();

  const rows = page.locator('#results-master .summary-row');
  await expect(rows.first()).toBeVisible();

  const batchResp = await batchRespPromise;
  const status = batchResp.status();

  try {
    if (batchFailed) throw new Error('requestfailed for /api/v1/validate/batch: ' + JSON.stringify(batchFailed));
    if (status !== 200) throw new Error('batch status != 200: ' + status);
    await expect(rows.first()).toBeVisible();
  } catch (err) {
    console.log('--- Browser console events ---');
    for (const e of events) {
      try {
        console.log(JSON.stringify(e));
      } catch {
        console.log(String(e));
      }
    }
    try {
      const logs = execSync('docker logs --tail 300 req-eval-backend-dev', { encoding: 'utf-8' });
      console.log('--- docker logs (req-eval-backend-dev, tail 300) ---\n' + logs);
    } catch (e) {
      console.log('docker logs fetch failed: ' + String(e));
    }
    throw err;
  }
});