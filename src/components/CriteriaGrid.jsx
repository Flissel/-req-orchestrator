import React from 'react'
import './CriteriaGrid.css'

// Criteria configuration with tier information
const CRITERIA_CONFIG = {
  // Gating criteria (must pass at 80%+)
  atomic: { label: 'Atomic', tier: 'gating', threshold: 0.80, weight: 0.20 },
  clarity: { label: 'Clarity', tier: 'gating', threshold: 0.80, weight: 0.15 },
  testability: { label: 'Testability', tier: 'gating', threshold: 0.80, weight: 0.15 },

  // Priority criteria (should pass at 70%+)
  design_independent: { label: 'Design Independent', tier: 'priority', threshold: 0.70, weight: 0.12 },
  unambiguous: { label: 'Unambiguous', tier: 'priority', threshold: 0.70, weight: 0.12 },

  // Polish criteria (target 60%+)
  concise: { label: 'Concise', tier: 'polish', threshold: 0.60, weight: 0.08 },
  consistent_language: { label: 'Consistent Language', tier: 'polish', threshold: 0.60, weight: 0.08 },
  measurability: { label: 'Measurability', tier: 'polish', threshold: 0.60, weight: 0.05 },
  purpose_independent: { label: 'Purpose Independent', tier: 'polish', threshold: 0.60, weight: 0.05 },
  follows_template: { label: 'Template', tier: 'polish', threshold: 0.60, weight: 0.00 }
}

// Ordered criteria by tier importance
const ORDERED_CRITERIA = [
  // Gating first
  'atomic', 'clarity', 'testability',
  // Priority second
  'design_independent', 'unambiguous',
  // Polish last
  'concise', 'consistent_language', 'measurability', 'purpose_independent', 'follows_template'
]

const TIER_LABELS = {
  gating: { label: 'GATING', color: '#dc3545', description: 'Must pass at 80%' },
  priority: { label: 'PRIORITY', color: '#fd7e14', description: 'Should pass at 70%' },
  polish: { label: 'POLISH', color: '#ffc107', description: 'Target 60%' }
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

  const getCriterionStatus = (criterion) => {
    const config = CRITERIA_CONFIG[criterion]
    const data = criteriaMap.get(criterion)
    if (!data) return { status: 'unknown', score: null, reason: '', tier: config?.tier || 'priority' }

    const threshold = config?.threshold || 0.70
    const passedThreshold = data.score >= threshold

    return {
      status: passedThreshold ? 'pass' : 'fail',
      score: data.score,
      reason: data.reason,
      tier: config?.tier || 'priority',
      threshold: threshold
    }
  }

  const getScoreColor = (score, tier, threshold) => {
    if (score === null) return 'var(--muted)'
    if (score >= threshold) return 'var(--ok)'
    // For failing scores, use tier color
    if (tier === 'gating') return '#dc3545'
    if (tier === 'priority') return '#fd7e14'
    return '#ffc107'
  }

  const getTierBadgeColor = (tier) => {
    return TIER_LABELS[tier]?.color || '#6c757d'
  }

  // Group criteria by tier for display
  const groupedCriteria = {
    gating: ORDERED_CRITERIA.filter(c => CRITERIA_CONFIG[c]?.tier === 'gating'),
    priority: ORDERED_CRITERIA.filter(c => CRITERIA_CONFIG[c]?.tier === 'priority'),
    polish: ORDERED_CRITERIA.filter(c => CRITERIA_CONFIG[c]?.tier === 'polish')
  }

  const renderCriterion = (criterion) => {
    const config = CRITERIA_CONFIG[criterion]
    const { status, score, reason, tier, threshold } = getCriterionStatus(criterion)
    const percentage = score !== null ? Math.round(score * 100) : null
    const thresholdPercent = Math.round((threshold || 0.70) * 100)

    return (
      <div
        key={criterion}
        className={`criterion-item ${status} tier-${tier}`}
        title={reason || `${config?.label}: ${percentage !== null ? percentage + '%' : 'Not evaluated'} (threshold: ${thresholdPercent}%)`}
      >
        <div className="criterion-header">
          <span className="criterion-name">{config?.label}</span>
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
                  backgroundColor: getScoreColor(score, tier, threshold)
                }}
              />
              {/* Threshold marker */}
              <div
                className="score-threshold-marker"
                style={{ left: `${thresholdPercent}%` }}
                title={`Threshold: ${thresholdPercent}%`}
              />
            </div>
            <span className="score-text" style={{ color: getScoreColor(score, tier, threshold) }}>
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
  }

  return (
    <div className="criteria-grid-container">
      {/* Gating Criteria Section */}
      <div className="tier-section">
        <div className="tier-header" style={{ borderColor: TIER_LABELS.gating.color }}>
          <span className="tier-badge" style={{ backgroundColor: TIER_LABELS.gating.color }}>
            {TIER_LABELS.gating.label}
          </span>
          <span className="tier-description">{TIER_LABELS.gating.description}</span>
        </div>
        <div className="criteria-grid">
          {groupedCriteria.gating.map(renderCriterion)}
        </div>
      </div>

      {/* Priority Criteria Section */}
      <div className="tier-section">
        <div className="tier-header" style={{ borderColor: TIER_LABELS.priority.color }}>
          <span className="tier-badge" style={{ backgroundColor: TIER_LABELS.priority.color }}>
            {TIER_LABELS.priority.label}
          </span>
          <span className="tier-description">{TIER_LABELS.priority.description}</span>
        </div>
        <div className="criteria-grid">
          {groupedCriteria.priority.map(renderCriterion)}
        </div>
      </div>

      {/* Polish Criteria Section */}
      <div className="tier-section">
        <div className="tier-header" style={{ borderColor: TIER_LABELS.polish.color }}>
          <span className="tier-badge" style={{ backgroundColor: TIER_LABELS.polish.color }}>
            {TIER_LABELS.polish.label}
          </span>
          <span className="tier-description">{TIER_LABELS.polish.description}</span>
        </div>
        <div className="criteria-grid">
          {groupedCriteria.polish.map(renderCriterion)}
        </div>
      </div>
    </div>
  )
}

export default CriteriaGrid
