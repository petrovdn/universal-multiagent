import React, { useState } from 'react'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { Copy, Check, Moon, Sun } from 'lucide-react'
import type { WorkspaceTab } from '../../types/workspace'
import type { CodeData } from '../../types/workspace'

interface CodeViewerProps {
  tab: WorkspaceTab
}

export function CodeViewer({ tab }: CodeViewerProps) {
  const [copied, setCopied] = useState(false)
  const [isDark, setIsDark] = useState(true)
  const codeData = tab.data as CodeData | undefined

  const code = codeData?.code || ''
  const language = codeData?.language || 'python'
  const filename = codeData?.filename || tab.title

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }

  const theme = isDark ? vscDarkPlus : oneLight

  if (!code) {
    return (
      <div className="h-full w-full flex items-center justify-center">
        <div className="text-center">
          <p className="text-slate-600 dark:text-slate-400">Код не загружен</p>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full w-full flex flex-col bg-white dark:bg-slate-900">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-slate-200 dark:border-slate-700">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
            {filename}
          </span>
          <span className="text-xs text-slate-500 dark:text-slate-500 px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800">
            {language}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsDark(!isDark)}
            className="p-2 rounded hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            title={isDark ? 'Светлая тема' : 'Темная тема'}
          >
            {isDark ? (
              <Sun className="w-4 h-4 text-slate-600 dark:text-slate-400" />
            ) : (
              <Moon className="w-4 h-4 text-slate-600 dark:text-slate-400" />
            )}
          </button>
          <button
            onClick={handleCopy}
            className="p-2 rounded hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors flex items-center gap-1"
            title="Копировать код"
          >
            {copied ? (
              <>
                <Check className="w-4 h-4 text-green-600 dark:text-green-400" />
                <span className="text-xs text-green-600 dark:text-green-400">Скопировано</span>
              </>
            ) : (
              <>
                <Copy className="w-4 h-4 text-slate-600 dark:text-slate-400" />
                <span className="text-xs text-slate-600 dark:text-slate-400">Копировать</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Code */}
      <div className="flex-1 overflow-auto">
        <SyntaxHighlighter
          language={language}
          style={theme}
          customStyle={{
            margin: 0,
            padding: '1rem',
            height: '100%',
            fontSize: '14px',
            lineHeight: '1.6',
          }}
          showLineNumbers
          wrapLines
        >
          {code}
        </SyntaxHighlighter>
      </div>
    </div>
  )
}

