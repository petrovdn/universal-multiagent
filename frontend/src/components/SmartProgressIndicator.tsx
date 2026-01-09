import React, { useState, useEffect, useRef } from 'react'
import { Loader2 } from 'lucide-react'

interface SmartProgressIndicatorProps {
  message: string
  elapsedSec: number
  estimatedSec: number
  progressPercent: number
}

export function SmartProgressIndicator({
  message,
  elapsedSec,
  estimatedSec,
  progressPercent
}: SmartProgressIndicatorProps) {
  const [displayMessage, setDisplayMessage] = useState(message)
  const messageRef = useRef<string>(message)
  
  // Обновляем сообщение с анимацией
  useEffect(() => {
    if (message !== messageRef.current) {
      // Анимация смены сообщения
      setDisplayMessage('')
      setTimeout(() => {
        setDisplayMessage(message)
        messageRef.current = message
      }, 150)
    } else {
      setDisplayMessage(message)
    }
  }, [message])
  
  const formatTime = (seconds: number): string => {
    if (seconds < 60) {
      return `${seconds}с`
    }
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}м ${secs}с`
  }
  
  return (
    <div className="smart-progress-indicator">
      <div className="smart-progress-header">
        <div className="smart-progress-icon">
          <Loader2 size={16} className="spinner" />
        </div>
        <div className="smart-progress-content">
          <div className="smart-progress-message">
            {displayMessage || message}
          </div>
          <div className="smart-progress-timer">
            {formatTime(elapsedSec)} / {formatTime(estimatedSec)}
          </div>
        </div>
      </div>
      
      <div className="smart-progress-bar-container">
        <div className="smart-progress-bar">
          <div 
            className="smart-progress-bar-fill"
            style={{ width: `${Math.min(100, progressPercent)}%` }}
          />
        </div>
      </div>
    </div>
  )
}
