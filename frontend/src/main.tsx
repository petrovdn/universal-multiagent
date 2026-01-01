import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'

console.log('[main.tsx] Starting app...')

try {
  const rootElement = document.getElementById('root')
  if (!rootElement) {
    console.error('[main.tsx] Root element not found!')
    throw new Error('Root element not found')
  }
  
  console.log('[main.tsx] Root element found, creating root...')
  const root = ReactDOM.createRoot(rootElement)
  
  console.log('[main.tsx] Rendering App...')
  root.render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  )
  console.log('[main.tsx] App rendered successfully')
} catch (error) {
  console.error('[main.tsx] Error rendering app:', error)
  throw error
}






