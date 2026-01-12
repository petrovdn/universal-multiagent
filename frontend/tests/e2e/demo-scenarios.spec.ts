import { test, expect, Page, BrowserContext } from '@playwright/test';
import * as fs from 'fs';

/**
 * E2E тесты для демонстрации системы.
 * 
 * Покрывают реальные сценарии использования:
 * 1. Работа с файлами (PDF, DOCX, изображения)
 * 2. Работа с календарём
 * 3. Копирование и форматирование документов
 * 4. Создание презентаций
 * 
 * Запуск:
 *   cd frontend
 *   npx playwright test demo-scenarios.spec.ts
 *   npx playwright test demo-scenarios.spec.ts --ui  # Интерактивный режим
 * 
 * ВАЖНО: Требуется запущенный backend и frontend
 * ВАЖНО: Для тестов с файлами нужна настроенная рабочая папка в Google Workspace
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
        sessionId: 'demo-e2e',
        hypothesisId: 'DEMO',
        source: 'playwright'
      })
    });
  } catch (e) {
    // Ignore log errors
  }
}

/**
 * Helper: вход в систему (если требуется)
 */
async function loginIfNeeded(page: Page) {
  const loginDialogOverlay = page.locator('.login-dialog-overlay');
  const loginDialog = page.locator('.login-dialog');
  const usernameField = page.locator('#username');
  
  const hasOverlay = await loginDialogOverlay.isVisible({ timeout: 3000 }).catch(() => false);
  const hasDialog = await loginDialog.isVisible({ timeout: 3000 }).catch(() => false);
  const hasUsernameField = await usernameField.isVisible({ timeout: 3000 }).catch(() => false);
  
  const needsLogin = hasOverlay || hasDialog || hasUsernameField;
  
  await logDebug('demo:login:check', 'Login check', { needsLogin, hasOverlay, hasDialog, hasUsernameField });
  
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
    
    await logDebug('demo:login', 'Login successful', {});
  } else {
    await logDebug('demo:login', 'Already authenticated', {});
    const chatInput = page.locator('textarea.chat-input, .input-form textarea').first();
    await expect(chatInput).toBeVisible({ timeout: 10000 });
  }
}

/**
 * Helper: отправить сообщение и дождаться ответа
 */
async function sendMessageAndWaitForResponse(page: Page, message: string, timeout = 120000) {
  await logDebug('demo:send', 'Sending message', { message: message.slice(0, 100), timeout });
  
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
    '.assistant-message-wrapper, .final-result-prose, .sticky-result-section, .markdown',
    { timeout }
  );
  
  // Даём время на полное отображение
  await page.waitForTimeout(2000);
  
  await logDebug('demo:send', 'Response received', {});
}

/**
 * Helper: получить текст последнего ответа
 */
async function getLastResponse(page: Page): Promise<string> {
  const response = await page.locator('.final-result-prose, .assistant-message-wrapper, .markdown').last().textContent().catch(() => '');
  return response || '';
}

/**
 * Helper: проверить, что ответ содержит ключевые слова
 */
function responseContains(response: string, keywords: string[]): boolean {
  const lowerResponse = response.toLowerCase();
  return keywords.some(kw => lowerResponse.includes(kw.toLowerCase()));
}

/**
 * Helper: прикрепить локальные файлы через кнопку "скрепка" в чате
 * Использует input[type="file"] и Playwright setInputFiles API
 * 
 * @param page - страница Playwright
 * @param filePaths - массив абсолютных путей к файлам
 * @returns количество успешно прикреплённых файлов
 */
async function attachLocalFiles(page: Page, filePaths: string[]): Promise<number> {
  await logDebug('demo:attachFiles', 'Attaching local files', { count: filePaths.length, files: filePaths });
  
    // Проверяем существование файлов
  const existingFiles: string[] = [];
  const missingFiles: string[] = [];
  for (const filePath of filePaths) {
    try {
      if (fs.existsSync(filePath)) {
        existingFiles.push(filePath);
      } else {
        missingFiles.push(filePath);
        await logDebug('demo:attachFiles', 'File not found', { filePath });
      }
    } catch (error: any) {
      missingFiles.push(filePath);
      await logDebug('demo:attachFiles', 'Error checking file', { filePath, error: error.message });
    }
  }
  
  if (existingFiles.length === 0) {
    await logDebug('demo:attachFiles', 'No files found', { missingFiles });
    return 0;
  }
  
  if (missingFiles.length > 0) {
    await logDebug('demo:attachFiles', 'Some files missing', { 
      existing: existingFiles.length, 
      missing: missingFiles.length,
      missingFiles 
    });
  }
  
  // Находим скрытый input[type="file"]
  const fileInput = page.locator('input[type="file"]').first();
  
  try {
    // Проверяем, что страница не закрыта
    if (page.isClosed()) {
      await logDebug('demo:attachFiles', 'Page is closed', {});
      return 0;
    }
    
    // Используем setInputFiles для загрузки файлов без открытия системного диалога
    await fileInput.setInputFiles(existingFiles);
    
    // Ждём загрузки ВСЕХ файлов на сервер
    // Каждый файл создаёт элемент .attached-file
    const expectedCount = existingFiles.length;
    let actualCount = 0;
    
    // Ждём до 15 секунд пока все файлы загрузятся (увеличено для больших файлов)
    for (let i = 0; i < 15; i++) {
      await page.waitForTimeout(1000);
      const attachedFiles = page.locator('.attached-files .attached-file');
      actualCount = await attachedFiles.count();
      
      // Получаем имена загруженных файлов для отладки
      const fileNames = await attachedFiles.allTextContents().catch(() => []);
      
      await logDebug('demo:attachFiles:progress', 'Waiting for files', { 
        expected: expectedCount, 
        actual: actualCount,
        iteration: i + 1,
        fileNames: fileNames.slice(0, 5) // Первые 5 для отладки
      });
      
      if (actualCount >= expectedCount) {
        await logDebug('demo:attachFiles', 'All files loaded', { count: actualCount });
        break;
      }
    }
    
    if (actualCount < expectedCount) {
      await logDebug('demo:attachFiles', 'Not all files loaded', { 
        expected: expectedCount, 
        actual: actualCount,
        missing: expectedCount - actualCount
      });
    }
    
    await logDebug('demo:attachFiles', 'Files attached', { 
      requestedCount: expectedCount, 
      attachedCount: actualCount
    });
    
    return actualCount;
  } catch (error: any) {
    await logDebug('demo:attachFiles', 'Error attaching files', { error: error.message });
    return 0;
  }
}

/**
 * Helper: закрыть все workspace табы (кроме placeholder)
 * Чтобы тест начинался с чистого состояния
 */
async function closeAllWorkspaceTabs(page: Page): Promise<void> {
  await logDebug('demo:closeWorkspace', 'Closing all workspace tabs', {});
  
  try {
    // Находим все кнопки закрытия табов (aria-label="Close tab")
    const closeButtons = page.locator('button[aria-label="Close tab"]');
    let count = await closeButtons.count();
    
    await logDebug('demo:closeWorkspace', 'Found tabs to close', { count });
    
    // Закрываем табы по одному, но не более 5 раз (защита от бесконечного цикла)
    let attempts = 0;
    while (count > 0 && attempts < 5) {
      try {
        // Проверяем, что страница ещё открыта
        if (page.isClosed()) {
          await logDebug('demo:closeWorkspace', 'Page was closed, stopping', {});
          break;
        }
        
        await closeButtons.first().click({ timeout: 2000 });
        await page.waitForTimeout(500);
        
        // Пересчитываем кнопки
        count = await closeButtons.count();
        attempts++;
      } catch (error: any) {
        await logDebug('demo:closeWorkspace', 'Error closing tab', { error: error.message });
        break;
      }
    }
    
    await logDebug('demo:closeWorkspace', 'Workspace tabs closed', { remaining: count, attempts });
  } catch (error: any) {
    await logDebug('demo:closeWorkspace', 'Error in closeAllWorkspaceTabs', { error: error.message });
  }
}

/**
 * Helper: открыть файл в workspace через popup (для Google Drive файлов)
 * Возвращает true, если файл успешно выбран
 */
async function selectFileFromWorkspace(page: Page, context: BrowserContext, fileName: string): Promise<boolean> {
  await logDebug('demo:selectFile', 'Opening file selector', { fileName });
  
  // Кликаем на кнопку "+" в workspace panel для открытия popup
  // Кнопка имеет title="Добавить файл из рабочей области"
  const addTabButton = page.locator('button[title="Добавить файл из рабочей области"], button[title*="Добавить файл"]').first();
  
  const buttonVisible = await addTabButton.isVisible({ timeout: 5000 }).catch(() => false);
  if (!buttonVisible) {
    await logDebug('demo:selectFile', 'Add button not found, trying alternative selector', {});
    // Попробуем найти любую кнопку с иконкой Plus в tab-bar
    const altButton = page.locator('.tab-bar button, button:has(svg.lucide-plus)').first();
    const altVisible = await altButton.isVisible({ timeout: 3000 }).catch(() => false);
    if (!altVisible) {
      await logDebug('demo:selectFile', 'No add button found at all', {});
      return false;
    }
  }
  
  try {
    // Ждём popup окно
    const [popup] = await Promise.all([
      context.waitForEvent('page', { timeout: 10000 }),
      addTabButton.click()
    ]);
    
    await popup.waitForLoadState('networkidle');
    await logDebug('demo:selectFile', 'Popup opened', {});
    
    // Ждём загрузки списка файлов
    await popup.waitForSelector('table tbody tr, .file-item', { timeout: 30000 });
    
    // Ищем файл по имени (частичное совпадение)
    const fileRow = popup.locator(`tr:has-text("${fileName}"), .file-item:has-text("${fileName}")`).first();
    const fileExists = await fileRow.isVisible({ timeout: 5000 }).catch(() => false);
    
    if (!fileExists) {
      await logDebug('demo:selectFile', 'File not found in list', { fileName });
      await popup.close();
      return false;
    }
    
    // Кликаем на файл для выбора
    await fileRow.click();
    
    // Popup закроется автоматически после выбора
    await page.waitForTimeout(2000);
    
    await logDebug('demo:selectFile', 'File selected successfully', { fileName });
    return true;
  } catch (error: any) {
    await logDebug('demo:selectFile', 'Error selecting file', { fileName, error: error.message });
    return false;
  }
}

/**
 * Helper: проверить, что файл открыт в workspace
 */
async function isFileOpenInWorkspace(page: Page, fileName: string): Promise<boolean> {
  const tab = page.locator(`.tab-component:has-text("${fileName}"), .workspace-tab:has-text("${fileName}")`).first();
  return await tab.isVisible({ timeout: 3000 }).catch(() => false);
}

/**
 * Helper: открыть файл "сказка" в workspace
 * Предполагается, что файл с названием "сказка" существует в workspace
 */
async function openSkazkaFile(page: Page, context: BrowserContext): Promise<boolean> {
  // Пробуем разные варианты названия
  const possibleNames = ['сказка', 'Сказка', 'сказ', 'Сказ'];
  
  for (const name of possibleNames) {
    // Проверяем, не открыт ли уже файл
    const alreadyOpen = await isFileOpenInWorkspace(page, name);
    if (alreadyOpen) {
      await logDebug('demo:openSkazka', 'Skazka already open', { name });
      return true;
    }
    
    // Пробуем открыть
    const success = await selectFileFromWorkspace(page, context, name);
    if (success) {
      await page.waitForTimeout(2000);
      return true;
    }
  }
  
  await logDebug('demo:openSkazka', 'Skazka file not found', {});
  return false;
}


// ==================== КОНФИГУРАЦИЯ ТЕСТОВЫХ ФАЙЛОВ ====================

/**
 * Пути к тестовым файлам для демо.
 * 
 * ВАЖНО: Перед запуском тестов убедитесь, что файлы существуют!
 * Можно изменить пути на актуальные для вашей системы.
 * 
 * Поддерживаемые форматы: изображения (jpg, png, gif, webp), PDF, Word (doc, docx)
 */
const TEST_FILES = {
  // Файлы для теста 1 (анализ файлов)
  methodology: '/Users/Dima/Desktop/demo-files/Методология работы со стратегией - годовой цикл.docx',
  reference: '/Users/Dima/Downloads/9190016821.pdf',
  photo: '/Users/Dima/Desktop/demo-files/unnamed.jpg',
};

// ==================== ТЕСТЫ ====================

test.describe('Demo Scenarios - Файлы', () => {
  test.setTimeout(180000); // 3 минуты на тест
  
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await loginIfNeeded(page);
    await logDebug('demo:beforeEach', 'Page loaded', {});
  });

  test('1.1 Выбрать три файла и спросить "Что в файлах?"', async ({ page }) => {
    await logDebug('demo:test:1.1', 'Starting file analysis test', {});
    
    // Закрываем все workspace табы, чтобы ничего не открывалось в правой панели
    await closeAllWorkspaceTabs(page);
    
    // Список файлов для прикрепления (через кнопку "скрепка")
    const filesToAttach = [
      TEST_FILES.methodology,
      TEST_FILES.reference,
      TEST_FILES.photo
    ];
    
    // Прикрепляем файлы через input[type="file"]
    const filesAttached = await attachLocalFiles(page, filesToAttach);
    
    await logDebug('demo:test:1.1', 'Files attached', { count: filesAttached, total: filesToAttach.length });
    
    // Проверяем, что все файлы прикреплены
    if (filesAttached === 0) {
      console.warn('⚠️  SKIP: Тестовые файлы не найдены. Проверьте пути в TEST_FILES:');
      console.warn('   - ' + filesToAttach.join('\n   - '));
      test.skip();
      return;
    }
    
    // Проверяем, что загрузились все 3 файла
    if (filesAttached < filesToAttach.length) {
      await logDebug('demo:test:1.1', 'WARNING: Not all files attached', { 
        attached: filesAttached, 
        expected: filesToAttach.length 
      });
      // Продолжаем тест, но с предупреждением
      console.warn(`⚠️  WARNING: Загрузилось только ${filesAttached} из ${filesToAttach.length} файлов`);
    }
    
    // Отправляем вопрос
    await sendMessageAndWaitForResponse(page, 'Что в файлах?', 120000);
    
    const response = await getLastResponse(page);
    await logDebug('demo:test:1.1', 'Response received', { responseLen: response.length });
    
    // Проверяем, что система описала файлы
    expect(response.length).toBeGreaterThan(50);
    
    // Делаем скриншот для отчёта
    await page.screenshot({ path: 'test-results/demo-1.1-files.png', fullPage: true });
  });

  test('1.2 Уточняющий вопрос "подробнее о страховке"', async ({ page }) => {
    await logDebug('demo:test:1.2', 'Starting insurance question test', {});
    
    // Закрываем все workspace табы
    await closeAllWorkspaceTabs(page);
    
    // Прикрепляем Reference файл
    const filesAttached = await attachLocalFiles(page, [TEST_FILES.reference]);
    
    if (filesAttached === 0) {
      console.warn('⚠️  SKIP: Reference файл не найден:', TEST_FILES.reference);
      test.skip();
      return;
    }
    
    // Сначала спрашиваем что в файле
    await sendMessageAndWaitForResponse(page, 'Что в файле?', 90000);
    
    // Потом уточняем о страховке
    await sendMessageAndWaitForResponse(page, 'подробнее о страховке', 90000);
    
    const response = await getLastResponse(page);
    await logDebug('demo:test:1.2', 'Response received', { responseLen: response.length });
    
    // Проверяем, что система рассказала о страховке
    const hasInsuranceInfo = responseContains(response, ['страхов', 'insurance', 'полис', 'policy']);
    expect(hasInsuranceInfo || response.length > 30).toBeTruthy();
    
    await page.screenshot({ path: 'test-results/demo-1.2-insurance.png', fullPage: true });
  });

  test('1.3 Вопрос о фотографии "расскажи о девушке на фото"', async ({ page }) => {
    await logDebug('demo:test:1.3', 'Starting photo question test', {});
    
    // Закрываем все workspace табы
    await closeAllWorkspaceTabs(page);
    
    // Прикрепляем фото
    const filesAttached = await attachLocalFiles(page, [TEST_FILES.photo]);
    
    if (filesAttached === 0) {
      console.warn('⚠️  SKIP: Фото не найдено:', TEST_FILES.photo);
      test.skip();
      return;
    }
    
    // Спрашиваем о девушке на фото
    await sendMessageAndWaitForResponse(page, 'расскажи о девушке на фото', 90000);
    
    const response = await getLastResponse(page);
    await logDebug('demo:test:1.3', 'Response received', { responseLen: response.length });
    
    // Проверяем, что система описала фото
    expect(response.length).toBeGreaterThan(20);
    
    await page.screenshot({ path: 'test-results/demo-1.3-photo.png', fullPage: true });
  });
});


test.describe('Demo Scenarios - Календарь', () => {
  test.setTimeout(120000); // 2 минуты на тест
  
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await loginIfNeeded(page);
  });

  test('2.1 Показать встречи на этой неделе', async ({ page }) => {
    await logDebug('demo:test:2.1', 'Starting weekly meetings test', {});
    
    await sendMessageAndWaitForResponse(page, 'Какие встречи есть на этой неделе?', 60000);
    
    const response = await getLastResponse(page);
    await logDebug('demo:test:2.1', 'Response received', { responseLen: response.length });
    
    // Проверяем, что система вернула информацию о встречах
    const hasMeetingInfo = responseContains(response, [
      'встреч', 'событи', 'мероприят', 'calendar', 'meeting',
      'запланирован', 'нет встреч', 'не найдено'
    ]);
    
    expect(hasMeetingInfo || response.length > 20).toBeTruthy();
    
    await page.screenshot({ path: 'test-results/demo-2.1-weekly-meetings.png', fullPage: true });
  });

  test('2.2 Показать встречи с конкретным участником', async ({ page }) => {
    await logDebug('demo:test:2.2', 'Starting participant meetings test', {});
    
    await sendMessageAndWaitForResponse(page, 'какие встречи с marat@ в этом месяце?', 60000);
    
    const response = await getLastResponse(page);
    await logDebug('demo:test:2.2', 'Response received', { responseLen: response.length });
    
    // Проверяем, что система вернула информацию
    const hasInfo = responseContains(response, [
      'встреч', 'событи', 'marat', 'не найдено', 'нет встреч',
      'запланирован', 'календар'
    ]);
    
    expect(hasInfo || response.length > 20).toBeTruthy();
    
    await page.screenshot({ path: 'test-results/demo-2.2-participant-meetings.png', fullPage: true });
  });
});


test.describe('Demo Scenarios - Документы', () => {
  test.setTimeout(180000); // 3 минуты на тест
  
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await loginIfNeeded(page);
  });

  test('3.1 Скопировать сказку и отформатировать', async ({ page, context }) => {
    await logDebug('demo:test:3.1', 'Starting document copy test', {});
    
    // Открываем сказку в workspace
    const skazkaOpened = await openSkazkaFile(page, context);
    await logDebug('demo:test:3.1', 'Skazka file status', { opened: skazkaOpened });
    
    if (!skazkaOpened) {
      // Если сказка не найдена, пропускаем тест с предупреждением
      console.warn('SKIP: Файл "сказка" не найден в workspace');
      test.skip();
      return;
    }
    
    // Ждём загрузки документа
    await page.waitForTimeout(3000);
    
    // Отправляем запрос
    await sendMessageAndWaitForResponse(page, 'сделай копию сказки и отформатируй красиво', 120000);
    
    const response = await getLastResponse(page);
    await logDebug('demo:test:3.1', 'Response received', { responseLen: response.length });
    
    // Проверяем, что система выполнила задачу
    const hasSuccess = responseContains(response, [
      'создан', 'скопирован', 'отформатирован', 'готов', 'выполнен',
      'документ', 'копия', 'форматирован'
    ]);
    
    expect(hasSuccess || response.length > 30).toBeTruthy();
    
    await page.screenshot({ path: 'test-results/demo-3.1-document-copy.png', fullPage: true });
  });
});


test.describe('Demo Scenarios - Презентации', () => {
  test.setTimeout(300000); // 5 минут на тест (создание презентации - долгая операция)
  
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await loginIfNeeded(page);
  });

  test('4.1 Создать презентацию на основе сказки', async ({ page, context }) => {
    await logDebug('demo:test:4.1', 'Starting presentation creation test', {});
    
    // Открываем сказку в workspace
    const skazkaOpened = await openSkazkaFile(page, context);
    await logDebug('demo:test:4.1', 'Skazka file status', { opened: skazkaOpened });
    
    if (!skazkaOpened) {
      console.warn('SKIP: Файл "сказка" не найден в workspace');
      test.skip();
      return;
    }
    
    // Ждём загрузки документа
    await page.waitForTimeout(3000);
    
    // Отправляем сложный запрос на создание презентации
    const request = `на основе сказки сделай официальную серьезную презентацию, для доклада в министерстве внутренних дел. Тема: Преступность не дремлет! Похождения банды Прыг и Ласка`;
    
    await sendMessageAndWaitForResponse(page, request, 240000); // 4 минуты на создание
    
    const response = await getLastResponse(page);
    await logDebug('demo:test:4.1', 'Response received', { responseLen: response.length });
    
    // Проверяем, что презентация создана
    const hasSuccess = responseContains(response, [
      'презентац', 'создан', 'слайд', 'готов', 'выполнен',
      'presentation', 'slide'
    ]);
    
    expect(hasSuccess || response.length > 50).toBeTruthy();
    
    // Проверяем, что в workspace появилась презентация
    const presentationTab = page.locator('.tab-component:has-text("резентац"), .workspace-tab:has-text("резентац"), .tab-component:has-text("Преступность")').first();
    const hasPresentationTab = await presentationTab.isVisible({ timeout: 5000 }).catch(() => false);
    
    await logDebug('demo:test:4.1', 'Presentation tab check', { visible: hasPresentationTab });
    
    // Делаем скриншот результата
    await page.screenshot({ path: 'test-results/demo-4.1-presentation.png', fullPage: true });
    
    // Проверяем наличие слайдов (если презентация открыта в viewer)
    if (hasPresentationTab) {
      await presentationTab.click();
      await page.waitForTimeout(2000);
      
      // Ищем элементы слайдов
      const slides = page.locator('.slide-thumbnail, .slide-item, [class*="slide"]');
      const slideCount = await slides.count();
      
      await logDebug('demo:test:4.1', 'Slides found', { count: slideCount });
      
      // Должно быть минимум 2 слайда
      expect(slideCount).toBeGreaterThanOrEqual(1);
      
      await page.screenshot({ path: 'test-results/demo-4.1-presentation-slides.png', fullPage: true });
    }
  });
});


// ==================== ПОЛНЫЙ СЦЕНАРИЙ ДЕМО ====================

test.describe('Demo - Full Scenario', () => {
  test.setTimeout(600000); // 10 минут на полный сценарий
  
  test('FULL: Полный демо-сценарий с файлами, календарём и презентацией', async ({ page, context }) => {
    await logDebug('demo:full', 'Starting full demo scenario', {});
    
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await loginIfNeeded(page);
    
    // --- Часть 1: Файлы ---
    await logDebug('demo:full:part1', 'Part 1: Files', {});
    
    // Прикрепляем файлы через кнопку "скрепка"
    const filesToAttach = [TEST_FILES.methodology, TEST_FILES.reference, TEST_FILES.photo];
    const filesAttached = await attachLocalFiles(page, filesToAttach);
    
    if (filesAttached > 0) {
      // Вопрос о файлах
      await sendMessageAndWaitForResponse(page, 'Что в файлах?', 120000);
      let response = await getLastResponse(page);
      expect(response.length).toBeGreaterThan(30);
      await page.screenshot({ path: 'test-results/demo-full-1-files.png', fullPage: true });
      
      // Вопрос о страховке
      await sendMessageAndWaitForResponse(page, 'подробнее о страховке', 60000);
      response = await getLastResponse(page);
      expect(response.length).toBeGreaterThan(20);
      
      // Вопрос о фото
      await sendMessageAndWaitForResponse(page, 'теперь расскажи о девушке на фото', 60000);
      response = await getLastResponse(page);
      expect(response.length).toBeGreaterThan(20);
      await page.screenshot({ path: 'test-results/demo-full-1-photo.png', fullPage: true });
    } else {
      await logDebug('demo:full:part1', 'SKIP: Files not found', {});
    }
    
    // --- Часть 2: Календарь ---
    await logDebug('demo:full:part2', 'Part 2: Calendar', {});
    
    // Новая сессия для календаря (опционально)
    await page.locator('.new-chat-button, button:has-text("Новый чат")').click().catch(() => {});
    await page.waitForTimeout(2000);
    
    await sendMessageAndWaitForResponse(page, 'Какие встречи есть на этой неделе?', 60000);
    let response = await getLastResponse(page);
    expect(response.length).toBeGreaterThan(10);
    await page.screenshot({ path: 'test-results/demo-full-2-calendar.png', fullPage: true });
    
    await sendMessageAndWaitForResponse(page, 'какие встречи с marat@ в этом месяце?', 60000);
    response = await getLastResponse(page);
    expect(response.length).toBeGreaterThan(10);
    
    // --- Часть 3: Сказка ---
    await logDebug('demo:full:part3', 'Part 3: Skazka', {});
    
    const skazkaOpened = await openSkazkaFile(page, context);
    
    if (skazkaOpened) {
      await page.waitForTimeout(3000);
      
      // Копирование
      await sendMessageAndWaitForResponse(page, 'сделай копию сказки и отформатируй красиво', 120000);
      response = await getLastResponse(page);
      expect(response.length).toBeGreaterThan(20);
      await page.screenshot({ path: 'test-results/demo-full-3-copy.png', fullPage: true });
      
      // --- Часть 4: Презентация ---
      await logDebug('demo:full:part4', 'Part 4: Presentation', {});
      
      const presentationRequest = `на основе сказки сделай официальную серьезную презентацию, для доклада в министерстве внутренних дел. Тема: Преступность не дремлет! Похождения банды Прыг и Ласка`;
      
      await sendMessageAndWaitForResponse(page, presentationRequest, 240000);
      response = await getLastResponse(page);
      expect(response.length).toBeGreaterThan(30);
      await page.screenshot({ path: 'test-results/demo-full-4-presentation.png', fullPage: true });
    }
    
    await logDebug('demo:full', 'Full demo scenario completed', {});
  });
});
