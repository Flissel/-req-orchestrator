import { useState } from 'react'

/**
 * BatchValidationButton - Shows queue of failing requirements with batch validation trigger
 *
 * Features:
 * - Badge with count of failing requirements (score < 0.7)
 * - Estimated time and cost preview
 * - Opens BatchValidationModal on click
 */
export default function BatchValidationButton({ failingRequirements, onStartBatch }) {
  const [showPreview, setShowPreview] = useState(false)

  if (!failingRequirements || failingRequirements.length === 0) {
    return null
  }

  const count = failingRequirements.length
  const estimatedTimeSeconds = count * 3 // ~3 seconds per requirement
  const estimatedMinutes = Math.ceil(estimatedTimeSeconds / 60)

  return (
    <div style={{
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      borderRadius: '12px',
      padding: '20px',
      margin: '20px 0',
      color: 'white',
      boxShadow: '0 4px 6px rgba(0,0,0,0.1)'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
            <h3 style={{ margin: 0, fontSize: '18px', fontWeight: '600' }}>
              🔧 Requirements Need Improvement
            </h3>
            <span style={{
              background: 'rgba(255,255,255,0.3)',
              borderRadius: '12px',
              padding: '4px 12px',
              fontSize: '14px',
              fontWeight: '700'
            }}>
              {count}
            </span>
          </div>

          <p style={{
            margin: '8px 0',
            fontSize: '14px',
            opacity: 0.95,
            lineHeight: '1.5'
          }}>
            {count} requirement{count > 1 ? 's have' : ' has'} quality scores below 0.7 threshold
          </p>

          {showPreview && (
            <div style={{
              background: 'rgba(255,255,255,0.15)',
              borderRadius: '8px',
              padding: '12px',
              marginTop: '12px',
              fontSize: '13px'
            }}>
              <div style={{ fontWeight: '600', marginBottom: '8px' }}>
                Batch validation will:
              </div>
              <ul style={{ margin: '0', paddingLeft: '20px', lineHeight: '1.6' }}>
                <li>Auto-fix failing quality criteria</li>
                <li>Split requirements with atomic violations</li>
                <li>Apply LLM-powered improvements</li>
                <li>Show before/after diffs</li>
              </ul>
              <div style={{
                marginTop: '12px',
                paddingTop: '12px',
                borderTop: '1px solid rgba(255,255,255,0.2)',
                display: 'flex',
                justifyContent: 'space-between'
              }}>
                <span>⏱ Estimated time:</span>
                <span style={{ fontWeight: '600' }}>~{estimatedMinutes} minute{estimatedMinutes > 1 ? 's' : ''}</span>
              </div>
            </div>
          )}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginLeft: '20px' }}>
          <button
            onClick={() => onStartBatch(failingRequirements)}
            style={{
              background: 'white',
              color: '#667eea',
              border: 'none',
              borderRadius: '8px',
              padding: '12px 24px',
              fontSize: '15px',
              fontWeight: '600',
              cursor: 'pointer',
              boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
              transition: 'all 0.2s'
            }}
            onMouseEnter={(e) => {
              e.target.style.transform = 'translateY(-2px)'
              e.target.style.boxShadow = '0 4px 8px rgba(0,0,0,0.2)'
            }}
            onMouseLeave={(e) => {
              e.target.style.transform = 'translateY(0)'
              e.target.style.boxShadow = '0 2px 4px rgba(0,0,0,0.1)'
            }}
          >
            Fix All ({count})
          </button>

          <button
            onClick={() => setShowPreview(!showPreview)}
            style={{
              background: 'transparent',
              color: 'white',
              border: '1px solid rgba(255,255,255,0.3)',
              borderRadius: '8px',
              padding: '8px 16px',
              fontSize: '13px',
              cursor: 'pointer',
              transition: 'all 0.2s'
            }}
            onMouseEnter={(e) => {
              e.target.style.background = 'rgba(255,255,255,0.1)'
            }}
            onMouseLeave={(e) => {
              e.target.style.background = 'transparent'
            }}
          >
            {showPreview ? '▲ Hide Details' : '▼ Show Details'}
          </button>
        </div>
      </div>

      {/* Show first few failing requirements */}
      {showPreview && (
        <div style={{
          marginTop: '16px',
          paddingTop: '16px',
          borderTop: '1px solid rgba(255,255,255,0.2)'
        }}>
          <div style={{ fontSize: '13px', fontWeight: '600', marginBottom: '8px' }}>
            Failing Requirements:
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {failingRequirements.slice(0, 5).map((req, idx) => (
              <div
                key={req.req_id || idx}
                style={{
                  fontSize: '12px',
                  opacity: 0.9,
                  padding: '4px 8px',
                  background: 'rgba(255,255,255,0.1)',
                  borderRadius: '4px'
                }}
              >
                <span style={{ fontWeight: '600' }}>{req.req_id || `REQ-${idx+1}`}</span>
                {' '}
                - Score: {req.validation_score !== undefined ? (req.validation_score * 100).toFixed(0) : '?'}%
                {' '}
                - {req.title?.substring(0, 60) || 'No title'}{req.title?.length > 60 ? '...' : ''}
              </div>
            ))}
            {failingRequirements.length > 5 && (
              <div style={{ fontSize: '12px', opacity: 0.7, fontStyle: 'italic', marginTop: '4px' }}>
                ... and {failingRequirements.length - 5} more
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
