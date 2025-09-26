import { test, expect } from '@playwright/test';

test.describe('Use modified filter/working mode', () => {
  test('filters list, scopes batch actions, and controls reanalyze-modified', async ({ page }) => {
    // Mock: Demo requirements (3 items)
    await page.route('**/api/v1/demo/requirements', async (route) => {
      const json = {
        items: [
          { id: 'R1', requirementText: 'A' },
          { id: 'R2', requirementText: 'B' },
          { id: 'R3', requirementText: 'C' }
        ]
      };
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(json) });
    });

    // Track calls to batch endpoint (used by processing and re-analyze)
    let batchCalls = 0;
    await page.route('**/api/v1/validate/batch**', async (route) => {
      batchCalls++;
      let body: any = {};
      try { body = route.request().postDataJSON() || {}; } catch { body = {}; }
      const items: string[] = Array.isArray(body?.items) ? body.items : [''];
      const arr = items.map((t: string, i: number) => ({
        id: `mock-${Date.now()}-${i}`,
        originalText: String(t || ''),
        correctedText: '',
        status: 'rejected',
        evaluation: [],
        score: 0.11,
        verdict: 'fail'
      }));
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(arr) });
    });

    // Open app
    await page.goto('/', { waitUntil: 'domcontentloaded' });

    // Load requirements
    await page.click('#load-btn');
    await expect(page.locator('#requirements-section')).toBeVisible();

    // Process (incremental, mocked above)
    await page.click('#process-btn');
    const rows = page.locator('#results-master .summary-row');
    await expect(rows).toHaveCount(3);

    const toggleBtn = page.locator('[data-action="toggle-modified"]');
    await expect(toggleBtn).toBeVisible();

    // Initially: 0/3 modified
    await expect(toggleBtn).toContainText(/Use modified \(0\/3\)/);

    // Toggle on when none modified → empty state + disabled actions
    await toggleBtn.click();
    await expect(toggleBtn).toHaveAttribute('aria-pressed', 'true');
    await expect(page.locator('#results-master .detail-placeholder')).toHaveText(/Keine geänderten Items/i);
    await expect(page.locator('#accept-all-btn')).toBeDisabled();
    await expect(page.locator('#reject-all-btn')).toBeDisabled();
    await expect(page.locator('[data-action="reanalyze-modified"]')).toBeDisabled();

    // Toggle off to edit
    await toggleBtn.click();
    await expect(toggleBtn).toHaveAttribute('aria-pressed', 'false');

    // Mark index 0 and 2 as modified via left editors
    const input0 = page.locator('#req-list .req-collapsed[data-idx="0"] .editable-input');
    const input2 = page.locator('#req-list .req-collapsed[data-idx="2"] .editable-input');
    await input0.fill('A modified');
    await input2.fill('C modified');

    // Toggle on to re-render and compute counts
    await toggleBtn.click();
    await expect(toggleBtn).toHaveAttribute('aria-pressed', 'true');
    await expect(toggleBtn).toContainText(/Use modified \(2\/3\)/);

    // Only 2 visible rows, each with data-modified="true" and badge
    const visRows = page.locator('#results-master .summary-row');
    await expect(visRows).toHaveCount(2);
    await expect(page.locator('#results-master .summary-row[data-modified="true"]')).toHaveCount(2);
    await expect(page.locator('#results-master .summary-row .badge.modified')).toHaveCount(2);

    // Accept all (scoped to visible)
    await page.click('#accept-all-btn');
    await expect(page.locator('#results-master .summary-row[data-status="accepted"]')).toHaveCount(2);

    // Toggle off to inspect all; unmodified row should remain rejected
    await toggleBtn.click();
    await expect(page.locator('#results-master .summary-row')).toHaveCount(3);
    const unmodifiedRow = page.locator('#results-master .summary-row[data-modified="false"]');
    await expect(unmodifiedRow).toHaveCount(1);
    await expect(unmodifiedRow).toHaveAttribute('data-status', 'rejected');

    // Re-analyze modified should issue exactly 2 additional batch calls
    const baseline = batchCalls;
    await toggleBtn.click(); // on
    await page.click('[data-action="reanalyze-modified"]');
    await expect.poll(() => batchCalls).toBe(baseline + 2);
  });
});