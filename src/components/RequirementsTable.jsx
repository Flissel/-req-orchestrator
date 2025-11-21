import React, { useState } from 'react'
import './RequirementsTable.css'

const RequirementsTable = ({ requirements, onRequirementClick, onRequirementUpdate }) => {
  const [sortBy, setSortBy] = useState('id')
  const [sortOrder, setSortOrder] = useState('asc')
  const [filterTag, setFilterTag] = useState('all')
  const [filterScore, setFilterScore] = useState('all')

  // Get unique tags
  const uniqueTags = [...new Set(requirements.map(r => r.tag || 'untagged'))]

  // Sort and filter
  let filteredReqs = [...requirements]

  // Filter by tag
  if (filterTag !== 'all') {
    filteredReqs = filteredReqs.filter(r => (r.tag || 'untagged') === filterTag)
  }

  // Filter by score
  if (filterScore === 'pass') {
    filteredReqs = filteredReqs.filter(r => r.validation_passed === true)
  } else if (filterScore === 'fail') {
    filteredReqs = filteredReqs.filter(r => r.validation_passed === false)
  }

  // Sort
  filteredReqs.sort((a, b) => {
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

  const handleSort = (column) => {
    if (sortBy === column) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(column)
      setSortOrder('asc')
    }
  }

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

  const getViolatedCriteria = (req) => {
    if (!req.evaluation || !Array.isArray(req.evaluation)) {
      return []
    }
    return req.evaluation
      .filter(e => e.isValid === false)
      .map(e => ({
        criterion: e.criterion,
        reason: e.reason || 'No details available'
      }))
  }

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
          </select>
        </div>

        <div className="filter-stats">
          Showing {filteredReqs.length} of {requirements.length} requirements
        </div>
      </div>

      {/* Table */}
      <div className="table-wrapper">
        <table className="requirements-table">
          <thead>
            <tr>
              <th onClick={() => handleSort('id')} className="sortable">
                ID {sortBy === 'id' && (sortOrder === 'asc' ? '↑' : '↓')}
              </th>
              <th>Requirement</th>
              <th onClick={() => handleSort('tag')} className="sortable">
                Tag {sortBy === 'tag' && (sortOrder === 'asc' ? '↑' : '↓')}
              </th>
              <th onClick={() => handleSort('score')} className="sortable">
                Score {sortBy === 'score' && (sortOrder === 'asc' ? '↑' : '↓')}
              </th>
              <th>Evidence</th>
              <th>Violated Criteria</th>
            </tr>
          </thead>
          <tbody>
            {filteredReqs.length === 0 ? (
              <tr>
                <td colSpan="6" className="no-data">
                  No requirements found. Start mining to extract requirements.
                </td>
              </tr>
            ) : (
              filteredReqs.map(req => {
                const badge = getScoreBadge(req.validation_score, req.validation_passed)
                const evidenceCount = req.evidence_refs?.length || 0
                const violatedCriteria = getViolatedCriteria(req)

                return (
                  <tr key={req.req_id} onClick={() => onRequirementClick?.(req.req_id)} className="clickable-row">
                    <td className="req-id">{req.req_id}</td>
                    <td className="req-title">{req.title}</td>
                    <td>
                      <span className="tag-chip">{req.tag || 'untagged'}</span>
                    </td>
                    <td>
                      <span
                        className="score-badge"
                        style={{ backgroundColor: badge.color }}
                      >
                        {badge.icon} {badge.text}
                      </span>
                    </td>
                    <td className="evidence-count">
                      {evidenceCount > 0 ? `${evidenceCount} ref${evidenceCount > 1 ? 's' : ''}` : '-'}
                    </td>
                    <td className="violated-criteria-cell">
                      {violatedCriteria.length === 0 ? (
                        <span className="no-violations">✓ All Pass</span>
                      ) : (
                        <div className="violated-list">
                          {violatedCriteria.map((v, idx) => (
                            <span
                              key={idx}
                              className="criteria-chip"
                              title={v.reason}
                            >
                              {v.criterion}
                            </span>
                          ))}
                        </div>
                      )}
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default RequirementsTable
