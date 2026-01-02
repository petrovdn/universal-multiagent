import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface FinalResultBlockProps {
  content: string
}

export function FinalResultBlock({ content }: FinalResultBlockProps) {
  if (!content || content.trim().length === 0) {
    return null
  }

  return (
    <div style={{ 
      maxWidth: '900px',
      width: '100%',
      margin: '0 auto',
      marginTop: '24px',
      paddingTop: '24px',
      paddingLeft: '14px',
      paddingRight: '14px',
      borderTop: '1px solid var(--border-secondary)'
    }}>
      <div className="prose max-w-none 
        prose-p:text-gray-900 
        prose-p:leading-6 prose-p:my-3 prose-p:text-[13px]
        prose-h1:text-gray-900 prose-h1:text-[20px] prose-h1:font-semibold prose-h1:mb-3 prose-h1:mt-6 prose-h1:first:mt-0 prose-h1:leading-tight
        prose-h2:text-gray-900 prose-h2:text-[18px] prose-h2:font-semibold prose-h2:mb-2 prose-h2:mt-5 prose-h2:leading-tight
        prose-h3:text-gray-900 prose-h3:text-[16px] prose-h3:font-semibold prose-h3:mb-2 prose-h3:mt-4 prose-h3:leading-tight
        prose-strong:text-gray-900 prose-strong:font-semibold
        prose-code:text-gray-900 prose-code:bg-gray-100 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-[13px] prose-code:border prose-code:border-gray-200
        prose-pre:bg-gray-100 prose-pre:text-gray-900 prose-pre:border prose-pre:border-gray-200 prose-pre:text-[13px] prose-pre:rounded-lg prose-pre:p-4
        prose-ul:text-gray-900 prose-ul:my-3 prose-ul:pl-10
        prose-ol:text-gray-900 prose-ol:my-3 prose-ol:pl-10
        prose-li:text-gray-900 prose-li:my-1.5 prose-li:text-[13px]
        prose-a:text-blue-600 prose-a:underline hover:prose-a:text-blue-700
        prose-blockquote:text-gray-600 prose-blockquote:border-l-gray-300 prose-blockquote:pl-4 prose-blockquote:my-3
        prose-table:w-full prose-table:border-collapse prose-table:my-4
        prose-th:border prose-th:border-gray-300 prose-th:bg-gray-50 prose-th:px-3 prose-th:py-2 prose-th:text-left prose-th:font-semibold
        prose-td:border prose-td:border-gray-300 prose-td:px-3 prose-td:py-2
        prose-tr:hover:bg-gray-50">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      </div>
    </div>
  )
}

