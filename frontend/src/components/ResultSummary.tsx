import React from 'react'
import { CheckCircle, XCircle, Lightbulb, Clock } from 'lucide-react'
import { ResultSummary as ResultSummaryType } from '../store/chatStore'

interface ResultSummaryProps {
  summary: ResultSummaryType
}

export function ResultSummary({ summary }: ResultSummaryProps) {
  const hasContent = 
    summary.completedTasks.length > 0 ||
    summary.failedTasks.length > 0 ||
    summary.alternativesUsed.length > 0 ||
    summary.duration !== undefined ||
    summary.tokensUsed !== undefined

  if (!hasContent) {
    return null
  }

  const formatDuration = (seconds?: number): string => {
    if (!seconds) return ''
    if (seconds < 60) {
      return `${seconds.toFixed(1)} сек`
    }
    const minutes = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${minutes} мин ${secs.toFixed(0)} сек`
  }

  return (
    <div className="result-summary">
      <div className="result-summary-header">
        <CheckCircle size={18} className="result-summary-icon-success" />
        <h3 className="result-summary-title">Задача выполнена!</h3>
      </div>

      <div className="result-summary-content">
        {/* Выполненные задачи */}
        {summary.completedTasks.length > 0 && (
          <div className="result-summary-section">
            <div className="result-summary-section-header">
              <CheckCircle size={14} className="result-summary-section-icon-success" />
              <span className="result-summary-section-title">Выполнено:</span>
            </div>
            <ul className="result-summary-list">
              {summary.completedTasks.map((task, index) => (
                <li key={index} className="result-summary-list-item">
                  {task}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Неудачные задачи */}
        {summary.failedTasks.length > 0 && (
          <div className="result-summary-section">
            <div className="result-summary-section-header">
              <XCircle size={14} className="result-summary-section-icon-error" />
              <span className="result-summary-section-title">Ошибки:</span>
            </div>
            <ul className="result-summary-list">
              {summary.failedTasks.map((task, index) => (
                <li key={index} className="result-summary-list-item result-summary-list-item-error">
                  <strong>{task.task}:</strong> {task.error}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Использованные альтернативы */}
        {summary.alternativesUsed.length > 0 && (
          <div className="result-summary-section">
            <div className="result-summary-section-header">
              <Lightbulb size={14} className="result-summary-section-icon-alternative" />
              <span className="result-summary-section-title">Использованы альтернативы:</span>
            </div>
            <ul className="result-summary-list">
              {summary.alternativesUsed.map((alt, index) => (
                <li key={index} className="result-summary-list-item">
                  {alt}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Метрики */}
        {(summary.duration !== undefined || summary.tokensUsed !== undefined) && (
          <div className="result-summary-metrics">
            {summary.duration !== undefined && (
              <div className="result-summary-metric">
                <Clock size={14} className="result-summary-metric-icon" />
                <span className="result-summary-metric-label">Время:</span>
                <span className="result-summary-metric-value">{formatDuration(summary.duration)}</span>
              </div>
            )}
            {summary.tokensUsed !== undefined && (
              <div className="result-summary-metric">
                <span className="result-summary-metric-label">Токены:</span>
                <span className="result-summary-metric-value">{summary.tokensUsed.toLocaleString()}</span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

