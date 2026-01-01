import React from 'react'
import { Mail, User, FileText, Paperclip } from 'lucide-react'
import type { WorkspaceTab } from '../../types/workspace'

interface EmailPreviewProps {
  tab: WorkspaceTab
}

export function EmailPreview({ tab }: EmailPreviewProps) {
  const emailData = tab.data || {}
  const { to, subject, body, attachments = [] } = emailData

  return (
    <div className="h-full w-full flex flex-col bg-white dark:bg-slate-900">
      {/* Header */}
      <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-700">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 rounded bg-blue-100 dark:bg-blue-900/30">
            <Mail className="w-5 h-5 text-blue-600 dark:text-blue-400" />
          </div>
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
            Предпросмотр письма
          </h2>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        <div className="max-w-3xl mx-auto space-y-6">
          {/* To */}
          <div>
            <label className="flex items-center gap-2 text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
              <User className="w-4 h-4" />
              Кому:
            </label>
            <div className="px-4 py-2 bg-slate-50 dark:bg-slate-800 rounded border border-slate-200 dark:border-slate-700">
              <p className="text-slate-900 dark:text-slate-100">
                {to && Array.isArray(to) ? to.join(', ') : to || 'Не указано'}
              </p>
            </div>
          </div>

          {/* Subject */}
          <div>
            <label className="flex items-center gap-2 text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
              <FileText className="w-4 h-4" />
              Тема:
            </label>
            <div className="px-4 py-2 bg-slate-50 dark:bg-slate-800 rounded border border-slate-200 dark:border-slate-700">
              <p className="text-slate-900 dark:text-slate-100">
                {subject || 'Без темы'}
              </p>
            </div>
          </div>

          {/* Attachments */}
          {attachments && attachments.length > 0 && (
            <div>
              <label className="flex items-center gap-2 text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                <Paperclip className="w-4 h-4" />
                Вложения:
              </label>
              <div className="px-4 py-3 bg-slate-50 dark:bg-slate-800 rounded border border-slate-200 dark:border-slate-700">
                <ul className="space-y-1">
                  {attachments.map((att: any, idx: number) => (
                    <li key={idx} className="text-sm text-slate-700 dark:text-slate-300">
                      • {att.name || att.filename || `Вложение ${idx + 1}`}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          {/* Body */}
          <div>
            <label className="flex items-center gap-2 text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
              <FileText className="w-4 h-4" />
              Содержание:
            </label>
            <div className="px-4 py-4 bg-slate-50 dark:bg-slate-800 rounded border border-slate-200 dark:border-slate-700">
              <div className="prose prose-sm dark:prose-invert max-w-none">
                {body ? (
                  <div dangerouslySetInnerHTML={{ __html: body.replace(/\n/g, '<br/>') }} />
                ) : (
                  <p className="text-slate-500 dark:text-slate-400 italic">Текст письма отсутствует</p>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

