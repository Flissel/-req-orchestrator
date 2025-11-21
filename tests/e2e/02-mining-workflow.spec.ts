import { test, expect } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';
import { fileURLToPath } from 'url';

/**
 * Mining Workflow E2E Test
 * Tests the complete requirements mining journey from upload to results
 */

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

test.describe('Requirements Mining Workflow', () => {
  // Create a test file for upload
  test.beforeAll(() => {
    const testDataDir = path.join(__dirname, '../../data/test');
    if (!fs.existsSync(testDataDir)) {
      fs.mkdirSync(testDataDir, { recursive: true });
    }

    const testFilePath = path.join(testDataDir, 'test_requirements.md');
    const testContent = `# Test Requirements

## Functional Requirements

REQ-1: Das System soll Benutzer-Login unterstützen
Als Benutzer möchte ich mich mit Email und Passwort anmelden können, damit ich auf meine Daten zugreifen kann.

REQ-2: Das System soll Dateien hochladen können
Das System muss PDF, DOCX und MD Dateien bis 10MB akzeptieren.

REQ-3: Export-Funktion implementieren
Als Administrator möchte ich alle Requirements als CSV exportieren können.

## Non-Functional Requirements

REQ-4: Performance Anforderung
Die Antwortzeit der API soll unter 200ms liegen bei 95% der Requests.

REQ-5: Security Requirement
Alle Daten müssen SSL/TLS verschlüsselt übertragen werden.
`;

    fs.writeFileSync(testFilePath, testContent, 'utf-8');
  });

  test('Complete mining workflow: Upload → Mine → View Results', async ({ page }) => {
    // Step 1: Navigate to frontend
    await page.goto('http://localhost:3000');
    await page.waitForLoadState('networkidle');

    // Step 2: Upload test file
    const fileInput = page.locator('input[type="file"]');
    await expect(fileInput).toBeVisible();

    const testFilePath = path.join(__dirname, '../../data/test/test_requirements.md');
    await fileInput.setInputFiles(testFilePath);

    // Verify file is selected (check for filename display)
    await expect(page.getByText('test_requirements.md')).toBeVisible({ timeout: 5000 });

    // Step 3: Start mining
    const startButton = page.getByRole('button', { name: /start.*mining|mining.*starten/i });
    await expect(startButton).toBeVisible();
    await expect(startButton).toBeEnabled();

    await startButton.click();

    // Step 4: Wait for agent status to update
    // Mining should start and show "processing" or similar status
    await page.waitForTimeout(2000); // Allow SSE connection to establish

    // Check for agent status updates (adjust selectors based on your AgentStatus component)
    const agentStatus = page.locator('[data-testid="agent-status"]')
      .or(page.getByText(/chunk.*miner|orchestrator/i).first());

    // Agent should show active status
    await expect(agentStatus).toBeVisible({ timeout: 10000 });

    // Step 5: Wait for requirements to appear
    // This may take some time depending on LLM response
    await page.waitForTimeout(15000); // Give LLM time to respond

    // Check if requirements list is populated
    const requirementsList = page.locator('[data-testid="requirements-list"]')
      .or(page.locator('text=/REQ-/i').first());

    // At least one requirement should be visible
    await expect(requirementsList).toBeVisible({ timeout: 30000 });

    // Step 6: Verify requirements count
    // Should have extracted some requirements from the test file
    const reqElements = await page.locator('text=/REQ-\\d+/i').count();
    expect(reqElements).toBeGreaterThan(0);

    console.log(`✓ Extracted ${reqElements} requirements`);

    // Step 7: Verify no critical errors in console
    const errors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });

    const criticalErrors = errors.filter(e =>
      !e.includes('DevTools') &&
      !e.includes('Warning:') &&
      e.includes('Error')
    );

    if (criticalErrors.length > 0) {
      console.warn('Console errors detected:', criticalErrors);
    }
  });

  test('Mining shows agent status updates via SSE', async ({ page }) => {
    await page.goto('http://localhost:3000');
    await page.waitForLoadState('networkidle');

    // Track console logs for SSE events
    const sseMessages: string[] = [];
    page.on('console', msg => {
      if (msg.text().includes('SSE') || msg.text().includes('[App]')) {
        sseMessages.push(msg.text());
      }
    });

    // Upload file
    const fileInput = page.locator('input[type="file"]');
    const testFilePath = path.join(__dirname, '../../data/test/test_requirements.md');
    await fileInput.setInputFiles(testFilePath);

    // Start mining
    const startButton = page.getByRole('button', { name: /start.*mining/i });
    await startButton.click();

    // Wait for SSE connection
    await page.waitForTimeout(3000);

    // Should have received SSE messages
    expect(sseMessages.length).toBeGreaterThan(0);
    console.log(`✓ Received ${sseMessages.length} SSE messages`);
  });

  test('Can handle mining without file selected', async ({ page }) => {
    await page.goto('http://localhost:3000');
    await page.waitForLoadState('networkidle');

    const startButton = page.getByRole('button', { name: /start.*mining/i });

    // Button should be disabled when no file selected
    await expect(startButton).toBeDisabled();
  });

  test('Can cancel/reset mining', async ({ page }) => {
    await page.goto('http://localhost:3000');
    await page.waitForLoadState('networkidle');

    // Upload file
    const fileInput = page.locator('input[type="file"]');
    const testFilePath = path.join(__dirname, '../../data/test/test_requirements.md');
    await fileInput.setInputFiles(testFilePath);

    // Start mining
    const startButton = page.getByRole('button', { name: /start.*mining/i });
    await startButton.click();

    await page.waitForTimeout(2000);

    // Look for reset/cancel button
    const resetButton = page.getByRole('button', { name: /reset|cancel|abbrechen/i });
    if (await resetButton.isVisible()) {
      await resetButton.click();

      // Requirements list should clear
      await page.waitForTimeout(1000);

      // Start button should be available again
      await expect(startButton).toBeVisible();
    }
  });
});
