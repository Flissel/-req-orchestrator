import { test, expect } from '@playwright/test';

// UI Regression test for index_optimized.html using Playwright
// - Mocks the batch endpoint to control the results and avoid backend flakiness (HTTP 500)
// - Verifies header actions (Accept all / Reject all), counter pills, per-item Accept/Reject, filters, collapsible details, and correction textarea

test.describe('Optimized UI - Results rendering and interactions', () => {
  test.skip('should load requirements, mock processing, and support accept/reject + filters', async ({ page }) => {
    // Intercept batch processing POST and return a stable response
    await page.route('**/api/validate/batch**', async (route) => {
      const json = [
        {
          originalText: 'The vehicle attendant must have the ability to monitor the status of the shuttle.',
          correctedText: 'The vehicle attendant must be able to view the real-time status of the shuttle, including location, occupancy, and operational state, on a digital display at least every 1 second.',
          evaluation: [
            { criterion: 'clarity_sentence', isValid: true },
            { criterion: 'testability_metric', isValid: true },
            { criterion: 'measurability_value', isValid: true }
          ],
          status: 'accepted',
          score: 0.92
        },
        {
          originalText: 'Das Shuttle muss manuell rückwärts fahren können.',
          correctedText: 'Das Shuttle muss die Möglichkeit haben, manuell im Rückwärtsgang zu fahren, wobei eine sichere Höchstgeschwindigkeit von 5 km/h definiert ist.',
          evaluation: [
            { criterion: 'clarity_phrasing', isValid: false, reason: 'Ambiguous phrasing' },
            { criterion: 'testability_observable', isValid: true },
            { criterion: 'measurability_threshold', isValid: false, reason: 'No measurable threshold defined' }
          ],
          status: 'rejected',
          score: 0.41
        }
      ];
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(json)
      });
    });

    // Open optimized frontend
    await page.goto('/index_optimized.html', { waitUntil: 'domcontentloaded' });

    // Load requirements from demo (real backend can respond; we just assert the UI reveals the list)
    await page.click('#load-btn');
    await expect(page.locator('#requirements-section')).toBeVisible();
    // Expect at least one requirement input item to be present
    await expect(page.locator('#requirements-display .item').first()).toBeVisible();

    // Start processing (mocked by our route above)
    await page.click('#process-btn');

    // Results header should appear with actions and pills
    await expect(page.locator('.results-header')).toBeVisible();
    await expect(page.locator('#accept-all-btn')).toBeVisible();
    await expect(page.locator('#reject-all-btn')).toBeVisible();

    // List should contain 2 results from our mock
    const resultsList = page.locator('#results-list .item');
    await expect(resultsList).toHaveCount(2);

    // Pills should reflect 1 accepted + 1 rejected initially
    await expect(page.locator('#pill-accepted')).toHaveText(/1/);
    await expect(page.locator('#pill-rejected')).toHaveText(/1/);

    // Expand first item and verify details/evaluation show
    const firstHead = resultsList.nth(0).locator('.item-head');
    await firstHead.click();
    await expect(resultsList.nth(0).locator('.details')).toBeVisible();
    await expect(resultsList.nth(0).locator('text=Evaluation')).toBeVisible();
    await expect(resultsList.nth(0).locator('textarea[data-role="correction"]')).toBeVisible();

    // Change status of second (rejected) item to accepted via per-item button
    const secondItem = resultsList.nth(1);
    await secondItem.locator('button.item-action-btn:has-text("Accept")').click();

    // Pills should update to 2 accepted + 0 rejected
    await expect(page.locator('#pill-accepted')).toHaveText(/2/);
    await expect(page.locator('#pill-rejected')).toHaveText(/0/);

    // Use filter buttons
    await page.click('#filter-rejected');
    await expect(page.locator('#results-list .item[data-status="rejected"]')).toHaveCount(0);

    await page.click('#filter-accepted');
    await expect(page.locator('#results-list .item[data-status="accepted"]')).toHaveCount(2);

    await page.click('#filter-all');
    await expect(resultsList).toHaveCount(2);
  });
});