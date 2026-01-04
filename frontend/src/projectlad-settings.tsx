import React from 'react'
import ReactDOM from 'react-dom/client'
import { ProjectLadSettingsWindow } from './components/ProjectLadSettingsWindow'
import './index.css'

const rootElement = document.getElementById('root')

if (rootElement) {
  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
      <ProjectLadSettingsWindow />
    </React.StrictMode>
  )
} else {
  console.error('[projectlad-settings.tsx] Root element not found!')
}

