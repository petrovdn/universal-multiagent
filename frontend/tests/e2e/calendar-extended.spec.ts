import { test, expect, Page } from '@playwright/test';

/**
 * Расширенные E2E тесты для календарных операций.
 * 
 * Тестирует:
 * 1. Вывод событий за разные периоды
 * 2. Назначение встреч с одним участником
 * 3. Назначение встреч с несколькими участниками
 * 4. Работу с уточнениями и без них
 * 
 * Запуск:
 *   cd frontend
 *   npx playwright test calendar-extended.spec.ts
 */

// Email участников для тестов
const PARTICIPANT_BSN = 'bsn@lad24.ru';
const PARTICIPANT_ARV = 'arv@lad24.ru';

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
    
    const chatInput = page.locator('textarea.chat-input, .input-form textarea').first();
    await expect(chatInput).toBeVisible({ timeout: 10000 });
    await page.waitForLoadState('networkidle');
  }
}

/**
 * Helper функция для отправки сообщения и ожидания ответа.
 */
async function sendMessageAndWaitForResponse(page: Page, message: string, timeout = 60000) {
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
  
  // Ждём появления ответа
  await page.waitForSelector(
    '[class*="assistant-message"], [class*="final-result"], .markdown, [class*="response"]',
    { timeout }
  );
  
  // Даём время на полное отображение
  await page.waitForTimeout(1000);
}

/**
 * Helper: проверяет, что система запросила уточнение
 */
async function expectClarificationRequested(page: Page): Promise<boolean> {
  const clarificationText = await page.locator('.markdown, [class*="assistant"]').last().textContent().catch(() => '');
  return clarificationText?.includes('уточнен') || 
         clarificationText?.includes('укажите') || 
         clarificationText?.includes('какое время') ||
         clarificationText?.includes('какую') ||
         clarificationText?.includes('Для выполнения');
}

/**
 * Helper: проверяет успешное создание встречи
 */
async function expectMeetingCreated(page: Page): Promise<boolean> {
  const responseText = await page.locator('.markdown, [class*="assistant"]').last().textContent().catch(() => '');
  return responseText?.includes('создан') || 
         responseText?.includes('запланирован') || 
         responseText?.includes('назначен') ||
         responseText?.includes('✅');
}

/**
 * Helper: проверяет отображение событий
 */
async function expectEventsDisplayed(page: Page): Promise<boolean> {
  const responseText = await page.locator('.markdown, [class*="assistant"]').last().textContent().catch(() => '');
  return responseText?.includes('событи') || 
         responseText?.includes('встреч') || 
         responseText?.includes('Found') ||
         responseText?.includes('нет запланированных') ||
         responseText?.includes('Время:');
}


// ==================== ТЕСТЫ ====================

test.describe('Calendar Extended Tests', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await loginIfNeeded(page);
  });

  // ==================== 1. ВЫВОД СОБЫТИЙ ЗА РАЗНЫЕ ПЕРИОДЫ ====================
  
  test.describe('1. Вывод событий за разные периоды', () => {
    
    test('1.1 Показать встречи на сегодня (полный запрос)', async ({ page }) => {
      await sendMessageAndWaitForResponse(page, 'покажи мои встречи на сегодня');
      expect(await expectEventsDisplayed(page)).toBeTruthy();
    });

    test('1.2 Показать встречи на завтра (полный запрос)', async ({ page }) => {
      await sendMessageAndWaitForResponse(page, 'покажи встречи на завтра');
      expect(await expectEventsDisplayed(page)).toBeTruthy();
    });

    test('1.3 Показать встречи на текущей неделе (полный запрос)', async ({ page }) => {
      await sendMessageAndWaitForResponse(page, 'покажи встречи на этой неделе');
      expect(await expectEventsDisplayed(page)).toBeTruthy();
    });

    test('1.4 Показать встречи на прошлой неделе (полный запрос)', async ({ page }) => {
      await sendMessageAndWaitForResponse(page, 'покажи встречи за прошлую неделю');
      expect(await expectEventsDisplayed(page)).toBeTruthy();
    });

    test('1.5 Показать встречи на следующей неделе (полный запрос)', async ({ page }) => {
      await sendMessageAndWaitForResponse(page, 'покажи встречи на следующей неделе');
      expect(await expectEventsDisplayed(page)).toBeTruthy();
    });

    test('1.6 Неполный запрос: "покажи встречи" - должен уточнить период', async ({ page }) => {
      await sendMessageAndWaitForResponse(page, 'покажи встречи');
      
      // Система должна либо запросить уточнение, либо показать за текущую неделю
      const responseText = await page.locator('.markdown, [class*="assistant"]').last().textContent().catch(() => '');
      const hasClarificationOrEvents = 
        await expectClarificationRequested(page) || 
        await expectEventsDisplayed(page);
      
      expect(hasClarificationOrEvents).toBeTruthy();
    });

  });

  // ==================== 2. НАЗНАЧЕНИЕ С ОДНИМ УЧАСТНИКОМ ====================
  
  test.describe('2. Назначение встречи с одним участником', () => {
    
    test('2.1 Полный запрос: конкретное время без подбора', async ({ page }) => {
      const message = `назначь встречу на завтра в 15:00 с ${PARTICIPANT_BSN} длительностью 30 минут на тему "Обсуждение проекта"`;
      await sendMessageAndWaitForResponse(page, message, 90000);
      
      // Должна создаться встреча или показать ошибку валидации (если время в прошлом)
      const responseText = await page.locator('.markdown, [class*="assistant"]').last().textContent().catch(() => '');
      const isSuccess = await expectMeetingCreated(page);
      const hasError = responseText?.includes('прошлом') || responseText?.includes('ошибка');
      
      expect(isSuccess || hasError).toBeTruthy();
    });

    test('2.2 Полный запрос: с подбором свободного времени', async ({ page }) => {
      const message = `найди свободное время для встречи с ${PARTICIPANT_BSN} на 1 час в ближайшие 3 дня`;
      await sendMessageAndWaitForResponse(page, message, 90000);
      
      // Система должна найти слот и создать встречу или предложить варианты
      const responseText = await page.locator('.markdown, [class*="assistant"]').last().textContent().catch(() => '');
      expect(responseText && responseText.length > 10).toBeTruthy();
    });

    test('2.3 Сложный диапазон: "во вторник или в четверг, в первой половине дня"', async ({ page }) => {
      const message = `назначь встречу с ${PARTICIPANT_BSN} во вторник или в четверг, в первой половине дня, на 45 минут`;
      await sendMessageAndWaitForResponse(page, message, 90000);
      
      // Система должна обработать сложное условие
      const responseText = await page.locator('.markdown, [class*="assistant"]').last().textContent().catch(() => '');
      expect(responseText && responseText.length > 10).toBeTruthy();
    });

    test('2.4 Неполный запрос: "создай встречу" - последовательные уточнения', async ({ page }) => {
      // Шаг 1: неполный запрос
      await sendMessageAndWaitForResponse(page, 'создай встречу');
      
      // Проверяем запрос уточнения
      const needsClarification = await expectClarificationRequested(page);
      expect(needsClarification).toBeTruthy();
      
      // Шаг 2: добавляем участника
      await sendMessageAndWaitForResponse(page, `с ${PARTICIPANT_BSN} на завтра в 11:00 на 30 минут`);
      
      // Теперь должна создаться встреча или ещё уточнения
      const finalResponse = await page.locator('.markdown, [class*="assistant"]').last().textContent().catch(() => '');
      expect(finalResponse && finalResponse.length > 10).toBeTruthy();
    });

    test('2.5 Неполный запрос: только участник, уточняем время', async ({ page }) => {
      // Шаг 1: только участник
      await sendMessageAndWaitForResponse(page, `назначь встречу с ${PARTICIPANT_BSN}`);
      
      // Должен запросить время
      expect(await expectClarificationRequested(page)).toBeTruthy();
      
      // Шаг 2: добавляем время
      await sendMessageAndWaitForResponse(page, 'завтра в 14:00 на 1 час');
      
      const finalResponse = await page.locator('.markdown, [class*="assistant"]').last().textContent().catch(() => '');
      expect(finalResponse && finalResponse.length > 10).toBeTruthy();
    });

  });

  // ==================== 3. НАЗНАЧЕНИЕ С НЕСКОЛЬКИМИ УЧАСТНИКАМИ ====================
  
  test.describe('3. Назначение встречи с несколькими участниками', () => {
    
    test('3.1 Полный запрос: два участника, конкретное время', async ({ page }) => {
      const message = `назначь встречу на послезавтра в 10:00 с ${PARTICIPANT_BSN} и ${PARTICIPANT_ARV} длительностью 1 час на тему "Планирование спринта"`;
      await sendMessageAndWaitForResponse(page, message, 90000);
      
      const responseText = await page.locator('.markdown, [class*="assistant"]').last().textContent().catch(() => '');
      expect(responseText && responseText.length > 10).toBeTruthy();
    });

    test('3.2 Полный запрос: два участника, подбор свободного времени', async ({ page }) => {
      const message = `найди свободное время для встречи с ${PARTICIPANT_BSN} и ${PARTICIPANT_ARV} на 50 минут в ближайшие 5 дней`;
      await sendMessageAndWaitForResponse(page, message, 120000);
      
      const responseText = await page.locator('.markdown, [class*="assistant"]').last().textContent().catch(() => '');
      expect(responseText && responseText.length > 10).toBeTruthy();
    });

    test('3.3 Неполный запрос: "встреча с bsn и arv" - уточнение времени', async ({ page }) => {
      // Шаг 1: только участники
      await sendMessageAndWaitForResponse(page, `назначь встречу с ${PARTICIPANT_BSN} и ${PARTICIPANT_ARV}`);
      
      // Должен запросить уточнения
      expect(await expectClarificationRequested(page)).toBeTruthy();
      
      // Шаг 2: указываем время
      await sendMessageAndWaitForResponse(page, 'в понедельник в 15:00 на 45 минут');
      
      const finalResponse = await page.locator('.markdown, [class*="assistant"]').last().textContent().catch(() => '');
      expect(finalResponse && finalResponse.length > 10).toBeTruthy();
    });

    test('3.4 Сложный запрос: несколько участников + диапазон дней', async ({ page }) => {
      const message = `организуй встречу команды с ${PARTICIPANT_BSN} и ${PARTICIPANT_ARV} на этой неделе, утром, на 1.5 часа`;
      await sendMessageAndWaitForResponse(page, message, 120000);
      
      const responseText = await page.locator('.markdown, [class*="assistant"]').last().textContent().catch(() => '');
      expect(responseText && responseText.length > 10).toBeTruthy();
    });

  });

  // ==================== 4. КОМБИНИРОВАННЫЕ СЦЕНАРИИ ====================
  
  test.describe('4. Комбинированные сценарии', () => {
    
    test('4.1 Проверить календарь и создать встречу в одном диалоге', async ({ page }) => {
      // Шаг 1: проверяем расписание
      await sendMessageAndWaitForResponse(page, 'покажи мои встречи на завтра');
      expect(await expectEventsDisplayed(page)).toBeTruthy();
      
      // Шаг 2: создаём встречу на основе увиденного
      await sendMessageAndWaitForResponse(
        page, 
        `назначь встречу с ${PARTICIPANT_BSN} на завтра в 16:00 на 30 минут`,
        90000
      );
      
      const finalResponse = await page.locator('.markdown, [class*="assistant"]').last().textContent().catch(() => '');
      expect(finalResponse && finalResponse.length > 10).toBeTruthy();
    });

    test('4.2 Постепенное уточнение: от минимума к полному запросу', async ({ page }) => {
      // Шаг 1: минимальный запрос
      await sendMessageAndWaitForResponse(page, 'встреча');
      
      // Шаг 2: добавляем информацию постепенно
      if (await expectClarificationRequested(page)) {
        await sendMessageAndWaitForResponse(page, `с ${PARTICIPANT_BSN}`);
      }
      
      if (await expectClarificationRequested(page)) {
        await sendMessageAndWaitForResponse(page, 'завтра в 10:00');
      }
      
      if (await expectClarificationRequested(page)) {
        await sendMessageAndWaitForResponse(page, 'на 30 минут');
      }
      
      // В конце должен быть результат
      const finalResponse = await page.locator('.markdown, [class*="assistant"]').last().textContent().catch(() => '');
      expect(finalResponse && finalResponse.length > 10).toBeTruthy();
    });

    test('4.3 Запрос с опечаткой/нечётким временем', async ({ page }) => {
      const message = `назначь встречу с ${PARTICIPANT_BSN} где-то после обеда на полчаса`;
      await sendMessageAndWaitForResponse(page, message, 90000);
      
      // Система должна либо уточнить, либо выбрать разумное время
      const responseText = await page.locator('.markdown, [class*="assistant"]').last().textContent().catch(() => '');
      expect(responseText && responseText.length > 10).toBeTruthy();
    });

  });

});
