import { test, expect } from '@playwright/test';

test.describe('Auto-refine - single item flow', () => {
  test('auto-refine this requirement reaches release gate', async ({ page }) => {
    // Mock demo requirements (1 item)
    await page.route('**/api/v1/demo/requirements', async (route) => {
      const json = { items: [{ id: 'R1', requirementText: 'Login requirement' }] };
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(json) });
    });

    // Mock batch endpoint: pass if text contains 'MERGED', else fail + suggestions
    let batchCalls = 0;
    await page.route('**/api/v1/validate/batch**', async (route) => {
      batchCalls++;
      let body: any = {};
      try { body = route.request().postDataJSON() || {}; } catch { body = {}; }
      const items: string[] = Array.isArray(body?.items) ? body.items : [''];
      const arr = items.map((t: string, i: number) => {
        const text = String(t || '');
        const isMerged = text.includes('MERGED');
        return {
          id: `mock-${Date.now()}-${i}`,
          originalText: text,
          correctedText: '',
          status: isMerged ? 'accepted' : 'rejected',
          evaluation: isMerged ? [{ criterion: 'ok', isValid: true }] : [],
          score: isMerged ? 0.91 : 0.2,
          verdict: isMerged ? 'pass' : 'fail',
          suggestions: isMerged ? [] : [{ correction: `MERGED: ${text}` }]
        };
      });
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(arr) });
    });

    // Mock suggestions endpoint (fallback if not provided by batch)
    await page.route('**/api/v1/validate/suggest', async (route) => {
      let body: any = [];
      try { body = route.request().postDataJSON() || []; } catch { body = []; }
      const original = Array.isArray(body) ? String(body[0] || '') : '';
      const suggestions = [{ correction: `MERGED: ${original}` }];
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(suggestions) });
    });

    // Mock apply endpoint to produce merged text
    await page.route('**/api/v1/corrections/apply', async (route) => {
      let body: any = {};
      try { body = route.request().postDataJSON() || {}; } catch { body = {}; }
      const original = String(body?.originalText || '');
      const response = { evaluationId: 'ev1', items: [{ rewrittenId: 1, redefinedRequirement: `MERGED: ${original}` }] };
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(response) });
    });

    // Open app and process
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await page.click('#load-btn');
    await page.click('#process-btn');
    const row = page.locator('#results-master .summary-row').first();
    await expect(row).toBeVisible();

    // Trigger auto-refine on the current item
    await page.click('[data-action="auto-refine-one"]');

    // Expect result is released (OK)
    await expect(row.locator('[data-role="status-badge"]')).toHaveText('OK');
    await expect(page.locator('#ok-indicator')).toHaveText(/All OK/i);
  });
});

test.describe('Auto-refine - open issues scoped by Use modified', () => {
  test('header action only processes visible open issues when Use modified is active', async ({ page }) => {
    // Mock demo requirements (3 items)
    await page.route('**/api/v1/demo/requirements', async (route) => {
      const json = { items: [
        { id: 'R1', requirementText: 'A' },
        { id: 'R2', requirementText: 'B' },
        { id: 'R3', requirementText: 'C' }
      ]};
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(json) });
    });

    // Batch: initial fail, pass when text contains 'MERGED'
    let batchCalls = 0;
    await page.route('**/api/v1/validate/batch**', async (route) => {
      batchCalls++;
      let body: any = {};
      try { body = route.request().postDataJSON() || {}; } catch { body = {}; }
      const items: string[] = Array.isArray(body?.items) ? body.items : [''];
      const arr = items.map((t: string, i: number) => {
        const text = String(t || '');
        const isMerged = text.includes('MERGED');
        return {
          id: `mock-${Date.now()}-${i}`,
          originalText: text,
          correctedText: '',
          status: isMerged ? 'accepted' : 'rejected',
          evaluation: isMerged ? [{ criterion: 'ok', isValid: true }] : [],
          score: isMerged ? 0.9 : 0.2,
          verdict: isMerged ? 'pass' : 'fail'
        };
      });
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(arr) });
    });

    // Suggestions and apply
    await page.route('**/api/v1/validate/suggest', async (route) => {
      let body: any = [];
      try { body = route.request().postDataJSON() || []; } catch { body = []; }
      const original = Array.isArray(body) ? String(body[0] || '') : '';
      const suggestions = [{ correction: `MERGED: ${original}` }];
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(suggestions) });
    });
    await page.route('**/api/v1/corrections/apply', async (route) => {
      let body: any = {};
      try { body = route.request().postDataJSON() || {}; } catch { body = {}; }
      const original = String(body?.originalText || '');
      const response = { evaluationId: 'ev2', items: [{ rewrittenId: 1, redefinedRequirement: `MERGED: ${original}` }] };
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(response) });
    });

    // Open and process
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await page.click('#load-btn');
    await page.click('#process-btn');

    // Mark index 0 and 2 as modified in left editors
    await page.fill('#req-list .req-collapsed[data-idx="0"] .editable-input', 'A modified');
    await page.fill('#req-list .req-collapsed[data-idx="2"] .editable-input', 'C modified');

    // Activate Use modified mode
    const toggleBtn = page.locator('[data-action="toggle-modified"]');
    await toggleBtn.click();
    await expect(toggleBtn).toHaveAttribute('aria-pressed', 'true');

    // Baseline batch calls so far
    const baseline = batchCalls;

    // Trigger header auto-refine for visible open issues (should be 2)
    await page.click('[data-action="auto-refine-open"]');

    // Expect two additional re-analysis calls (one per visible item)
    await expect.poll(() => batchCalls).toBe(baseline + 2);

    // And both visible rows become OK
    const visRows = page.locator('#results-master .summary-row');
    await expect(visRows).toHaveCount(2);
    await expect(visRows.nth(0).locator('[data-role="status-badge"]')).toHaveText('OK');
    await expect(visRows.nth(1).locator('[data-role="status-badge"]')).toHaveText('OK');
  });
});

test.describe('Auto-refine - escalation to manual review', () => {
  test('adds Review badge when max iterations are exhausted', async ({ page }) => {
    // Mock demo requirements (1 item)
    await page.route('**/api/v1/demo/requirements', async (route) => {
      const json = { items: [{ id: 'R1', requirementText: 'Unclear requirement' }] };
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(json) });
    });

    // Batch: always fail regardless of text
    await page.route('**/api/v1/validate/batch**', async (route) => {
      let body: any = {};
      try { body = route.request().postDataJSON() || {}; } catch { body = {}; }
      const items: string[] = Array.isArray(body?.items) ? body.items : [''];
      const arr = items.map((t: string, i: number) => ({
        id: `mock-${Date.now()}-${i}`,
        originalText: String(t || ''),
        correctedText: '',
        status: 'rejected',
        evaluation: [],
        score: 0.1,
        verdict: 'fail'
      }));
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(arr) });
    });

    // Suggestions: provide one atom
    await page.route('**/api/v1/validate/suggest', async (route) => {
      let body: any = [];
      try { body = route.request().postDataJSON() || []; } catch { body = []; }
      const original = Array.isArray(body) ? String(body[0] || '') : '';
      const suggestions = [{ correction: `TRY: ${original}` }];
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(suggestions) });
    });

    // Apply: return some merged text, but batch will still fail
    await page.route('**/api/v1/corrections/apply', async (route) => {
      let body: any = {};
      try { body = route.request().postDataJSON() || {}; } catch { body = {}; }
      const original = String(body?.originalText || '');
      const response = { evaluationId: 'ev3', items: [{ rewrittenId: 1, redefinedRequirement: `TRY: ${original}` }] };
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(response) });
    });

    // Open and process
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await page.click('#load-btn');
    await page.click('#process-btn');

    // Trigger item-level auto-refine
    await page.click('[data-action="auto-refine-one"]');

    // Expect Review badge appears on the row after loop
    const row = page.locator('#results-master .summary-row').first();
    await expect(row.locator('.badge.review')).toBeVisible();
    // And status remains error
    await expect(row.locator('[data-role="status-badge"]')).toHaveText(/Fehler/i);
  });
});