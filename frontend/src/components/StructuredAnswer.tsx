import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { CheckCircle, XCircle, Loader2 } from 'lucide-react'

interface StructuredAnswerProps {
  content: string
  isStreaming?: boolean
}

interface AttemptBlock {
  number: string
  title: string
  content: string
}

export function StructuredAnswer({ content, isStreaming }: StructuredAnswerProps) {
  // Parse content into logical blocks based on the "--- ## Попытка N:" pattern
  const parseAttempts = (text: string): { attempts: AttemptBlock[], remaining: string } => {
    const attempts: AttemptBlock[] = []
    
    // Split by "---" markers
    const parts = text.split(/---\s*\n/)
    
    let remaining = ''
    
    parts.forEach((part) => {
      const trimmedPart = part.trim()
      if (!trimmedPart) return
      
      // Check if this part starts with "## Попытка [N]:"
      const attemptMatch = trimmedPart.match(/^##\s*Попытка\s+(\d+):\s*(.+?)(?:\n([\s\S]*))?$/)
      
      if (attemptMatch) {
        attempts.push({
          number: attemptMatch[1],
          title: attemptMatch[2].trim(),
          content: attemptMatch[3] ? attemptMatch[3].trim() : ''
        })
      } else {
        // This is remaining content (not an attempt block)
        remaining += (remaining ? '\n\n' : '') + trimmedPart
      }
    })
    
    return { attempts, remaining }
  }
  
  const { attempts, remaining } = parseAttempts(content)
  
  // If no structured attempts found, render as plain markdown
  if (attempts.length === 0) {
    return (
      <div className="answer-block">
        <div className="answer-block-content">
          {content ? (
            <div className="prose max-w-none 
              prose-p:text-gray-900 
              prose-p:leading-6 prose-p:my-3 prose-p:text-[15px]
              prose-h1:text-gray-900 prose-h1:text-[20px] prose-h1:font-semibold prose-h1:mb-3 prose-h1:mt-6 prose-h1:first:mt-0 prose-h1:leading-tight
              prose-h2:text-gray-900 prose-h2:text-[18px] prose-h2:font-semibold prose-h2:mb-2 prose-h2:mt-5 prose-h2:leading-tight
              prose-h3:text-gray-900 prose-h3:text-[16px] prose-h3:font-semibold prose-h3:mb-2 prose-h3:mt-4 prose-h3:leading-tight
              prose-strong:text-gray-900 prose-strong:font-semibold
              prose-code:text-gray-900 prose-code:bg-gray-100 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-[13px] prose-code:border prose-code:border-gray-200
              prose-pre:bg-gray-100 prose-pre:text-gray-900 prose-pre:border prose-pre:border-gray-200 prose-pre:text-[13px] prose-pre:rounded-lg prose-pre:p-4
              prose-ul:text-gray-900 prose-ul:my-3
              prose-li:text-gray-900 prose-li:my-1.5 prose-li:text-[15px]
              prose-a:text-blue-600 prose-a:underline hover:prose-a:text-blue-700
              prose-blockquote:text-gray-600 prose-blockquote:border-l-gray-300 prose-blockquote:pl-4 prose-blockquote:my-3">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
              {isStreaming && (
                <span className="answer-block-cursor">▊</span>
              )}
            </div>
          ) : isStreaming ? (
            <div className="answer-block-placeholder">
              <span className="answer-block-cursor">▊</span>
            </div>
          ) : null}
        </div>
      </div>
    )
  }
  
  // Render structured attempts as separate visual blocks
  return (
    <div className="answer-block">
      <div className="space-y-3">
        {attempts.map((attempt, index) => (
          <div 
            key={index}
            style={{
              padding: '12px 16px',
              background: '#f8f9fa',
              border: '1px solid #e0e0e0',
              borderRadius: '8px',
              marginBottom: '8px'
            }}
          >
            <div style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '8px', 
              marginBottom: '8px',
              color: '#1976d2',
              fontWeight: '600',
              fontSize: '14px'
            }}>
              <Loader2 style={{ width: '16px', height: '16px' }} />
              <span>Попытка {attempt.number}: {attempt.title}</span>
            </div>
            {attempt.content && (
              <div className="prose prose-sm max-w-none
                prose-p:text-gray-700 prose-p:text-[14px] prose-p:my-2
                prose-ul:my-2 prose-li:text-[14px] prose-li:text-gray-700
                prose-code:text-[13px] prose-code:bg-white prose-code:px-1 prose-code:py-0.5">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{attempt.content}</ReactMarkdown>
              </div>
            )}
          </div>
        ))}
        
        {remaining && (
          <div style={{ marginTop: '16px' }}>
            <div className="prose max-w-none 
              prose-p:text-gray-900 prose-p:text-[15px]
              prose-h2:text-gray-900 prose-h2:text-[18px] prose-h2:font-semibold
              prose-ul:my-3 prose-li:text-[15px]">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{remaining}</ReactMarkdown>
            </div>
          </div>
        )}
        
        {isStreaming && (
          <div style={{ marginTop: '8px' }}>
            <span className="answer-block-cursor">▊</span>
          </div>
        )}
      </div>
    </div>
  )
}

