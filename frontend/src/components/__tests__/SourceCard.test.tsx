/**
 * TDD tests for SourceCard component - Phase 1, Step 2.1.
 * 
 * These tests should FAIL initially (Red phase), then pass after implementation (Green phase).
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { SourceCard } from '../SourceCard'
import { SourceCard as SourceCardType } from '../../store/chatStore'

describe('SourceCard', () => {
  it('renders source card with loading state', () => {
    const source: SourceCardType = {
      id: 'src-1',
      name: 'Gmail',
      icon: '📧',
      tool_name: 'list_emails',
      preview: 'Проверяю непрочитанные письма',
      status: 'loading',
      timestamp: new Date().toISOString()
    }
    
    render(<SourceCard source={source} />)
    
    expect(screen.getByText('Gmail')).toBeInTheDocument()
    expect(screen.getByText('Проверяю непрочитанные письма')).toBeInTheDocument()
    expect(screen.getByText('📧')).toBeInTheDocument()
    // Should show loading indicator
    const loadingIndicator = screen.getByText('⏳')
    expect(loadingIndicator).toBeInTheDocument()
  })
  
  it('renders source card with completed state', () => {
    const source: SourceCardType = {
      id: 'src-2',
      name: 'Google Sheets',
      icon: '📊',
      tool_name: 'get_sheet_data',
      preview: 'Получаю данные',
      status: 'completed',
      item_count: 15,
      timestamp: new Date().toISOString()
    }
    
    render(<SourceCard source={source} />)
    
    expect(screen.getByText('Google Sheets')).toBeInTheDocument()
    expect(screen.getByText('Найдено: 15')).toBeInTheDocument()
    // Should show success indicator
    const successIndicator = screen.getByText('✓')
    expect(successIndicator).toBeInTheDocument()
  })
  
  it('renders source card with error state', () => {
    const source: SourceCardType = {
      id: 'src-3',
      name: 'Google Calendar',
      icon: '📅',
      tool_name: 'get_calendar_events',
      preview: 'Проверяю встречи',
      status: 'error',
      error: 'Ошибка доступа',
      timestamp: new Date().toISOString()
    }
    
    render(<SourceCard source={source} />)
    
    expect(screen.getByText('Google Calendar')).toBeInTheDocument()
    expect(screen.getByText('Ошибка')).toBeInTheDocument()
    // Should show error indicator
    const errorIndicator = screen.getByText('✗')
    expect(errorIndicator).toBeInTheDocument()
  })
  
  it('applies correct background color for loading state', () => {
    const source: SourceCardType = {
      id: 'src-1',
      name: 'Gmail',
      icon: '📧',
      tool_name: 'list_emails',
      preview: 'Проверяю письма',
      status: 'loading',
      timestamp: new Date().toISOString()
    }
    
    const { container } = render(<SourceCard source={source} />)
    const card = container.firstChild as HTMLElement
    
    // Loading state should have orange/amber background
    expect(card).toHaveStyle({ backgroundColor: '#fff3e0' })
  })
  
  it('applies correct background color for completed state', () => {
    const source: SourceCardType = {
      id: 'src-2',
      name: 'Gmail',
      icon: '📧',
      tool_name: 'list_emails',
      preview: 'Проверяю письма',
      status: 'completed',
      timestamp: new Date().toISOString()
    }
    
    const { container } = render(<SourceCard source={source} />)
    const card = container.firstChild as HTMLElement
    
    // Completed state should have green background
    expect(card).toHaveStyle({ backgroundColor: '#e8f5e9' })
  })
  
  it('applies correct background color for error state', () => {
    const source: SourceCardType = {
      id: 'src-3',
      name: 'Gmail',
      icon: '📧',
      tool_name: 'list_emails',
      preview: 'Проверяю письма',
      status: 'error',
      timestamp: new Date().toISOString()
    }
    
    const { container } = render(<SourceCard source={source} />)
    const card = container.firstChild as HTMLElement
    
    // Error state should have red background
    expect(card).toHaveStyle({ backgroundColor: '#ffebee' })
  })
  
  it('does not show item count when not provided', () => {
    const source: SourceCardType = {
      id: 'src-2',
      name: 'Google Sheets',
      icon: '📊',
      tool_name: 'get_sheet_data',
      preview: 'Получаю данные',
      status: 'completed',
      timestamp: new Date().toISOString()
    }
    
    render(<SourceCard source={source} />)
    
    expect(screen.queryByText(/Найдено:/)).not.toBeInTheDocument()
  })
})
