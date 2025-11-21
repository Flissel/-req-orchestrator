import { test, expect } from '@playwright/test';

/**
 * SSE Connection Tests
 *
 * Verifies that Server-Sent Events (SSE) connections establish successfully
 * and reach OPEN state despite Firefox CORS warnings.
 *
 * Evidence from console logs:
 * ✅ [ClarificationModal] Connected to session: session-XXX
 * ✅ [Chat] Workflow SSE connected: session-XXX
 * ✅ [Chat] Clarification SSE connected: session-XXX
 * ⚠️ Cross-Origin Request Blocked (warning appears AFTER successful connection)
 *
 * Key Insight: CORS warnings appear after connections succeed.
 * This is expected Firefox behavior for EventSource with cross-origin URLs.
 */

test.describe('SSE Connection Tests', () => {

  test('All three SSE connections establish successfully', async ({ page }) => {
    // Track connection logs
    const connectionLogs: string[] = [];
    const debugLogs: string[] = [];

    page.on('console', msg => {
      const text = msg.text();

      // Track "connected" messages
      if (text.includes('SSE connected') || text.includes('Connected to session')) {
        connectionLogs.push(text);
      }

      // Track SSE debug messages
      if (text.includes('[SSE-Debug]')) {
        debugLogs.push(text);
      }
    });

    // Navigate to app
    await page.goto('http://localhost:3000');
    await page.waitForLoadState('domcontentloaded');

    // Wait for React root
    const root = page.locator('#root');
    await expect(root).toBeVisible({ timeout: 10000 });

    // Wait for SSE connections to establish
    await page.waitForTimeout(3000);

    // Verify all 3 "connected" logs appeared
    expect(connectionLogs.length).toBeGreaterThanOrEqual(3);

    // Check for specific connection messages
    const hasClarificationModal = connectionLogs.some(log =>
      log.includes('ClarificationModal') && log.includes('Connected to session')
    );
    const hasWorkflowSSE = connectionLogs.some(log =>
      log.includes('Workflow SSE connected')
    );
    const hasClarificationChat = connectionLogs.some(log =>
      log.includes('Clarification SSE connected')
    );

    expect(hasClarificationModal).toBeTruthy();
    expect(hasWorkflowSSE).toBeTruthy();
    expect(hasClarificationChat).toBeTruthy();

    console.log(`✅ All 3 SSE connections established: ${connectionLogs.length} connection logs`);
  });

  test('SSE connections reach OPEN state (readyState === 1)', async ({ page }) => {
    await page.goto('http://localhost:3000');
    await page.waitForLoadState('domcontentloaded');

    const root = page.locator('#root');
    await expect(root).toBeVisible({ timeout: 10000 });

    // Wait for SSE connections to establish
    await page.waitForTimeout(3000);

    // Check EventSource readyState via exposed instances
    const sseStates = await page.evaluate(() => {
      const connections = (window as any).__sseConnections;

      if (!connections) {
        return { error: 'SSE connections not exposed to window' };
      }

      return {
        workflow: connections.workflow?.readyState,
        clarificationChat: connections.clarificationChat?.readyState,
        clarificationModal: connections.clarificationModal?.readyState
      };
    });

    // EventSource.OPEN === 1
    expect(sseStates.workflow).toBe(1);
    expect(sseStates.clarificationChat).toBe(1);
    expect(sseStates.clarificationModal).toBe(1);

    console.log('✅ All SSE connections in OPEN state (readyState = 1)');
  });

  test('SSE debug utility logs connection lifecycle', async ({ page }) => {
    const debugLogs: string[] = [];

    page.on('console', msg => {
      const text = msg.text();
      if (text.includes('[SSE-Debug]')) {
        debugLogs.push(text);
      }
    });

    await page.goto('http://localhost:3000');
    await page.waitForLoadState('domcontentloaded');

    const root = page.locator('#root');
    await expect(root).toBeVisible({ timeout: 10000 });

    // Wait for SSE connections
    await page.waitForTimeout(3000);

    // Verify debug logs appeared
    expect(debugLogs.length).toBeGreaterThan(0);

    // Check for specific debug messages
    const hasInitialState = debugLogs.some(log => log.includes('Initial state'));
    const hasOpenState = debugLogs.some(log => log.includes('OPEN (connection established)'));
    const hasExposed = debugLogs.some(log => log.includes('Exposed window.__sseConnections'));

    expect(hasInitialState).toBeTruthy();
    expect(hasOpenState).toBeTruthy();
    expect(hasExposed).toBeTruthy();

    console.log(`✅ SSE debug utility working: ${debugLogs.length} debug logs`);
  });

  test('CORS warnings do not block SSE functionality', async ({ page }) => {
    const connectionLogs: string[] = [];
    const corsWarnings: string[] = [];

    page.on('console', msg => {
      const text = msg.text();

      if (text.includes('SSE connected') || text.includes('Connected to session')) {
        connectionLogs.push(text);
      }

      // Note: CORS warnings may appear in browser console but not always accessible via page.on('console')
      if (text.toLowerCase().includes('cross-origin') || text.toLowerCase().includes('cors')) {
        corsWarnings.push(text);
      }
    });

    await page.goto('http://localhost:3000');
    await page.waitForLoadState('domcontentloaded');

    const root = page.locator('#root');
    await expect(root).toBeVisible({ timeout: 10000 });

    // Wait for connections
    await page.waitForTimeout(3000);

    // Verify connections succeeded
    expect(connectionLogs.length).toBeGreaterThanOrEqual(3);

    // CORS warnings (if captured) are acceptable
    // But connections should work regardless
    console.log(`✅ Connections: ${connectionLogs.length}, CORS warnings: ${corsWarnings.length}`);
    console.log('✅ SSE functionality not blocked by CORS');
  });

  test('SSE connections exposed to window for debugging', async ({ page }) => {
    await page.goto('http://localhost:3000');
    await page.waitForLoadState('domcontentloaded');

    const root = page.locator('#root');
    await expect(root).toBeVisible({ timeout: 10000 });

    await page.waitForTimeout(3000);

    // Verify connections exposed to window
    const exposedConnections = await page.evaluate(() => {
      const connections = (window as any).__sseConnections;

      if (!connections) {
        return { exists: false };
      }

      return {
        exists: true,
        keys: Object.keys(connections),
        count: Object.keys(connections).length
      };
    });

    expect(exposedConnections.exists).toBeTruthy();
    expect(exposedConnections.count).toBe(3);
    expect(exposedConnections.keys).toContain('workflow');
    expect(exposedConnections.keys).toContain('clarificationChat');
    expect(exposedConnections.keys).toContain('clarificationModal');

    console.log('✅ SSE connections properly exposed to window.__sseConnections');
  });

  test('SSE connection URLs are correct', async ({ page }) => {
    await page.goto('http://localhost:3000');
    await page.waitForLoadState('domcontentloaded');

    const root = page.locator('#root');
    await expect(root).toBeVisible({ timeout: 10000 });

    await page.waitForTimeout(3000);

    // Check connection URLs
    const connectionURLs = await page.evaluate(() => {
      const connections = (window as any).__sseConnections;

      if (!connections) {
        return {};
      }

      return {
        workflow: connections.workflow?.url,
        clarificationChat: connections.clarificationChat?.url,
        clarificationModal: connections.clarificationModal?.url
      };
    });

    // Verify URLs contain expected patterns
    expect(connectionURLs.workflow).toContain('/api/workflow/stream?session_id=');
    expect(connectionURLs.clarificationChat).toContain('/api/clarification/stream?session_id=');
    expect(connectionURLs.clarificationModal).toContain('/api/clarification/stream?session_id=');

    // All should connect to localhost:8000 (hardcoded currently)
    expect(connectionURLs.workflow).toContain('http://localhost:8000');
    expect(connectionURLs.clarificationChat).toContain('http://localhost:8000');
    expect(connectionURLs.clarificationModal).toContain('http://localhost:8000');

    console.log('✅ SSE connection URLs verified');
  });
});
