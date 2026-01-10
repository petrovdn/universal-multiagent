import React, { useState, useEffect, useRef } from 'react'

interface PlanningBlockProps {
  content: string
  isStreaming: boolean
  estimatedSeconds?: number // Оценочное время в секундах
  onCollapseChange?: (collapsed: boolean) => void
  initialCollapsed?: boolean // Начальное состояние свёрнутости
  className?: string
}

export function PlanningBlock({ 
  content, 
  isStreaming, 
  estimatedSeconds = 10,
  onCollapseChange,
  initialCollapsed = false,
  className = '' 
}: PlanningBlockProps) {
  const [isCollapsed, setIsCollapsed] = useState(initialCollapsed)
  const [elapsedTime, setElapsedTime] = useState(0)
  const contentRef = useRef<HTMLDivElement>(null)
  const startTimeRef = useRef<number>(Date.now())
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const onCollapseChangeRef = useRef(onCollapseChange)
  const hasInitializedRef = useRef(false)

  // Обновляем ref при изменении колбэка (без зависимости от него в других useEffect)
  useEffect(() => {
    onCollapseChangeRef.current = onCollapseChange
  }, [onCollapseChange])

  // Инициализация и синхронизация collapsed состояния
  const prevInitialCollapsedRef = useRef(initialCollapsed)
  const isCollapsedRef = useRef(isCollapsed)
  
  // Обновляем ref при изменении состояния
  useEffect(() => {
    isCollapsedRef.current = isCollapsed
  }, [isCollapsed])
  
  useEffect(() => {
    // Инициализируем только один раз при монтировании
    if (!hasInitializedRef.current) {
      setIsCollapsed(initialCollapsed)
      prevInitialCollapsedRef.current = initialCollapsed
      isCollapsedRef.current = initialCollapsed
      hasInitializedRef.current = true
    } else {
      // Если initialCollapsed изменился извне (не от нашего setState), синхронизируем
      // Но только если текущее состояние отличается
      if (prevInitialCollapsedRef.current !== initialCollapsed && initialCollapsed !== isCollapsedRef.current) {
        setIsCollapsed(initialCollapsed)
        prevInitialCollapsedRef.current = initialCollapsed
        isCollapsedRef.current = initialCollapsed
      }
    }
  }, [initialCollapsed]) // Убираем isCollapsed из зависимостей - используем ref

  // Сброс таймера при начале нового стриминга (только при переходе false -> true)
  // И автосворачивание после окончания стриминга
  const prevStreamingRef = useRef(isStreaming)
  useEffect(() => {
    if (isStreaming && !prevStreamingRef.current) {
      // Только при начале нового стриминга
      startTimeRef.current = Date.now()
      setElapsedTime(0)
      // Разворачиваем при начале стриминга (НЕ вызываем onCollapseChange здесь!)
      setIsCollapsed(false)
    } else if (!isStreaming && prevStreamingRef.current) {
      // Когда стриминг закончился - сворачиваем
      setIsCollapsed(true)
    }
    prevStreamingRef.current = isStreaming
  }, [isStreaming]) // Только isStreaming в зависимостях

  // Обновление обратного отсчёта
  useEffect(() => {
    if (isStreaming) {
      intervalRef.current = setInterval(() => {
        const elapsed = (Date.now() - startTimeRef.current) / 1000
        setElapsedTime(elapsed)
      }, 100)

      return () => {
        if (intervalRef.current) {
          clearInterval(intervalRef.current)
          intervalRef.current = null
        }
      }
    } else {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }
  }, [isStreaming])

  // Auto-scroll при стриминге
  useEffect(() => {
    if (contentRef.current && isStreaming && !isCollapsed) {
      contentRef.current.scrollTop = contentRef.current.scrollHeight
    }
  }, [content, isStreaming, isCollapsed])

  const remainingTime = Math.max(0, estimatedSeconds - elapsedTime)
  const displayTime = Math.ceil(remainingTime)

  // Убираем пустую первую строку из контента (удаляем начальные переносы строк)
  const cleanContent = content.trimStart().replace(/^\n+/, '')

  const toggleCollapse = () => {
    const newCollapsed = !isCollapsedRef.current
    setIsCollapsed(newCollapsed)
    isCollapsedRef.current = newCollapsed
    prevInitialCollapsedRef.current = newCollapsed // Обновляем ref чтобы избежать лишних синхронизаций
    // Вызываем колбэк синхронно, но через ref, чтобы избежать зависимости
    onCollapseChangeRef.current?.(newCollapsed)
  }

  // Если свёрнуто, показываем только "План" со стрелкой вправо
  if (isCollapsed && !isStreaming) {
    return (
      <div 
        className={`planning-block-collapsed ${className}`}
        onClick={toggleCollapse}
        style={{ cursor: 'pointer' }}
      >
        <span className="planning-collapsed-text" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <span style={{ fontSize: '10px' }}>▶</span>
          <span>План</span>
        </span>
      </div>
    )
  }

  // Если не стримится и не свёрнуто - показываем развёрнутый вид с "План" сверху
  if (!isStreaming && !isCollapsed) {
    return (
      <div className={`planning-block ${className}`}>
        <div 
          className="planning-header"
          onClick={toggleCollapse}
          style={{ cursor: 'pointer' }}
        >
          <span style={{ fontSize: '10px' }}>▼</span>
          <span className="planning-title">
            План
          </span>
        </div>
        <div 
          ref={contentRef}
          className="planning-content"
        >
          {cleanContent}
        </div>
      </div>
    )
  }

  // Во время стриминга показываем "Планирую (Nс)..." со стрелкой вниз
  return (
    <div className={`planning-block ${isStreaming ? 'planning-block-streaming' : ''} ${className}`}>
      <div className="planning-header">
        <span style={{ fontSize: '10px' }}>▼</span>
        <span className="planning-title">
          Планирую ({displayTime}с)...
        </span>
      </div>
      {!isCollapsed && (
        <div 
          ref={contentRef}
          className="planning-content"
        >
          {cleanContent}
        </div>
      )}
    </div>
  )
}
