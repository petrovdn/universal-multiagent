import React from 'react'
import ReactDOM from 'react-dom/client'
import { WorkspaceFileSelectorWindow } from './components/WorkspaceFileSelectorWindow'
import './index.css'

console.log('[file-selector.tsx] Script loaded and imports completed')

const rootElement = document.getElementById('root')
console.log('[file-selector.tsx] Root element:', rootElement ? 'found' : 'not found')

if (rootElement) {
  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
      <WorkspaceFileSelectorWindow />
    </React.StrictMode>
  )
  console.log('[file-selector.tsx] React root created')
} else {
  console.error('[file-selector.tsx] Root element not found!')
}

