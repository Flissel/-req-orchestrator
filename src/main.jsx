import React from 'react'
import ReactDOM from 'react-dom/client'
import AppV2 from './AppV2.jsx'
import ErrorBoundary from './components/ErrorBoundary.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary>
      <AppV2 />
    </ErrorBoundary>
  </React.StrictMode>,
)