import React from 'react'
import { useWorkspaceStore } from '../store/workspaceStore'

export type FilePreviewType = 'sheets' | 'docs' | 'slides' | 'code' | 'email' | 'chart'

interface FilePreviewCardProps {
  type: FilePreviewType
  title: string
  subtitle?: string
  previewData: {
    // For sheets:
    rows?: string[][]
    // For docs:
    text?: string
    // For slides:
    thumbnailUrl?: string
    presentationId?: string
    // For code:
    code?: string
    language?: string
    // For email:
    subject?: string
    body?: string
    // For chart:
    chartType?: string
    series?: any[]
  }
  fileId: string
  fileUrl?: string
  onOpenInPanel: () => void
}

const getFileIcon = (type: FilePreviewType): string => {
  switch (type) {
    case 'sheets':
      return '📊'
    case 'docs':
      return '📄'
    case 'slides':
      return '📑'
    case 'code':
      return '💻'
    case 'email':
      return '✉️'
    case 'chart':
      return '📈'
    default:
      return '📄'
  }
}

export function FilePreviewCard({
  type,
  title,
  subtitle,
  previewData,
  fileId,
  fileUrl,
  onOpenInPanel
}: FilePreviewCardProps) {
  const renderPreview = () => {
    switch (type) {
      case 'sheets':
        if (previewData.rows && previewData.rows.length > 0) {
          const displayRows = previewData.rows.slice(0, 5)
          const remainingRows = previewData.rows.length - 5
          return (
            <div className="preview-table">
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '11px' }}>
                <tbody>
                  {displayRows.map((row, i) => (
                    <tr key={i}>
                      {row.slice(0, 4).map((cell, j) => (
                        <td
                          key={j}
                          style={{
                            padding: '4px 8px',
                            border: '1px solid #e5e5e5',
                            maxWidth: '100px',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap'
                          }}
                        >
                          {cell?.substring(0, 20) || ''}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              {remainingRows > 0 && (
                <div style={{ padding: '4px 8px', fontSize: '11px', color: '#9ca3af' }}>
                  +{remainingRows} строк
                </div>
              )}
            </div>
          )
        }
        return <div style={{ padding: '8px', fontSize: '13px', color: '#9ca3af' }}>Нет данных для предпросмотра</div>

      case 'docs':
        if (previewData.text) {
          const previewText = previewData.text.substring(0, 300)
          return (
            <div className="preview-text" style={{ padding: '8px', fontSize: '13px', lineHeight: '1.5', color: '#111' }}>
              {previewText}
              {previewData.text.length > 300 && '...'}
            </div>
          )
        }
        return <div style={{ padding: '8px', fontSize: '13px', color: '#9ca3af' }}>Нет текста для предпросмотра</div>

      case 'slides':
        if (previewData.presentationId) {
          return (
            <div className="preview-slides" style={{ width: '100%', height: '150px', position: 'relative', overflow: 'hidden' }}>
              <iframe
                src={`https://docs.google.com/presentation/d/${previewData.presentationId}/embed?start=false&loop=false&delayms=3000`}
                style={{
                  border: 'none',
                  transform: 'scale(0.5)',
                  transformOrigin: 'top left',
                  width: '200%',
                  height: '200%'
                }}
                title={title}
              />
            </div>
          )
        }
        return <div style={{ padding: '8px', fontSize: '13px', color: '#9ca3af' }}>Нет данных для предпросмотра</div>

      case 'code':
        if (previewData.code) {
          const previewCode = previewData.code.substring(0, 500)
          return (
            <pre className="preview-code" style={{ margin: 0, padding: '8px', fontSize: '11px', overflow: 'auto', backgroundColor: '#f5f5f5' }}>
              <code>{previewCode}{previewData.code.length > 500 && '\n// ...'}</code>
            </pre>
          )
        }
        return <div style={{ padding: '8px', fontSize: '13px', color: '#9ca3af' }}>Нет кода для предпросмотра</div>

      case 'email':
        return (
          <div className="preview-email" style={{ padding: '8px' }}>
            {previewData.subject && (
              <div style={{ fontSize: '13px', fontWeight: '500', marginBottom: '4px', color: '#111' }}>
                Тема: {previewData.subject}
              </div>
            )}
            {previewData.body && (
              <div style={{ fontSize: '12px', lineHeight: '1.5', color: '#666', maxHeight: '100px', overflow: 'hidden' }}>
                {previewData.body.substring(0, 200)}
                {previewData.body.length > 200 && '...'}
              </div>
            )}
          </div>
        )

      case 'chart':
        return (
          <div className="preview-chart" style={{ padding: '8px', fontSize: '13px', color: '#9ca3af' }}>
            График: {previewData.chartType || 'Chart'}
            {previewData.series && ` (${previewData.series.length} серий)`}
          </div>
        )

      default:
        return <div style={{ padding: '8px', fontSize: '13px', color: '#9ca3af' }}>Превью недоступно</div>
    }
  }

  return (
    <div className="file-preview-card">
      <div className="file-preview-header">
        <span style={{ fontSize: '16px' }}>{getFileIcon(type)}</span>
        <div style={{ flex: 1 }}>
          <div className="file-preview-title">{title}</div>
          {subtitle && <div className="file-preview-subtitle">{subtitle}</div>}
        </div>
      </div>
      <div className="file-preview-content">
        {renderPreview()}
      </div>
      <div className="file-preview-footer">
        <button className="file-preview-button" onClick={onOpenInPanel}>
          Открыть в панели →
        </button>
      </div>
    </div>
  )
}

