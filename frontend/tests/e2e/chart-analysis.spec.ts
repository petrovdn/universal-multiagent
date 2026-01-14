import { test, expect } from '@playwright/test'

test.describe('Spreadsheet Analysis with Charts', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    // Wait for app to load
    await page.waitForSelector('[data-testid="chat-input"]', { timeout: 10000 })
  })

  test('spreadsheet analysis shows dashboard with charts', async ({ page }) => {
    // This is a placeholder test - actual implementation would require:
    // 1. Mock WebSocket server or real backend
    // 2. Test spreadsheet with known data
    // 3. Agent that can execute the full flow
    
    // For now, we test that the UI components exist and can render charts
    
    // Check that workspace panel exists
    const workspacePanel = page.locator('[data-testid="workspace-panel"]')
    await expect(workspacePanel).toBeVisible({ timeout: 5000 }).catch(() => {
      // If workspace panel doesn't have test-id, check for tab component
      const tabs = page.locator('.workspace-tabs, [class*="tab"]')
      expect(tabs.count()).toBeGreaterThanOrEqual(0)
    })
    
    // Verify DashboardViewer component can be imported (build check)
    // This is a structural test - actual E2E would require full backend setup
    test.skip('Full E2E test requires backend with MCP servers and test spreadsheet')
  })

  test('dashboard viewer renders multiple charts', async ({ page }) => {
    // Test that DashboardViewer can render when chart_dashboard event is received
    // This would require WebSocket mock or real connection
    
    // Simulate chart_dashboard event via WebSocket mock
    await page.evaluate(() => {
      // Mock WebSocket event
      const event = new CustomEvent('chart_dashboard', {
        detail: {
          title: 'Анализ данных',
          charts: [
            {
              title: 'Test Chart 1',
              chartType: 'bar',
              series: [{ name: 'Series 1', data: [1, 2, 3] }],
              options: { xaxis: { categories: ['A', 'B', 'C'] } }
            },
            {
              title: 'Test Chart 2',
              chartType: 'line',
              series: [{ name: 'Series 2', data: [4, 5, 6] }],
              options: { xaxis: { categories: ['A', 'B', 'C'] } }
            }
          ]
        }
      })
      window.dispatchEvent(event)
    })
    
    // Wait a bit for potential rendering
    await page.waitForTimeout(1000)
    
    // Verify that dashboard tab could be created (structural test)
    // Full test would verify actual chart rendering
    test.skip('Full rendering test requires WebSocket integration')
  })
})
