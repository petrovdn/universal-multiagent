import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { PlanViewer } from '../viewers/PlanViewer'
import type { WorkspaceTab } from '../../types/workspace'
import type { PlanData } from '../../types/workspace'
import * as api from '../../services/api'

// Mock API functions
vi.mock('../../services/api', () => ({
  approvePlan: vi.fn(),
  rejectPlan: vi.fn(),
  updatePlan: vi.fn(),
}))

// Mock useChatStore
vi.mock('../../store/chatStore', () => ({
  useChatStore: vi.fn(() => ({
    currentSession: 'test-session-id',
  })),
}))

// Mock useWorkspaceStore
vi.mock('../../store/workspaceStore', () => ({
  useWorkspaceStore: vi.fn(() => ({
    updateTab: vi.fn(),
  })),
}))

const createMockPlanTab = (overrides: Partial<WorkspaceTab> = {}): WorkspaceTab => ({
  id: 'plan-tab-1',
  type: 'plan',
  title: 'План выполнения',
  closeable: true,
  timestamp: Date.now(),
  data: {
    planText: '# План выполнения\n\n1. Шаг первый\n2. Шаг второй',
    confirmationId: 'confirmation-123',
    workflowId: 'workflow-123',
    isAwaitingConfirmation: true,
  } as PlanData,
  ...overrides,
})

describe('PlanViewer', () => {
  describe('Рендеринг', () => {
    it('должен отображать markdown план в редактируемом textarea', () => {
      const tab = createMockPlanTab()
      render(<PlanViewer tab={tab} />)

      const textarea = screen.getByRole('textbox') as HTMLTextAreaElement
      expect(textarea).toBeInTheDocument()
      expect(textarea.value).toContain('# План выполнения')
      expect(textarea.value).toContain('1. Шаг первый')
    })

    it('должен показывать заголовок "План выполнения"', () => {
      const tab = createMockPlanTab()
      render(<PlanViewer tab={tab} />)

      expect(screen.getByText('План выполнения')).toBeInTheDocument()
    })

    it('должен показывать кнопки Approve и Reject', () => {
      const tab = createMockPlanTab()
      render(<PlanViewer tab={tab} />)

      expect(screen.getByText('Approve')).toBeInTheDocument()
      expect(screen.getByText('Reject')).toBeInTheDocument()
    })
  })

  describe('Редактирование', () => {
    it('должен обновлять текст при редактировании', () => {
      const tab = createMockPlanTab()
      render(<PlanViewer tab={tab} />)

      const textarea = screen.getByRole('textbox') as HTMLTextAreaElement
      fireEvent.change(textarea, { target: { value: '# Новый план\n\nНовое содержимое' } })

      expect(textarea.value).toBe('# Новый план\n\nНовое содержимое')
    })
  })

  describe('Approve', () => {
    it('должен вызывать approvePlan API при клике на Approve', async () => {
      const mockApprovePlan = vi.mocked(api.approvePlan).mockResolvedValue({})
      const tab = createMockPlanTab()

      render(<PlanViewer tab={tab} />)

      const approveButton = screen.getByText('Approve')
      fireEvent.click(approveButton)

      await waitFor(() => {
        expect(mockApprovePlan).toHaveBeenCalledWith('test-session-id', 'confirmation-123')
      })
    })
  })

  describe('Reject', () => {
    it('должен вызывать rejectPlan API при клике на Reject', async () => {
      const mockRejectPlan = vi.mocked(api.rejectPlan).mockResolvedValue({})
      const tab = createMockPlanTab()

      render(<PlanViewer tab={tab} />)

      const rejectButton = screen.getByText('Reject')
      fireEvent.click(rejectButton)

      await waitFor(() => {
        expect(mockRejectPlan).toHaveBeenCalledWith('test-session-id', 'confirmation-123')
      })
    })
  })
})
