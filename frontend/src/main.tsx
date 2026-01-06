import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'

// #region agent log
// Check CSS loading
if (typeof window !== 'undefined') {
  setTimeout(() => {
    const testEl = document.createElement('div')
    testEl.className = 'input-area'
    document.body.appendChild(testEl)
    const style = window.getComputedStyle(testEl)
    const position = style.position
    document.body.removeChild(testEl)
    console.log('[DEBUG main.tsx] CSS styles check - input-area position:', position, 'Expected: relative')
  }, 500)
}
// #endregion

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







