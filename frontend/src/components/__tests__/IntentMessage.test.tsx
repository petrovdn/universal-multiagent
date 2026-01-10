import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { IntentMessage } from '../IntentMessage'
import { IntentBlock } from '../../store/chatStore'

// Mock IntentBlock factory
const createMockIntentBlock = (overrides: Partial<IntentBlock> = {}): IntentBlock => ({
  id: 'test-intent-1',
  intent: 'Получение событий календаря',
  status: 'started',
  phase: 'planning',
  details: [],
  thinkingText: '',
  isCollapsed: false,
  planningCollapsed: false,
  executingCollapsed: false,
  progressPercent: 0,
  elapsedSec: 0,
  estimatedSec: 10,
  startedAt: Date.now(),
  ...overrides,
})

describe('IntentMessage', () => {
  describe('Проблема 1: Placeholder при пустом thinking', () => {
    it('должен показывать placeholder "Анализирую..." когда фаза planning и thinkingText пустой', () => {
      const block = createMockIntentBlock({
        phase: 'planning',
        thinkingText: '', // Пустой - стриминг ещё не начался
      })

      render(
        <IntentMessage
          block={block}
          onToggleCollapse={vi.fn()}
          onTogglePlanningCollapse={vi.fn()}
          onToggleExecutingCollapse={vi.fn()}
        />
      )

      // Должен показывать placeholder текст
      expect(screen.getByText(/Анализирую/i)).toBeInTheDocument()
    })

    it('должен показывать реальный текст когда thinkingText не пустой', () => {
      const block = createMockIntentBlock({
        phase: 'planning',
        thinkingText: 'Изучаю ваш запрос о событиях календаря...',
      })

      render(
        <IntentMessage
          block={block}
          onToggleCollapse={vi.fn()}
          onTogglePlanningCollapse={vi.fn()}
          onToggleExecutingCollapse={vi.fn()}
        />
      )

      // Должен показывать реальный текст
      expect(screen.getByText(/Изучаю ваш запрос/i)).toBeInTheDocument()
      // НЕ должен показывать placeholder
      expect(screen.queryByText(/^Анализирую\.\.\.$/)).not.toBeInTheDocument()
    })

    it('должен показывать мигающий курсор при пустом thinking в фазе planning', () => {
      const block = createMockIntentBlock({
        phase: 'planning',
        thinkingText: '', // Пустой
      })

      const { container } = render(
        <IntentMessage
          block={block}
          onToggleCollapse={vi.fn()}
          onTogglePlanningCollapse={vi.fn()}
          onToggleExecutingCollapse={vi.fn()}
        />
      )

      // Должен быть элемент курсора
      const cursor = container.querySelector('.intent-thinking-cursor')
      expect(cursor).toBeInTheDocument()
    })
  })
})
