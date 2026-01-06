import React from 'react'
import ReactDOM from 'react-dom/client'
import { OneCSettingsWindow } from './components/OneCSettingsWindow'
import './index.css'

const rootElement = document.getElementById('root')

if (rootElement) {
  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
      <OneCSettingsWindow />
    </React.StrictMode>
  )
} else {
  console.error('[onec-settings.tsx] Root element not found!')
}




