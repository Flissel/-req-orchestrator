import React from 'react'
import './CriteriaGrid.css'

const CRITERIA_LABELS = {
  clarity: 'Clarity',
  testability: 'Testability',
  measurability: 'Measurability',
  atomic: 'Atomic',
  concise: 'Concise',
  unambiguous: 'Unambiguous',
  consistent_language: 'Consistent Language',
  follows_template: 'Follows Template',
  design_independent: 'Design Independent',
  purpose_independent: 'Purpose Independent'
}

const CriteriaGrid = ({ requirement }) => {
  // Extract evaluation data
  const evaluation = requirement.evaluation || []

  // Create criteria map - accept both backend and frontend formats
  const criteriaMap = new Map()
  evaluation.forEach(e => {
    // Accept both "isValid" (frontend) and "passed" (backend) formats
    const isValid = e.isValid !== undefined ? e.isValid : e.passed
    // Accept both "reason" (frontend) and "feedback" (backend) formats
    const reason = e.reason || e.feedback || ''

    criteriaMap.set(e.criterion, {
      isValid: isValid,
      reason: reason,
      score: e.score !== undefined ? e.score : (isValid ? 1.0 : 0.0)
    })
  })

  // Get all criteria (default to all 10 if not present)
  const allCriteria = Object.keys(CRITERIA_LABELS)

  const getCriterionStatus = (criterion) => {
    const data = criteriaMap.get(criterion)
    if (!data) return { status: 'unknown', score: null, reason: '' }

    return {
      status: data.isValid ? 'pass' : 'fail',
      score: data.score,
      reason: data.reason
    }
  }

  const getScoreColor = (score) => {
    if (score === null) return 'var(--muted)'
    if (score >= 0.7) return 'var(--ok)'
    if (score >= 0.5) return 'var(--warn)'
    return 'var(--err)'
  }

  return (
    <div className="criteria-grid">
      {allCriteria.map(criterion => {
        const { status, score, reason } = getCriterionStatus(criterion)
        const percentage = score !== null ? Math.round(score * 100) : null

        return (
          <div
            key={criterion}
            className={`criterion-item ${status}`}
            title={reason || `${CRITERIA_LABELS[criterion]}: ${percentage !== null ? percentage + '%' : 'Not evaluated'}`}
          >
            <div className="criterion-header">
              <span className="criterion-name">{CRITERIA_LABELS[criterion]}</span>
              <span className="criterion-status-icon">
                {status === 'pass' ? '✓' : status === 'fail' ? '✗' : '?'}
              </span>
            </div>

            {percentage !== null && (
              <div className="criterion-score">
                <div className="score-bar-container">
                  <div
                    className="score-bar-fill"
                    style={{
                      width: `${percentage}%`,
                      backgroundColor: getScoreColor(score)
                    }}
                  />
                </div>
                <span className="score-text" style={{ color: getScoreColor(score) }}>
                  {percentage}%
                </span>
              </div>
            )}

            {reason && (
              <div className="criterion-reason">
                {reason}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

export default CriteriaGrid
