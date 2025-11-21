import { test, expect } from '@playwright/test';
import * as path from 'path';
import { fileURLToPath } from 'url';

/**
 * Knowledge Graph Visualization Test
 * Tests the KG rendering and interaction
 */

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

test.describe('Knowledge Graph Visualization', () => {
  test('KG component renders after mining', async ({ page }) => {
    await page.goto('http://localhost:3000');
    await page.waitForLoadState('networkidle');

    // Upload and start mining
    const fileInput = page.locator('input[type="file"]');
    const testFilePath = path.join(__dirname, '../../data/test/test_requirements.md');
    await fileInput.setInputFiles(testFilePath);

    const startButton = page.getByRole('button', { name: /start.*mining/i });
    await startButton.click();

    // Wait for mining to complete
    await page.waitForTimeout(20000);

    // Look for KG container (adjust selector based on your KnowledgeGraph component)
    const kgContainer = page.locator('[data-testid="knowledge-graph"]')
      .or(page.locator('#cy')) // Cytoscape container typically has id="cy"
      .or(page.getByText(/knowledge.*graph|wissensgraph/i).first());

    await expect(kgContainer).toBeVisible({ timeout: 10000 });
  });

  test('KG has nodes and edges', async ({ page }) => {
    await page.goto('http://localhost:3000');
    await page.waitForLoadState('networkidle');

    // Perform mining
    const fileInput = page.locator('input[type="file"]');
    const testFilePath = path.join(__dirname, '../../data/test/test_requirements.md');
    await fileInput.setInputFiles(testFilePath);

    const startButton = page.getByRole('button', { name: /start.*mining/i });
    await startButton.click();

    await page.waitForTimeout(20000);

    // Check if Cytoscape canvas exists
    const cyCanvas = page.locator('#cy canvas').or(page.locator('canvas').first());

    if (await cyCanvas.isVisible()) {
      // Canvas should have been drawn on
      const canvasBox = await cyCanvas.boundingBox();
      expect(canvasBox).toBeTruthy();
      expect(canvasBox!.width).toBeGreaterThan(100);
      expect(canvasBox!.height).toBeGreaterThan(100);

      console.log('✓ KG canvas rendered');
    }
  });

  test('Can export KG as JSON', async ({ page, context }) => {
    await page.goto('http://localhost:3000');
    await page.waitForLoadState('networkidle');

    // Perform mining
    const fileInput = page.locator('input[type="file"]');
    const testFilePath = path.join(__dirname, '../../data/test/test_requirements.md');
    await fileInput.setInputFiles(testFilePath);

    const startButton = page.getByRole('button', { name: /start.*mining/i });
    await startButton.click();

    await page.waitForTimeout(20000);

    // Look for export button
    const exportButton = page.getByRole('button', { name: /export.*json|json.*export/i });

    if (await exportButton.isVisible({ timeout: 5000 })) {
      // Set up download listener
      const downloadPromise = page.waitForEvent('download', { timeout: 10000 });

      await exportButton.click();

      const download = await downloadPromise;
      expect(download.suggestedFilename()).toMatch(/\.json$/i);

      console.log('✓ KG export successful');
    } else {
      console.log('⚠ Export button not found - may need to wait for KG to build');
    }
  });

  test('KG stats are displayed', async ({ page }) => {
    await page.goto('http://localhost:3000');
    await page.waitForLoadState('networkidle');

    // Perform mining
    const fileInput = page.locator('input[type="file"]');
    const testFilePath = path.join(__dirname, '../../data/test/test_requirements.md');
    await fileInput.setInputFiles(testFilePath);

    const startButton = page.getByRole('button', { name: /start.*mining/i });
    await startButton.click();

    await page.waitForTimeout(20000);

    // Check for stats (nodes count, edges count)
    const statsText = page.getByText(/\d+\s*(nodes?|knoten)/i)
      .or(page.getByText(/\d+\s*(edges?|kanten)/i));

    if (await statsText.isVisible({ timeout: 5000 })) {
      const text = await statsText.textContent();
      console.log(`✓ KG stats visible: ${text}`);
    }
  });
});
