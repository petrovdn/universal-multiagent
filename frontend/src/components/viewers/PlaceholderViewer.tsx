import React from 'react'
import { Sparkles } from 'lucide-react'

export function PlaceholderViewer() {
  return (
    <div 
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: document.documentElement.classList.contains('dark')
          ? 'rgb(30 41 59)'
          : 'rgb(255 255 255)',
        flex: '1 1 auto'
      }}
    >
      <div style={{ textAlign: 'center', maxWidth: '400px', padding: '0 24px' }}>
        <div style={{ marginBottom: '24px', display: 'flex', justifyContent: 'center' }}>
          <div className="p-4 rounded-full bg-blue-100 dark:bg-blue-900/30">
            <Sparkles className="w-12 h-12 text-blue-600 dark:text-blue-400" />
          </div>
        </div>
        <h2 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
          AI that works. Not talks.
        </h2>
      </div>
    </div>
  )
}

