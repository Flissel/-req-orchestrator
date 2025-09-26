import { test, expect } from '@playwright/test';

test.describe('Apply Suggestion - LLM Apply Endpoint Integration', () => {
  test('promote updates correction textarea via /api/v1/corrections/apply', async ({ page }) => {
    // Mock: Demo requirements
    await page.route('**/api/v1/demo/requirements', async (route) => {
      const json = {
        items: [
          { id: 'R1', requirementText: 'Das System soll Logins verarbeiten.', context: '{}' }
        ]
      };
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(json) });
    });

    // Mock: Batch results including suggestions (atoms)
    await page.route('**/api/v1/validate/batch**', async (route) => {
      const json = [
        {
          id: 1,
          originalText: 'Das System soll Logins verarbeiten.',
          correctedText: '',
          status: 'rejected',
          evaluation: [],
          score: 0.42,
          verdict: 'fail',
          suggestions: [
            {
              correction: 'Das System soll Logins innerhalb von ≤200 ms (p95) unter 30 RPS verarbeiten.',
              acceptance_criteria: [
                'Given ein System im Normalbetrieb',
                'When Nutzer sich anmelden',
                'Then erfolgt die Anmeldung innerhalb von 200 ms (p95)'
              ],
              metrics: [{ name: 'response_time_ms', op: '<=', value: 200, context: 'Ref-Env 30RPS, p95' }]
            }
          ]
        }
      ];
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(json) });
    });

    // Mock: Apply endpoint - return newly redefined requirement
    await page.route('**/api/v1/corrections/apply', async (route) => {
      let body: any = {}; try { body = route.request().postDataJSON() || {}; } catch { body = {}; }
      // Basic guard: require selectedSuggestions
      const hasSelection = body && Array.isArray(body.selectedSuggestions) && body.selectedSuggestions.length > 0;
      const response = {
        evaluationId: 'ev_mock',
        items: hasSelection
          ? [{ rewrittenId: 1, redefinedRequirement: 'NEUE FASSUNG: Logins ≤200 ms (p95) bei 30 RPS.' }]
          : []
      };
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(response) });
    });

    // Open optimized UI
    await page.goto('/', { waitUntil: 'domcontentloaded' });

    // Load requirements
    await page.click('#load-btn');
    await expect(page.locator('#requirements-section')).toBeVisible();

    // Process (batch) - mocked above
    await page.click('#process-btn');

    // Suggestions section should appear (from mocked batch response)
    const suggSection = page.locator('section.detail-section.suggestions');
    await expect(suggSection).toBeVisible();

    // Click "Promote" on the first suggestion (calls /api/v1/corrections/apply)
    await page.click('[data-action="promote-suggestion"]');

    // Textarea should be updated with the text from apply-response
    const ta = page.locator('#correction-textarea');
    await expect(ta).toHaveValue('NEUE FASSUNG: Logins ≤200 ms (p95) bei 30 RPS.');
  });
});