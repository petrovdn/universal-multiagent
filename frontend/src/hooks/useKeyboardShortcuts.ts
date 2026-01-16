import { useEffect, useRef } from 'react'
import { useSettingsStore } from '../store/settingsStore'

interface KeyboardShortcutsOptions {
  onFocusInput?: () => void
  onCloseMenus?: () => void
  onOpenHelp?: () => void
  onOpenSettings?: () => void
  onSwitchMode?: (mode: 'query' | 'plan' | 'agent') => void
}

export function useKeyboardShortcuts(options: KeyboardShortcutsOptions) {
  const { setExecutionMode } = useSettingsStore()
  const optionsRef = useRef(options)

  // Обновляем ref при изменении options
  useEffect(() => {
    optionsRef.current = options
  }, [options])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Проверяем, не находится ли фокус в поле ввода или другом интерактивном элементе
      const target = e.target as HTMLElement
      const isInputFocused = 
        target.tagName === 'INPUT' || 
        target.tagName === 'TEXTAREA' || 
        target.isContentEditable ||
        target.closest('input') ||
        target.closest('textarea')

      // Ctrl/Cmd + K - Фокус на поле ввода
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault()
        if (optionsRef.current.onFocusInput) {
          optionsRef.current.onFocusInput()
        }
        return
      }

      // Esc - Закрыть открытые меню
      if (e.key === 'Escape') {
        if (optionsRef.current.onCloseMenus) {
          optionsRef.current.onCloseMenus()
        }
        return
      }

      // Ctrl/Cmd + / - Открыть справку
      if ((e.ctrlKey || e.metaKey) && e.key === '/') {
        e.preventDefault()
        if (optionsRef.current.onOpenHelp) {
          optionsRef.current.onOpenHelp()
        }
        return
      }

      // Ctrl/Cmd + , - Открыть настройки
      if ((e.ctrlKey || e.metaKey) && e.key === ',') {
        e.preventDefault()
        if (optionsRef.current.onOpenSettings) {
          optionsRef.current.onOpenSettings()
        }
        return
      }

      // Ctrl/Cmd + H - Открыть меню помощи
      if ((e.ctrlKey || e.metaKey) && e.key === 'h') {
        e.preventDefault()
        if (optionsRef.current.onOpenHelp) {
          optionsRef.current.onOpenHelp()
        }
        return
      }

      // Ctrl/Cmd + 1/2/3 - Переключить режимы работы
      // Работает только если фокус не в поле ввода
      if (!isInputFocused) {
        if ((e.ctrlKey || e.metaKey) && e.key === '1') {
          e.preventDefault()
          if (optionsRef.current.onSwitchMode) {
            optionsRef.current.onSwitchMode('query')
          } else {
            setExecutionMode('query')
          }
          return
        }
        if ((e.ctrlKey || e.metaKey) && e.key === '2') {
          e.preventDefault()
          if (optionsRef.current.onSwitchMode) {
            optionsRef.current.onSwitchMode('agent')
          } else {
            setExecutionMode('agent')
          }
          return
        }
        if ((e.ctrlKey || e.metaKey) && e.key === '3') {
          e.preventDefault()
          if (optionsRef.current.onSwitchMode) {
            optionsRef.current.onSwitchMode('plan')
          } else {
            setExecutionMode('plan')
          }
          return
        }
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [setExecutionMode])
}
