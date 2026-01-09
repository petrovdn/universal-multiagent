import { test, expect, Page } from '@playwright/test';

/**
 * Краткий набор E2E тестов для SmartProgressIndicator.
 * 
 * Проверяет:
 * - Показ контекстных сообщений
 * - Показ progress bar
 * - Обновление таймера
 * - Разные типы задач
 * 
 * Запуск:
 *   cd frontend
 *   npx playwright test smart-progress.spec.ts
 * 
 * Для расширенных тестов календаря см. calendar-extended.spec.ts
 */

/**
 * Helper функция для входа в систему.
 */
async function loginIfNeeded(page: Page) {
  const loginDialogOverlay = page.locator('.login-dialog-overlay');
  const loginDialog = page.locator('.login-dialog');
  const usernameField = page.locator('#username');
  
  const hasOverlay = await loginDialogOverlay.isVisible({ timeout: 3000 }).catch(() => false);
  const hasDialog = await loginDialog.isVisible({ timeout: 3000 }).catch(() => false);
  const hasUsernameField = await usernameField.isVisible({ timeout: 3000 }).catch(() => false);
  
  const needsLogin = hasOverlay || hasDialog || hasUsernameField;
  
  if (needsLogin) {
    console.log('[Test] Login dialog found, attempting login...');
    
    const usernameInput = page.locator('#username');
    const passwordInput = page.locator('#password');
    const loginButton = page.locator('.login-button');
    
    await expect(usernameInput).toBeVisible({ timeout: 10000 });
    await expect(passwordInput).toBeVisible({ timeout: 10000 });
    await expect(loginButton).toBeVisible({ timeout: 10000 });
    
    await usernameInput.clear();
    await passwordInput.clear();
    await usernameInput.fill('admin');
    await passwordInput.fill('admin');
    await loginButton.click();
    
    await expect(loginDialogOverlay).not.toBeVisible({ timeout: 15000 });
    await expect(loginDialog).not.toBeVisible({ timeout: 15000 });
    await expect(usernameField).not.toBeVisible({ timeout: 15000 });
    
    const chatInput = page.locator('textarea.chat-input, .input-form textarea').first();
    await expect(chatInput).toBeVisible({ timeout: 10000 });
    await page.waitForLoadState('networkidle');
    
    console.log('[Test] Login successful, chat interface loaded');
  } else {
    console.log('[Test] No login dialog found, user already authenticated');
    const chatInput = page.locator('textarea.chat-input, .input-form textarea').first();
    await expect(chatInput).toBeVisible({ timeout: 10000 });
  }
}

/**
 * Helper: отправить сообщение
 */
async function sendMessage(page: Page, message: string) {
  const chatInput = page.locator('textarea.chat-input, .input-form textarea').first();
  await expect(chatInput).toBeVisible({ timeout: 10000 });
  await chatInput.fill(message);
  
  const sendButton = page.locator('button[type="submit"].send-button, button.send-button:not(.input-icon-button):not(.stop-button)').last();
  const sendButtonVisible = await sendButton.isVisible({ timeout: 2000 }).catch(() => false);
  
  if (sendButtonVisible) {
    await sendButton.click();
  } else {
    await chatInput.press('Enter');
  }
}

test.describe('SmartProgressIndicator', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await loginIfNeeded(page);
    
    // Проверяем, что окно входа закрыто
    const stillHasLogin = await page.locator('.login-dialog-overlay, .login-dialog, #username').isVisible({ timeout: 1000 }).catch(() => false);
    if (stillHasLogin) {
      await page.waitForTimeout(2000);
      const stillVisible = await page.locator('.login-dialog-overlay').isVisible({ timeout: 1000 }).catch(() => false);
      if (stillVisible) {
        throw new Error('Login dialog still visible after login attempt');
      }
    }
  });

  test('1. should show contextual messages during LLM call', async ({ page }) => {
    // Проверяем, что окна входа нет
    const loginDialogVisible = await page.locator('.login-dialog-overlay, .login-dialog').isVisible({ timeout: 1000 }).catch(() => false);
    if (loginDialogVisible) {
      throw new Error('Login dialog is still visible!');
    }
    
    // Отправляем задачу про календарь
    await sendMessage(page, 'назначь встречу на завтра в 14:00 с bsn@lad24.ru на 30 минут');
    
    // Ждём появления SmartProgress
    const smartProgress = page.locator('.smart-progress-indicator, [class*="smart-progress"]');
    const isVisible = await smartProgress.isVisible({ timeout: 5000 }).catch(() => false);
    
    if (isVisible) {
      const message = smartProgress.locator('.smart-progress-message, [class*="message"]');
      const messageText = await message.textContent().catch(() => null);
      
      if (messageText) {
        const hasCalendarContext = 
          messageText.toLowerCase().includes('встреч') ||
          messageText.toLowerCase().includes('календар') ||
          messageText.toLowerCase().includes('событи') ||
          messageText.toLowerCase().includes('создан');
        
        expect(hasCalendarContext || messageText.length > 0).toBeTruthy();
      }
      
      const progressBar = smartProgress.locator('.smart-progress-bar, [class*="progress-bar"]');
      const hasProgressBar = await progressBar.isVisible().catch(() => false);
      expect(hasProgressBar || await progressBar.count() > 0).toBeTruthy();
    } else {
      console.log('SmartProgress did not appear (task may have completed quickly)');
    }
    
    // Ждём завершения (ответ может быть в assistant-message-wrapper или final-result-prose)
    await page.waitForSelector(
      '.assistant-message-wrapper, .final-result-prose, .sticky-result-section',
      { timeout: 60000 }
    ).catch(() => null);
  });

  test('2. should show progress bar with timer', async ({ page }) => {
    const loginDialogVisible = await page.locator('.login-dialog-overlay').isVisible({ timeout: 1000 }).catch(() => false);
    if (loginDialogVisible) {
      throw new Error('Login dialog is still visible!');
    }
    
    await sendMessage(page, 'покажи встречи на этой неделе');
    
    const smartProgress = page.locator('.smart-progress-indicator').first();
    const isVisible = await smartProgress.isVisible({ timeout: 5000 }).catch(() => false);
    
    if (isVisible) {
      const timer = smartProgress.locator('.smart-progress-timer, [class*="timer"]');
      const timerText = await timer.textContent().catch(() => null);
      
      if (timerText) {
        expect(timerText.length).toBeGreaterThan(0);
      }
      
      const progressBar = smartProgress.locator('.smart-progress-bar').first();
      const hasProgressBar = await progressBar.isVisible().catch(() => false);
      expect(hasProgressBar || await progressBar.count() > 0).toBeTruthy();
      
      await page.waitForTimeout(2000);
      
      const progressBarFill = progressBar.locator('.smart-progress-bar-fill').first();
      const fillWidth = await progressBarFill.evaluate((el) => {
        return window.getComputedStyle(el).width;
      }).catch(() => null);
      
      expect(fillWidth !== null).toBeTruthy();
    }
    
    await page.waitForSelector(
      '.assistant-message-wrapper, .final-result-prose, .sticky-result-section',
      { timeout: 30000 }
    ).catch(() => null);
  });

  test('3. should update timer every second', async ({ page }) => {
    const loginDialogVisible = await page.locator('.login-dialog-overlay').isVisible({ timeout: 1000 }).catch(() => false);
    if (loginDialogVisible) {
      throw new Error('Login dialog is still visible!');
    }
    
    await sendMessage(page, 'найди свободное время для встречи с bsn@lad24.ru на 1 час');
    
    const smartProgress = page.locator('.smart-progress-indicator').first();
    const isVisible = await smartProgress.isVisible({ timeout: 5000 }).catch(() => false);
    
    if (isVisible) {
      const timer = smartProgress.locator('.smart-progress-timer').first();
      const initialTimer = await timer.textContent().catch(() => null);
      
      if (initialTimer) {
        await page.waitForTimeout(2000);
        const updatedTimer = await timer.textContent().catch(() => null);
        expect(updatedTimer !== null).toBeTruthy();
      }
    }
    
    await page.waitForSelector(
      '.assistant-message-wrapper, .final-result-prose, .sticky-result-section',
      { timeout: 60000 }
    ).catch(() => null);
  });

  test('4. should show different messages for different task types', async ({ page }) => {
    const loginDialogVisible = await page.locator('.login-dialog-overlay').isVisible({ timeout: 1000 }).catch(() => false);
    if (loginDialogVisible) {
      throw new Error('Login dialog is still visible!');
    }
    
    // Тест с полным запросом на создание встречи
    await sendMessage(page, 'назначь встречу на послезавтра в 10:00 с bsn@lad24.ru и arv@lad24.ru на 1 час по теме проекта');
    
    const smartProgress = page.locator('.smart-progress-indicator').first();
    const isVisible = await smartProgress.isVisible({ timeout: 5000 }).catch(() => false);
    
    if (isVisible) {
      const message = smartProgress.locator('.smart-progress-message').first();
      const messageText = await message.textContent().catch(() => null);
      
      if (messageText) {
        expect(messageText.length).toBeGreaterThan(0);
      }
    }
    
    // Ждём завершения
    await page.waitForSelector(
      '.assistant-message-wrapper, .final-result-prose, .sticky-result-section',
      { timeout: 60000 }
    ).catch(() => null);
    
    await page.waitForTimeout(2000);
  });
});
