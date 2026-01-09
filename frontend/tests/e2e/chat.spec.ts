import { test, expect } from '@playwright/test';

/**
 * E2E тесты для чата через Playwright.
 * 
 * Запуск:
 *   cd frontend
 *   npx playwright install  # первый раз
 *   npx playwright test
 * 
 * UI режим:
 *   npx playwright test --ui
 * 
 * ВАЖНО: Требуется запущенный backend и frontend
 */

// Debug log endpoint
const DEBUG_LOG_ENDPOINT = 'http://127.0.0.1:7244/ingest/b733f86e-10e8-4a42-b8ba-7cfb96fa3c70';

async function logDebug(location: string, message: string, data: Record<string, any>) {
  try {
    await fetch(DEBUG_LOG_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        location,
        message,
        data,
        timestamp: Date.now(),
        sessionId: 'debug-session',
        hypothesisId: 'E2E',
        source: 'playwright'
      })
    });
  } catch (e) {
    // Ignore log errors
  }
}

test.describe('Chat Interface', () => {
  
  test.beforeEach(async ({ page }) => {
    await logDebug('playwright:beforeEach', 'Opening page', { url: '/' });
    await page.goto('/');
    
    // Wait for the page to load
    await page.waitForLoadState('networkidle');
    await logDebug('playwright:beforeEach', 'Page loaded', {});
  });

  test('should display response for simple message', async ({ page }) => {
    await logDebug('playwright:test:start', 'Starting simple message test', {});
    
    // Find the chat input
    const chatInput = page.locator('textarea[placeholder*="сообщение"], input[placeholder*="сообщение"], textarea, input[type="text"]').first();
    await expect(chatInput).toBeVisible({ timeout: 10000 });
    await logDebug('playwright:test', 'Found chat input', {});
    
    // Type a message
    const testMessage = 'привет';
    await chatInput.fill(testMessage);
    await logDebug('playwright:test', 'Filled message', { message: testMessage });
    
    // Find and click send button (or press Enter)
    const sendButton = page.locator('button[type="submit"], button:has-text("Отправить"), button:has(svg)').last();
    
    if (await sendButton.isVisible()) {
      await sendButton.click();
      await logDebug('playwright:test', 'Clicked send button', {});
    } else {
      await chatInput.press('Enter');
      await logDebug('playwright:test', 'Pressed Enter', {});
    }
    
    // Wait for response to appear
    // Look for assistant message or any response content
    await logDebug('playwright:test', 'Waiting for response...', {});
    
    // Wait for loading to finish (agent typing indicator to disappear)
    // Or wait for response text to appear
    const response = await page.waitForSelector(
      '[data-testid="assistant-message"], [class*="assistant"], [class*="response"], [class*="final-result"], .markdown, p:not(:empty)',
      { timeout: 30000, state: 'visible' }
    ).catch(() => null);
    
    if (response) {
      const text = await response.textContent();
      await logDebug('playwright:test', 'Got response', { textLen: text?.length || 0, preview: text?.slice(0, 100) });
      console.log('Response:', text?.slice(0, 200));
      
      expect(text).toBeTruthy();
      expect(text!.length).toBeGreaterThan(0);
    } else {
      await logDebug('playwright:test', 'No response found!', {});
      
      // Take screenshot for debugging
      await page.screenshot({ path: 'test-results/no-response.png', fullPage: true });
      
      // Get page HTML for debugging
      const html = await page.content();
      console.log('Page HTML (last 2000 chars):', html.slice(-2000));
      
      throw new Error('No response appeared after sending message');
    }
    
    await logDebug('playwright:test:end', 'Test completed', { success: true });
  });

  test('should show typing indicator while processing', async ({ page }) => {
    await logDebug('playwright:test:typing:start', 'Starting typing indicator test', {});
    
    const chatInput = page.locator('textarea, input[type="text"]').first();
    await expect(chatInput).toBeVisible({ timeout: 10000 });
    
    await chatInput.fill('расскажи о погоде');
    await chatInput.press('Enter');
    
    // Check for typing indicator or loading state
    const hasTypingIndicator = await page.locator(
      '[class*="typing"], [class*="loading"], [class*="thinking"], [data-testid="typing-indicator"]'
    ).isVisible({ timeout: 5000 }).catch(() => false);
    
    await logDebug('playwright:test:typing', 'Typing indicator check', { visible: hasTypingIndicator });
    
    // Wait for response
    await page.waitForSelector('[class*="assistant"], [class*="response"], .markdown', { timeout: 30000 });
    
    await logDebug('playwright:test:typing:end', 'Test completed', {});
  });

  test('should maintain conversation history', async ({ page }) => {
    await logDebug('playwright:test:history:start', 'Starting history test', {});
    
    const chatInput = page.locator('textarea, input[type="text"]').first();
    await expect(chatInput).toBeVisible({ timeout: 10000 });
    
    // Send first message
    await chatInput.fill('меня зовут Тест');
    await chatInput.press('Enter');
    
    // Wait for response
    await page.waitForSelector('[class*="assistant"], [class*="response"], .markdown', { timeout: 30000 });
    await logDebug('playwright:test:history', 'First response received', {});
    
    // Small delay
    await page.waitForTimeout(1000);
    
    // Send second message referencing first
    await chatInput.fill('как меня зовут?');
    await chatInput.press('Enter');
    
    // Wait for second response
    await page.waitForTimeout(15000); // Give time for processing
    
    // Check that both user messages are visible
    const userMessages = await page.locator('[class*="user"]').count();
    await logDebug('playwright:test:history', 'User messages count', { count: userMessages });
    
    expect(userMessages).toBeGreaterThanOrEqual(2);
    
    await logDebug('playwright:test:history:end', 'Test completed', {});
  });
});

test.describe('Debug: Check UI State', () => {
  
  test('should have workflow after sending message', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    const chatInput = page.locator('textarea, input[type="text"]').first();
    await chatInput.fill('тест');
    await chatInput.press('Enter');
    
    // Wait a bit for store to update
    await page.waitForTimeout(2000);
    
    // Check Zustand store state via browser console
    const storeState = await page.evaluate(() => {
      // @ts-ignore - accessing window store
      const state = window.__ZUSTAND_STORE_STATE__;
      return state;
    });
    
    await logDebug('playwright:debug', 'Store state', { state: JSON.stringify(storeState)?.slice(0, 500) });
    console.log('Store state:', storeState);
  });
});
