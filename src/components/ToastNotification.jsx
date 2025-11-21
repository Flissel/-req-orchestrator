import { useState, useEffect } from 'react'

/**
 * ToastNotification - Animated countdown notification with cancel button
 *
 * Features:
 * - Countdown timer (3 seconds default)
 * - Cancel button to abort action
 * - Auto-dismisses after countdown
 * - Smooth slide-in animation
 */
export default function ToastNotification({
  message,
  countdown = 3,
  onComplete,
  onCancel,
  show = false
}) {
  const [timeLeft, setTimeLeft] = useState(countdown)
  const [isVisible, setIsVisible] = useState(show)

  useEffect(() => {
    setIsVisible(show)
    setTimeLeft(countdown)
  }, [show, countdown])

  useEffect(() => {
    if (!isVisible || timeLeft <= 0) return

    const timer = setInterval(() => {
      setTimeLeft(prev => {
        if (prev <= 1) {
          clearInterval(timer)
          if (onComplete) {
            onComplete()
          }
          setIsVisible(false)
          return 0
        }
        return prev - 1
      })
    }, 1000)

    return () => clearInterval(timer)
  }, [isVisible, timeLeft, onComplete])

  const handleCancel = () => {
    setIsVisible(false)
    if (onCancel) {
      onCancel()
    }
  }

  if (!isVisible) return null

  const progressPercent = ((countdown - timeLeft) / countdown) * 100

  return (
    <div style={{
      position: 'fixed',
      top: '20px',
      right: '20px',
      zIndex: 2000,
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      color: 'white',
      padding: '16px 20px',
      borderRadius: '12px',
      boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
      minWidth: '320px',
      maxWidth: '420px',
      animation: 'slideInRight 0.3s ease-out'
    }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '12px'
      }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: '15px', fontWeight: '600', marginBottom: '4px' }}>
            🚀 Auto-Validierung
          </div>
          <div style={{ fontSize: '13px', opacity: 0.95, lineHeight: '1.4' }}>
            {message}
          </div>
        </div>
        <button
          onClick={handleCancel}
          style={{
            background: 'rgba(255, 255, 255, 0.2)',
            border: 'none',
            color: 'white',
            borderRadius: '6px',
            padding: '6px 12px',
            fontSize: '13px',
            cursor: 'pointer',
            fontWeight: '600',
            marginLeft: '12px',
            transition: 'background 0.2s'
          }}
          onMouseEnter={(e) => {
            e.target.style.background = 'rgba(255, 255, 255, 0.3)'
          }}
          onMouseLeave={(e) => {
            e.target.style.background = 'rgba(255, 255, 255, 0.2)'
          }}
        >
          Abbrechen
        </button>
      </div>

      {/* Countdown Progress Bar */}
      <div style={{
        position: 'relative',
        height: '6px',
        background: 'rgba(255, 255, 255, 0.2)',
        borderRadius: '3px',
        overflow: 'hidden'
      }}>
        <div style={{
          position: 'absolute',
          left: 0,
          top: 0,
          height: '100%',
          width: `${progressPercent}%`,
          background: 'white',
          transition: 'width 1s linear',
          borderRadius: '3px'
        }} />
      </div>

      {/* Countdown Text */}
      <div style={{
        marginTop: '8px',
        fontSize: '12px',
        opacity: 0.9,
        textAlign: 'center',
        fontWeight: '600'
      }}>
        Startet in {timeLeft} Sekunde{timeLeft !== 1 ? 'n' : ''}...
      </div>

      <style>{`
        @keyframes slideInRight {
          from {
            transform: translateX(100%);
            opacity: 0;
          }
          to {
            transform: translateX(0);
            opacity: 1;
          }
        }
      `}</style>
    </div>
  )
}
