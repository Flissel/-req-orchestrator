import React from 'react'
import './ValidationRequirementCard.css'

const ValidationRequirementCard = ({ requirement, isSelected, onClick, batchStatus }) => {
  const score = requirement.validation_score || 0
  const percentage = Math.round(score * 100)

  // Get violated criteria
  const violatedCriteria = requirement.evaluation
    ? requirement.evaluation
        .filter(e => e.isValid === false)
        .map(e => e.criterion)
    : []

  // Determine severity color
  const getSeverityClass = () => {
    if (score < 0.5) return 'severe'
    if (score < 0.7) return 'warning'
    return 'ok'
  }

  // Get batch status indicator
  const getBatchStatusIcon = () => {
    if (!batchStatus) return null
    switch (batchStatus) {
      case 'validating': return '~'
      case 'passed': return '+'
      case 'failed': return 'x'
      default: return '-'
    }
  }

  // Truncate text for display
  const truncateText = (text, maxLength = 60) => {
    if (!text) return ''
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text
  }

  return (
    <div
      className={`validation-req-card ${getSeverityClass()} ${isSelected ? 'selected' : ''} ${batchStatus ? `batch-${batchStatus}` : ''}`}
      onClick={onClick}
    >
      <div className="card-header">
        <span className="req-id">
          {batchStatus && (
            <span className={`batch-icon ${batchStatus}`}>[{getBatchStatusIcon()}]</span>
          )}
          {requirement.req_id}
        </span>
        <span className={`score-indicator ${getSeverityClass()}`}>
          {percentage}%
        </span>
      </div>

      <div className="card-content">
        <p className="req-text">{truncateText(requirement.title || requirement.text)}</p>
      </div>

      {violatedCriteria.length > 0 && (
        <div className="violated-criteria">
          {violatedCriteria.slice(0, 3).map((criterion, idx) => (
            <span key={idx} className="criterion-badge">
              {criterion}
            </span>
          ))}
          {violatedCriteria.length > 3 && (
            <span className="criterion-badge more">
              +{violatedCriteria.length - 3}
            </span>
          )}
        </div>
      )}

      <div className="card-actions">
        <button
          className="btn-validate-single"
          onClick={(e) => {
            e.stopPropagation()
            // Trigger single validation
          }}
        >
          Validate
        </button>
      </div>
    </div>
  )
}

export default ValidationRequirementCard
