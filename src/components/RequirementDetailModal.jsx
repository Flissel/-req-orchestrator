import { useState, useEffect } from 'react'
import CriteriaGrid from './CriteriaGrid'
import RequirementDiffView from './RequirementDiffView'

const AVAILABLE_TAGS = [
  'Functional', 'Non-Functional', 'Security', 'Performance',
  'Usability', 'Reliability', 'Scalability', 'Data', 'Integration',
  'UI/UX', 'Infrastructure', 'Compliance', 'General'
]

export default function RequirementDetailModal({ requirement, onClose, onSave, onValidate }) {
  const [activeTab, setActiveTab] = useState('overview')
  const [editedText, setEditedText] = useState('')
  const [editedTag, setEditedTag] = useState('')
  const [isEditing, setIsEditing] = useState(false)
  const [hasChanges, setHasChanges] = useState(false)

  useEffect(() => {
    if (requirement) {
      setEditedText(requirement.title || requirement.text || '')
      setEditedTag(requirement.tag || 'General')
      setIsEditing(false)
      setHasChanges(false)
    }
  }, [requirement])

  if (!requirement) return null

  const score = requirement.validation_score
  const scorePercent = score !== undefined ? Math.round(score * 100) : null
  const passed = requirement.validation_passed || (score !== undefined && score >= 0.7)

  const handleTextChange = (e) => {
    setEditedText(e.target.value)
    setHasChanges(true)
  }

  const handleTagChange = (e) => {
    setEditedTag(e.target.value)
    setHasChanges(true)
  }

  const handleSave = () => {
    if (onSave && hasChanges) {
      onSave(requirement.req_id, {
        title: editedText,
        tag: editedTag
      })
      setHasChanges(false)
      setIsEditing(false)
    }
  }

  const handleCancel = () => {
    setEditedText(requirement.title || requirement.text || '')
    setEditedTag(requirement.tag || 'General')
    setHasChanges(false)
    setIsEditing(false)
  }

  const getScoreColor = () => {
    if (scorePercent === null) return 'var(--muted)'
    if (scorePercent >= 80) return 'var(--ok)'
    if (scorePercent >= 70) return '#ff9800'
    return 'var(--err)'
  }

  const tabs = [
    { id: 'overview', label: 'Overview' },
    { id: 'criteria', label: 'Criteria' },
    { id: 'changes', label: 'Changes', disabled: !requirement.corrected_text && !requirement.fix_history },
    { id: 'evidence', label: 'Evidence', disabled: !requirement.evidence_refs?.length }
  ]

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(0, 0, 0, 0.7)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000,
      padding: '20px'
    }}>
      <div style={{
        background: 'var(--bg)',
        borderRadius: '8px',
        maxWidth: '900px',
        width: '100%',
        maxHeight: '90vh',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '0 4px 20px rgba(0, 0, 0, 0.3)'
      }}>
        {/* Header */}
        <div style={{
          padding: '20px',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div>
              <h2 style={{ margin: 0, fontSize: '18px' }}>{requirement.req_id}</h2>
              <div style={{ fontSize: '13px', color: 'var(--muted)', marginTop: '4px' }}>
                {editedTag}
              </div>
            </div>
            {/* Score Badge */}
            {scorePercent !== null && (
              <div style={{
                padding: '6px 12px',
                borderRadius: '20px',
                background: passed ? 'rgba(76, 175, 80, 0.15)' : 'rgba(244, 67, 54, 0.15)',
                color: getScoreColor(),
                fontWeight: '600',
                fontSize: '14px',
                display: 'flex',
                alignItems: 'center',
                gap: '6px'
              }}>
                {passed ? '✓' : '✗'} {scorePercent}%
              </div>
            )}
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              fontSize: '24px',
              cursor: 'pointer',
              color: 'var(--text)',
              padding: '0 8px'
            }}
          >
            ×
          </button>
        </div>

        {/* Tab Navigation */}
        <div style={{
          display: 'flex',
          borderBottom: '1px solid var(--border)',
          padding: '0 20px'
        }}>
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => !tab.disabled && setActiveTab(tab.id)}
              disabled={tab.disabled}
              style={{
                padding: '12px 20px',
                background: 'none',
                border: 'none',
                borderBottom: activeTab === tab.id ? '2px solid var(--primary)' : '2px solid transparent',
                color: tab.disabled ? 'var(--muted)' : activeTab === tab.id ? 'var(--primary)' : 'var(--text)',
                cursor: tab.disabled ? 'not-allowed' : 'pointer',
                fontWeight: activeTab === tab.id ? '600' : '400',
                fontSize: '14px',
                opacity: tab.disabled ? 0.5 : 1
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div style={{
          flex: 1,
          overflow: 'auto',
          padding: '20px'
        }}>
          {/* Overview Tab */}
          {activeTab === 'overview' && (
            <div>
              {/* Requirement Text */}
              <div style={{ marginBottom: '20px' }}>
                <div style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: '8px'
                }}>
                  <label style={{ fontWeight: '600', fontSize: '13px', color: 'var(--muted)' }}>
                    Requirement Text
                  </label>
                  {!isEditing && (
                    <button
                      onClick={() => setIsEditing(true)}
                      style={{
                        padding: '4px 12px',
                        borderRadius: '4px',
                        border: '1px solid var(--border)',
                        background: 'var(--bg)',
                        color: 'var(--text)',
                        cursor: 'pointer',
                        fontSize: '12px'
                      }}
                    >
                      Edit
                    </button>
                  )}
                </div>
                {isEditing ? (
                  <textarea
                    value={editedText}
                    onChange={handleTextChange}
                    style={{
                      width: '100%',
                      minHeight: '120px',
                      padding: '12px',
                      borderRadius: '6px',
                      border: '1px solid var(--primary)',
                      background: 'var(--bg-secondary)',
                      color: 'var(--text)',
                      fontSize: '14px',
                      fontFamily: 'inherit',
                      resize: 'vertical'
                    }}
                  />
                ) : (
                  <div style={{
                    padding: '15px',
                    background: 'var(--bg-secondary)',
                    borderRadius: '6px',
                    border: '1px solid var(--border)',
                    fontSize: '14px',
                    lineHeight: '1.6'
                  }}>
                    {editedText}
                  </div>
                )}
              </div>

              {/* Tag Selection */}
              <div style={{ marginBottom: '20px' }}>
                <label style={{
                  display: 'block',
                  fontWeight: '600',
                  fontSize: '13px',
                  color: 'var(--muted)',
                  marginBottom: '8px'
                }}>
                  Category Tag
                </label>
                {isEditing ? (
                  <select
                    value={editedTag}
                    onChange={handleTagChange}
                    style={{
                      padding: '10px 12px',
                      borderRadius: '6px',
                      border: '1px solid var(--primary)',
                      background: 'var(--bg-secondary)',
                      color: 'var(--text)',
                      fontSize: '14px',
                      minWidth: '200px'
                    }}
                  >
                    {AVAILABLE_TAGS.map(tag => (
                      <option key={tag} value={tag}>{tag}</option>
                    ))}
                  </select>
                ) : (
                  <span style={{
                    display: 'inline-block',
                    padding: '6px 12px',
                    background: 'var(--bg-secondary)',
                    borderRadius: '4px',
                    fontSize: '14px'
                  }}>
                    {editedTag}
                  </span>
                )}
              </div>

              {/* Quick Stats */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
                gap: '12px'
              }}>
                <div style={{
                  padding: '15px',
                  background: 'var(--bg-secondary)',
                  borderRadius: '6px',
                  border: '1px solid var(--border)'
                }}>
                  <div style={{ fontSize: '12px', color: 'var(--muted)', marginBottom: '4px' }}>
                    Validation Score
                  </div>
                  <div style={{
                    fontSize: '24px',
                    fontWeight: '600',
                    color: getScoreColor()
                  }}>
                    {scorePercent !== null ? `${scorePercent}%` : 'N/A'}
                  </div>
                </div>

                <div style={{
                  padding: '15px',
                  background: 'var(--bg-secondary)',
                  borderRadius: '6px',
                  border: '1px solid var(--border)'
                }}>
                  <div style={{ fontSize: '12px', color: 'var(--muted)', marginBottom: '4px' }}>
                    Fixes Applied
                  </div>
                  <div style={{ fontSize: '24px', fontWeight: '600' }}>
                    {requirement.validation_fixes ?? 0}
                  </div>
                </div>

                <div style={{
                  padding: '15px',
                  background: 'var(--bg-secondary)',
                  borderRadius: '6px',
                  border: '1px solid var(--border)'
                }}>
                  <div style={{ fontSize: '12px', color: 'var(--muted)', marginBottom: '4px' }}>
                    Evidence Sources
                  </div>
                  <div style={{ fontSize: '24px', fontWeight: '600' }}>
                    {requirement.evidence_refs?.length ?? 0}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Criteria Tab */}
          {activeTab === 'criteria' && (
            <div>
              {requirement.evaluation && requirement.evaluation.length > 0 ? (
                <CriteriaGrid requirement={requirement} />
              ) : (
                <div style={{
                  textAlign: 'center',
                  padding: '40px',
                  color: 'var(--muted)'
                }}>
                  <div style={{ fontSize: '32px', marginBottom: '10px' }}>📋</div>
                  <div>No validation data available.</div>
                  <div style={{ fontSize: '13px', marginTop: '8px' }}>
                    Run validation to see criteria scores.
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Changes Tab */}
          {activeTab === 'changes' && (
            <div>
              {requirement.original_text && requirement.corrected_text ? (
                <RequirementDiffView
                  oldText={requirement.original_text}
                  newText={requirement.corrected_text}
                  criterion="Overall"
                  scoreBefore={0}
                  scoreAfter={requirement.validation_score || 0}
                  compact={false}
                />
              ) : requirement.fix_history && requirement.fix_history.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {requirement.fix_history.map((fix, idx) => (
                    <RequirementDiffView
                      key={idx}
                      oldText={fix.before}
                      newText={fix.after}
                      criterion={fix.criterion}
                      scoreBefore={fix.score_before}
                      scoreAfter={fix.score_after}
                      suggestion={fix.suggestion}
                      compact={false}
                    />
                  ))}
                </div>
              ) : (
                <div style={{
                  textAlign: 'center',
                  padding: '40px',
                  color: 'var(--muted)'
                }}>
                  <div style={{ fontSize: '32px', marginBottom: '10px' }}>📝</div>
                  <div>No changes recorded.</div>
                </div>
              )}
            </div>
          )}

          {/* Evidence Tab */}
          {activeTab === 'evidence' && (
            <div>
              {requirement.evidence_refs && requirement.evidence_refs.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {requirement.evidence_refs.map((ref, idx) => (
                    <div
                      key={idx}
                      style={{
                        padding: '15px',
                        background: 'var(--bg-secondary)',
                        borderRadius: '6px',
                        border: '1px solid var(--border)'
                      }}
                    >
                      <div style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        marginBottom: '8px'
                      }}>
                        <span style={{ fontWeight: '600', fontSize: '14px' }}>
                          {ref.sourceFile}
                        </span>
                        <span style={{
                          fontSize: '12px',
                          color: 'var(--muted)',
                          fontFamily: 'monospace'
                        }}>
                          Chunk #{ref.chunkIndex}
                        </span>
                      </div>
                      {ref.sha1 && (
                        <div style={{
                          fontSize: '11px',
                          color: 'var(--muted)',
                          fontFamily: 'monospace'
                        }}>
                          SHA1: {ref.sha1.substring(0, 12)}...
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{
                  textAlign: 'center',
                  padding: '40px',
                  color: 'var(--muted)'
                }}>
                  <div style={{ fontSize: '32px', marginBottom: '10px' }}>📎</div>
                  <div>No evidence sources linked.</div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{
          padding: '15px 20px',
          borderTop: '1px solid var(--border)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: '10px'
        }}>
          <div>
            {onValidate && (
              <button
                onClick={() => onValidate(requirement)}
                style={{
                  padding: '8px 16px',
                  borderRadius: '6px',
                  border: '1px solid var(--primary)',
                  background: 'var(--bg)',
                  color: 'var(--primary)',
                  cursor: 'pointer',
                  fontWeight: '500'
                }}
              >
                Validate
              </button>
            )}
          </div>

          <div style={{ display: 'flex', gap: '10px' }}>
            {isEditing && (
              <>
                <button
                  onClick={handleCancel}
                  style={{
                    padding: '8px 16px',
                    borderRadius: '6px',
                    border: '1px solid var(--border)',
                    background: 'var(--bg)',
                    color: 'var(--text)',
                    cursor: 'pointer',
                    fontWeight: '500'
                  }}
                >
                  Cancel
                </button>
                <button
                  onClick={handleSave}
                  disabled={!hasChanges}
                  style={{
                    padding: '8px 16px',
                    borderRadius: '6px',
                    border: 'none',
                    background: hasChanges ? 'var(--primary)' : 'var(--muted)',
                    color: 'white',
                    cursor: hasChanges ? 'pointer' : 'not-allowed',
                    fontWeight: '500'
                  }}
                >
                  Save Changes
                </button>
              </>
            )}
            {!isEditing && (
              <button
                onClick={onClose}
                style={{
                  padding: '8px 16px',
                  borderRadius: '6px',
                  border: 'none',
                  background: 'var(--primary)',
                  color: 'white',
                  cursor: 'pointer',
                  fontWeight: '500'
                }}
              >
                Close
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
