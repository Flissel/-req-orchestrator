import React from 'react'

/**
 * Error Boundary Component
 * Catches React rendering errors and displays fallback UI
 * Prevents entire app from crashing on component errors
 */
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null
    }
  }

  static getDerivedStateFromError(error) {
    // Update state so next render shows fallback UI
    return { hasError: true }
  }

  componentDidCatch(error, errorInfo) {
    // Log error details for debugging
    console.error('[ErrorBoundary] Caught error:', error)
    console.error('[ErrorBoundary] Error info:', errorInfo)

    // Update state with error details
    this.setState({
      error,
      errorInfo
    })

    // Optional: Send error to logging service
    // logErrorToService(error, errorInfo)
  }

  handleReset = () => {
    // Reset error state and attempt to recover
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null
    })
  }

  render() {
    if (this.state.hasError) {
      // Fallback UI when error occurs
      return (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '100vh',
          padding: '2rem',
          backgroundColor: '#1a1a1a',
          color: '#fff'
        }}>
          <div style={{
            maxWidth: '600px',
            textAlign: 'center',
            backgroundColor: '#2a2a2a',
            padding: '2rem',
            borderRadius: '8px',
            border: '1px solid #ff4444'
          }}>
            <h1 style={{ color: '#ff4444', marginBottom: '1rem' }}>
              ⚠️ Etwas ist schiefgelaufen
            </h1>
            <p style={{ marginBottom: '1.5rem', fontSize: '1.1rem' }}>
              Die Anwendung ist auf einen unerwarteten Fehler gestoßen.
            </p>

            {this.state.error && (
              <details style={{
                textAlign: 'left',
                marginBottom: '1.5rem',
                padding: '1rem',
                backgroundColor: '#1a1a1a',
                borderRadius: '4px',
                border: '1px solid #444'
              }}>
                <summary style={{ cursor: 'pointer', fontWeight: 'bold', marginBottom: '0.5rem' }}>
                  Fehlerdetails anzeigen
                </summary>
                <pre style={{
                  fontSize: '0.85rem',
                  overflow: 'auto',
                  maxHeight: '200px',
                  color: '#ff6666'
                }}>
                  {this.state.error.toString()}
                  {this.state.errorInfo && (
                    <>
                      {'\n\n'}
                      {this.state.errorInfo.componentStack}
                    </>
                  )}
                </pre>
              </details>
            )}

            <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center' }}>
              <button
                onClick={this.handleReset}
                style={{
                  padding: '0.75rem 1.5rem',
                  fontSize: '1rem',
                  backgroundColor: '#4CAF50',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontWeight: 'bold'
                }}
                onMouseOver={(e) => e.target.style.backgroundColor = '#45a049'}
                onMouseOut={(e) => e.target.style.backgroundColor = '#4CAF50'}
              >
                🔄 Erneut versuchen
              </button>

              <button
                onClick={() => window.location.reload()}
                style={{
                  padding: '0.75rem 1.5rem',
                  fontSize: '1rem',
                  backgroundColor: '#2196F3',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontWeight: 'bold'
                }}
                onMouseOver={(e) => e.target.style.backgroundColor = '#0b7dda'}
                onMouseOut={(e) => e.target.style.backgroundColor = '#2196F3'}
              >
                🔃 Seite neu laden
              </button>
            </div>

            <p style={{ marginTop: '1.5rem', fontSize: '0.9rem', color: '#999' }}>
              Wenn das Problem weiterhin besteht, überprüfen Sie bitte die Browser-Konsole
              oder kontaktieren Sie den Support.
            </p>
          </div>
        </div>
      )
    }

    // No error, render children normally
    return this.props.children
  }
}

export default ErrorBoundary
