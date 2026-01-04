import React from 'react'
import ReactDOM from 'react-dom/client'
import { WorkspaceFolderSelectorWindow } from './components/WorkspaceFolderSelectorWindow'
import './index.css'

const rootElement = document.getElementById('root')

if (rootElement) {
  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
      <WorkspaceFolderSelectorWindow />
    </React.StrictMode>
  )
} else {
  console.error('[workspace-folder-selector.tsx] Root element not found!')
}

