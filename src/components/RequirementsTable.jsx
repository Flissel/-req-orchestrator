import React, { useState, useMemo, useCallback } from 'react'
import { FixedSizeList as List } from 'react-window'
import './RequirementsTable.css'

// Row height for virtualized list
const ROW_HEIGHT = 60

const RequirementsTable = React.memo(({ requirements, onRequirementClick, onRequirementUpdate, onEnhanceRequirement }) => {
  const [sortBy, setSortBy] = useState('id')
  const [sortOrder, setSortOrder] = useState('asc')
  const [filterTag, setFilterTag] = useState('all')
  const [filterScore, setFilterScore] = useState('all')

  // Memoize unique tags - only recalculates when requirements change
  const uniqueTags = useMemo(() =>
    [...new Set(requirements.map(r => r.tag || 'untagged'))],
    [requirements]
  )

  // Memoize filtered and sorted requirements
  const filteredReqs = useMemo(() => {
    let result = [...requirements]

    // Filter by tag
    if (filterTag !== 'all') {
      result = result.filter(r => (r.tag || 'untagged') === filterTag)
    }

    // Filter by score
    if (filterScore === 'pass') {
      result = result.filter(r => r.validation_score !== undefined && r.validation_passed === true)
    } else if (filterScore === 'fail') {
      result = result.filter(r => r.validation_score !== undefined && r.validation_passed === false)
    } else if (filterScore === 'not_validated') {
      result = result.filter(r => r.validation_score === undefined)
    }

    // Sort
    result.sort((a, b) => {
      let aVal, bVal
      if (sortBy === 'id') {
        aVal = a.req_id || ''
        bVal = b.req_id || ''
      } else if (sortBy === 'score') {
        aVal = a.validation_score || 0
        bVal = b.validation_score || 0
      } else if (sortBy === 'tag') {
        aVal = a.tag || ''
        bVal = b.tag || ''
      }

      if (sortOrder === 'asc') {
        return aVal > bVal ? 1 : -1
      } else {
        return aVal < bVal ? 1 : -1
      }
    })

    return result
  }, [requirements, filterTag, filterScore, sortBy, sortOrder])

  // Memoize sort handler
  const handleSort = useCallback((column) => {
    if (sortBy === column) {
      setSortOrder(prev => prev === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(column)
      setSortOrder('asc')
    }
  }, [sortBy])

  const getScoreColor = (score) => {
    if (score === undefined) return 'gray'
    if (score >= 0.7) return 'var(--ok)'
    if (score >= 0.5) return 'var(--warn)'
    return 'var(--err)'
  }

  const getScoreBadge = (score, passed) => {
    if (score === undefined) return { text: 'N/A', color: 'gray' }
    const percentage = Math.round(score * 100)
    return {
      text: `${percentage}%`,
      color: getScoreColor(score),
      icon: passed ? '✓' : '✗'
    }
  }

  // Memoize helper functions
  const getViolatedCriteria = useCallback((req) => {
    if (!req.evaluation || !Array.isArray(req.evaluation)) {
      return []
    }
    return req.evaluation
      .filter(e => {
        const valid = e.isValid ?? e.passed ?? true
        return valid === false
      })
      .map(e => ({
        criterion: e.criterion,
        score: e.score ?? 0,
        reason: e.reason || e.feedback || 'No details available'
      }))
  }, [])

  // Virtualized row renderer
  const VirtualizedRow = useCallback(({ index, style }) => {
    const req = filteredReqs[index]
    const badge = getScoreBadge(req.validation_score, req.validation_passed)
    const evidenceCount = req.evidence_refs?.length || 0
    const violatedCriteria = getViolatedCriteria(req)

    return (
      <div
        style={style}
        className={`virtual-row clickable-row ${req.is_split_child ? 'split-child-row' : ''} ${req.split_occurred ? 'split-parent-row' : ''}`}
        onClick={() => onRequirementClick?.(req.req_id)}
      >
        <div className="virtual-cell req-id">
          {req.is_split_child && <span className="child-indent">↳ </span>}
          {req.req_id}
          {req.split_occurred && <span className="split-badge" title="This requirement was split into atomic parts">📋</span>}
        </div>
        <div className="virtual-cell req-title">{req.title}</div>
        <div className="virtual-cell">
          <span className="tag-chip">{req.tag || 'untagged'}</span>
        </div>
        <div className="virtual-cell">
          <span className="score-badge" style={{ backgroundColor: badge.color }}>
            {badge.icon} {badge.text}
          </span>
        </div>
        <div className="virtual-cell evidence-count">
          {evidenceCount > 0 ? `${evidenceCount} ref${evidenceCount > 1 ? 's' : ''}` : '-'}
        </div>
        <div className="virtual-cell violated-criteria-cell">
          {req.validation_score === undefined ? (
            <span className="not-validated">⏳ Not Validated</span>
          ) : violatedCriteria.length === 0 ? (
            <span className="no-violations">✓ All Pass</span>
          ) : (
            <div className="violated-list">
              {violatedCriteria.slice(0, 2).map((v, idx) => (
                <span key={idx} className="criteria-chip" title={v.reason}>
                  {v.criterion}
                </span>
              ))}
              {violatedCriteria.length > 2 && (
                <span className="criteria-chip more">+{violatedCriteria.length - 2}</span>
              )}
            </div>
          )}
        </div>
        <div className="virtual-cell actions-cell">
          {onEnhanceRequirement && (
            <button
              className="btn-enhance-row"
              onClick={(e) => {
                e.stopPropagation()
                onEnhanceRequirement(req)
              }}
              title="Enhance with SocietyOfMind"
            >
              🧠
            </button>
          )}
        </div>
      </div>
    )
  }, [filteredReqs, onRequirementClick, onEnhanceRequirement, getViolatedCriteria])

  // Use virtualization for large lists (>50 items)
  const useVirtualization = filteredReqs.length > 50

  return (
    <div className="requirements-table-container">
      {/* Filters */}
      <div className="table-filters">
        <div className="filter-group">
          <label>Tag:</label>
          <select value={filterTag} onChange={(e) => setFilterTag(e.target.value)}>
            <option value="all">All Tags</option>
            {uniqueTags.map(tag => (
              <option key={tag} value={tag}>{tag}</option>
            ))}
          </select>
        </div>

        <div className="filter-group">
          <label>Score:</label>
          <select value={filterScore} onChange={(e) => setFilterScore(e.target.value)}>
            <option value="all">All Scores</option>
            <option value="pass">Pass (≥70%)</option>
            <option value="fail">Fail (&lt;70%)</option>
            <option value="not_validated">Not Validated</option>
          </select>
        </div>

        <div className="filter-stats">
          Showing {filteredReqs.length} of {requirements.length} requirements
          {useVirtualization && <span className="virtualized-badge"> (virtualized)</span>}
        </div>
      </div>

      {/* Virtualized Table Header */}
      <div className="table-wrapper">
        <div className="virtual-header">
          <div className="virtual-header-cell sortable" onClick={() => handleSort('id')}>
            ID {sortBy === 'id' && (sortOrder === 'asc' ? '↑' : '↓')}
          </div>
          <div className="virtual-header-cell">Requirement</div>
          <div className="virtual-header-cell sortable" onClick={() => handleSort('tag')}>
            Tag {sortBy === 'tag' && (sortOrder === 'asc' ? '↑' : '↓')}
          </div>
          <div className="virtual-header-cell sortable" onClick={() => handleSort('score')}>
            Score {sortBy === 'score' && (sortOrder === 'asc' ? '↑' : '↓')}
          </div>
          <div className="virtual-header-cell">Evidence</div>
          <div className="virtual-header-cell">Violated Criteria</div>
          <div className="virtual-header-cell">Actions</div>
        </div>

        {filteredReqs.length === 0 ? (
          <div className="no-data">
            No requirements found. Start mining to extract requirements.
          </div>
        ) : useVirtualization ? (
          /* Virtualized list for large datasets */
          <List
            height={500}
            itemCount={filteredReqs.length}
            itemSize={ROW_HEIGHT}
            width="100%"
            className="virtual-list"
          >
            {VirtualizedRow}
          </List>
        ) : (
          /* Standard rendering for small datasets */
          <div className="virtual-body">
            {filteredReqs.map((req, index) => (
              <VirtualizedRow key={req.req_id} index={index} style={{}} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
})

export default RequirementsTable
