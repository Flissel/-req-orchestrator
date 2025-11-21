import React, { useState } from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import AppV2 from './AppV2.jsx'
import ErrorBoundary from './components/ErrorBoundary.jsx'
import './index.css'

function AppSwitch() {
  const [useV2, setUseV2] = useState(() => {
    const saved = localStorage.getItem('useAppV2')
    return saved === 'true'
  })

  const handleToggle = () => {
    const newValue = !useV2
    setUseV2(newValue)
    localStorage.setItem('useAppV2', newValue.toString())
  }

  return (
    <>
      <div style={{
        position: 'fixed',
        top: '10px',
        right: '10px',
        zIndex: 10000,
        background: useV2 ? '#4cc9f0' : '#9aa5b1',
        color: 'white',
        padding: '8px 16px',
        borderRadius: '20px',
        fontSize: '12px',
        fontWeight: '600',
        cursor: 'pointer',
        boxShadow: '0 2px 8px rgba(0,0,0,0.3)',
        transition: 'all 0.3s ease'
      }} onClick={handleToggle}>
        {useV2 ? '✨ New UI (V2)' : '📦 Legacy UI (V1)'} • Click to switch
      </div>
      {useV2 ? <AppV2 /> : <App />}
    </>
  )
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary>
      <AppSwitch />
    </ErrorBoundary>
  </React.StrictMode>,
)