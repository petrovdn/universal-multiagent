import { test, expect } from '@playwright/test';

/**
 * E2E тест для воспроизведения бага с лимитом итераций (10).
 * 
 * Запрос: "из документа сказка составь пошаговый план действий в виде военных
 * приказов персонажам. Далее сделай новую таблицу, и в нее внеси данные:
 * Персонаж, Кличка, Позывной, Приказ (по всем действиям, которые делали
 * персонажи). Потом из этой таблицы сделай еще один документ, который
 * называется "Отчет о выполнении приказов животными""
 * 
 * Ожидаемое поведение: Агент должен завершить задачу или вернуть осмысленный ответ
 * Фактическое поведение: Достигается лимит итераций (10)
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
        hypothesisId: 'E2E_SKAZKA',
        source: 'playwright'
      })
    });
  } catch (e) {
    // Ignore log errors
  }
}

/**
 * Helper функция для входа в систему.
 */
async function loginIfNeeded(page: any) {
  const loginDialogOverlay = page.locator('.login-dialog-overlay');
  const loginDialog = page.locator('.login-dialog');
  const loginTitle = page.locator('.login-dialog-title, h2:has-text("Вход в систему")');
  const usernameField = page.locator('#username');
  
  const hasOverlay = await loginDialogOverlay.isVisible({ timeout: 3000 }).catch(() => false);
  const hasDialog = await loginDialog.isVisible({ timeout: 3000 }).catch(() => false);
  const hasTitle = await loginTitle.isVisible({ timeout: 3000 }).catch(() => false);
  const hasUsernameField = await usernameField.isVisible({ timeout: 3000 }).catch(() => false);
  
  const needsLogin = hasOverlay || hasDialog || hasTitle || hasUsernameField;
  
  await logDebug('skazka:login:check', 'Login check result', { needsLogin, hasOverlay, hasDialog, hasTitle, hasUsernameField });
  
  if (needsLogin) {
    await logDebug('skazka:login', 'Login dialog found, attempting login', {});
    
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
    await logDebug('skazka:login', 'Login successful', {});
  } else {
    await logDebug('skazka:login', 'No login dialog, already authenticated', {});
    const chatInput = page.locator('textarea.chat-input, .input-form textarea').first();
    await expect(chatInput).toBeVisible({ timeout: 10000 });
  }
}

test.describe('Skazka Iteration Limit Bug', () => {
  
  test.beforeEach(async ({ page }) => {
    await logDebug('skazka:beforeEach', 'Opening page', { url: '/' });
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await logDebug('skazka:beforeEach', 'Page loaded', {});
    await loginIfNeeded(page);
  });

  test('should not hit iteration limit for complex document task', async ({ page }) => {
    // Увеличиваем таймаут для сложного запроса
    test.setTimeout(180000); // 3 минуты
    
    await logDebug('skazka:test:start', 'Starting skazka iteration limit test', {});
    
    const chatInput = page.locator('textarea.chat-input, .input-form textarea').first();
    await expect(chatInput).toBeVisible({ timeout: 10000 });
    await logDebug('skazka:test', 'Found chat input', {});
    
    // Точный запрос из скриншота
    const testMessage = `из документа сказка составь пошаговый план действий в виде военных приказов персонажам. Далее сделай новую таблицу, и в нее внеси данные: Персонаж, Кличка, Позывной, Приказ (по всем действиям, которые делали персонажи). Потом из этой таблицы сделай еще один документ, который называется "Отчет о выполнении приказов животными"`;
    
    await chatInput.fill(testMessage);
    await logDebug('skazka:test', 'Filled message', { messageLength: testMessage.length });
    
    // Отправляем сообщение
    const sendButton = page.locator('button[type="submit"].send-button, button.send-button:not(.input-icon-button):not(.stop-button)').last();
    const sendButtonVisible = await sendButton.isVisible({ timeout: 2000 }).catch(() => false);
    
    await logDebug('skazka:test:send', 'Send button check', { sendButtonVisible });
    
    if (sendButtonVisible) {
      await sendButton.click();
      await logDebug('skazka:test', 'Clicked send button', {});
    } else {
      await chatInput.press('Enter');
      await logDebug('skazka:test', 'Pressed Enter', {});
    }
    
    // Ждём начала обработки
    await logDebug('skazka:test', 'Waiting for response...', {});
    
    // Следим за появлением ошибки лимита итераций
    const startTime = Date.now();
    let iterationLimitReached = false;
    let responseReceived = false;
    let lastLogTime = startTime;
    
    // Опрашиваем страницу каждые 3 секунды
    while (Date.now() - startTime < 150000) { // 2.5 минуты максимум
      await page.waitForTimeout(3000);
      
      const currentTime = Date.now();
      const elapsed = (currentTime - startTime) / 1000;
      
      // Проверяем наличие сообщения об ошибке лимита итераций
      const iterationLimitMessage = await page.locator('text=лимит итераций').isVisible().catch(() => false);
      const iterationLimitMessageEng = await page.locator('text=iteration limit').isVisible().catch(() => false);
      const iterationLimitMessage10 = await page.locator('text=Достигнут лимит итераций (10)').isVisible().catch(() => false);
      
      if (iterationLimitMessage || iterationLimitMessageEng || iterationLimitMessage10) {
        iterationLimitReached = true;
        await logDebug('skazka:test:ERROR', 'ITERATION LIMIT REACHED', { 
          elapsed,
          iterationLimitMessage,
          iterationLimitMessageEng,
          iterationLimitMessage10
        });
        break;
      }
      
      // Проверяем успешный ответ
      const assistantMessage = await page.locator('[data-testid="assistant-message"], [class*="assistant"], .markdown').first().isVisible().catch(() => false);
      const finalResult = await page.locator('[class*="final-result"]').isVisible().catch(() => false);
      
      // Проверяем наличие индикатора обработки
      const isProcessing = await page.locator('[class*="typing"], [class*="loading"], [class*="thinking"]').isVisible().catch(() => false);
      
      // Логируем прогресс каждые 10 секунд
      if (currentTime - lastLogTime > 10000) {
        await logDebug('skazka:test:progress', 'Progress check', { 
          elapsed,
          assistantMessage,
          finalResult,
          isProcessing
        });
        lastLogTime = currentTime;
      }
      
      // Если есть сообщение и нет обработки - возможно завершилось
      if ((assistantMessage || finalResult) && !isProcessing) {
        // Ждём ещё немного чтобы убедиться что обработка завершилась
        await page.waitForTimeout(2000);
        const stillProcessing = await page.locator('[class*="typing"], [class*="loading"], [class*="thinking"]').isVisible().catch(() => false);
        
        if (!stillProcessing) {
          responseReceived = true;
          await logDebug('skazka:test:SUCCESS', 'Response received without iteration limit', { elapsed });
          break;
        }
      }
    }
    
    // Собираем финальную информацию
    const pageContent = await page.content();
    const hasIterationLimitInHtml = pageContent.includes('лимит итераций') || pageContent.includes('iteration limit');
    
    await logDebug('skazka:test:final', 'Test completed', { 
      iterationLimitReached,
      responseReceived,
      hasIterationLimitInHtml,
      totalElapsed: (Date.now() - startTime) / 1000
    });
    
    // Делаем скриншот для отладки
    await page.screenshot({ path: 'test-results/skazka-result.png', fullPage: true });
    
    // Assertions
    if (iterationLimitReached) {
      // Тест показывает баг - записываем информацию
      await logDebug('skazka:test:BUG_CONFIRMED', 'Bug confirmed: iteration limit reached', {});
      
      // Получаем HTML для анализа
      const responseArea = await page.locator('[class*="message"], [class*="response"]').allTextContents();
      await logDebug('skazka:test:response_content', 'Response area content', { 
        content: responseArea.join('\n').slice(0, 1000) 
      });
      
      // Тест должен падать, показывая баг
      expect(iterationLimitReached, 'Iteration limit should not be reached').toBe(false);
    }
    
    // Если не было ни ошибки, ни ответа - таймаут
    if (!iterationLimitReached && !responseReceived) {
      await logDebug('skazka:test:TIMEOUT', 'Test timed out without response', {});
      throw new Error('Test timed out without receiving response or hitting iteration limit');
    }
    
    await logDebug('skazka:test:end', 'Test completed successfully', { success: responseReceived });
  });
});
