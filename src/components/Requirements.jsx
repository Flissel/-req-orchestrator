export default function Requirements({
  requirements,
  onRequirementClick,
  selectedRequirementId,
  onValidateRequirement
}) {
  if (!requirements || requirements.length === 0) {
    return (
      <div className="card">
        <h2>📋 Extrahierte Requirements</h2>
        <div style={{ padding: '20px', textAlign: 'center', color: 'var(--muted)' }}>
          Keine Requirements gefunden. Starten Sie den Mining-Prozess.
        </div>
      </div>
    )
  }

  return (
    <div className="card">
      <h2>📋 Extrahierte Requirements ({requirements.length})</h2>
      <div style={{ maxHeight: '600px', overflowY: 'auto', marginTop: '15px' }}>
        {requirements.map((req, idx) => {
          const reqId = req.req_id || `REQ-${idx + 1}`
          const isSelected = selectedRequirementId === reqId
          const hasValidation = req.validation_score !== undefined
          const wasSplit = req.split_from || req.split_occurred

          return (
            <div
              key={reqId}
              className={`requirement-card ${isSelected ? 'selected' : ''}`}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <div
                  className="req-id clickable"
                  onClick={() => onRequirementClick && onRequirementClick(reqId)}
                  title="Click to view manifest"
                  style={{
                    cursor: onRequirementClick ? 'pointer' : 'default',
                    textDecoration: onRequirementClick ? 'underline' : 'none'
                  }}
                >
                  {reqId}
                </div>
                {onValidateRequirement && (
                  <button
                    onClick={() => onValidateRequirement(req)}
                    style={{
                      padding: '4px 8px',
                      fontSize: '11px',
                      borderRadius: '4px',
                      border: '1px solid var(--primary)',
                      background: 'var(--bg)',
                      color: 'var(--primary)',
                      cursor: 'pointer',
                      fontWeight: '500'
                    }}
                    title="Validate this requirement"
                  >
                    ✓ Validate
                  </button>
                )}
              </div>

              {hasValidation && (
                <div style={{
                  fontSize: '11px',
                  padding: '4px 8px',
                  borderRadius: '4px',
                  background: req.validation_score >= 0.7 ? '#c8e6c9' : '#ffcdd2',
                  color: req.validation_score >= 0.7 ? '#2e7d32' : '#c62828',
                  marginBottom: '8px',
                  fontWeight: '500'
                }}>
                  Quality Score: {(req.validation_score * 100).toFixed(0)}%
                  {req.validation_score >= 0.7 ? ' ✓' : ' ✗'}
                </div>
              )}

              {wasSplit && (
                <div style={{
                  fontSize: '11px',
                  padding: '4px 8px',
                  borderRadius: '4px',
                  background: '#fff3e0',
                  color: '#f57c00',
                  marginBottom: '8px',
                  fontWeight: '500',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px'
                }}>
                  ⚡ Split Requirement
                  {req.split_from && (
                    <span style={{ fontSize: '10px', opacity: 0.8 }}>
                      (from {req.split_from})
                    </span>
                  )}
                </div>
              )}

              <div className="req-title">{req.title || 'Kein Titel'}</div>
              <div style={{ marginTop: '10px' }}>
                <span className="req-tag">{req.tag || 'uncategorized'}</span>
              </div>
              {req.evidence_refs && req.evidence_refs.length > 0 && (
                <div style={{ marginTop: '10px', fontSize: '12px', color: 'var(--muted)' }}>
                  <strong>Evidence:</strong> {req.evidence_refs.length} Referenz(en)
                  <div style={{ marginTop: '5px' }}>
                    {req.evidence_refs.map((ref, i) => (
                      <div key={i} style={{ fontSize: '11px', opacity: 0.8 }}>
                        {ref.sourceFile || 'unknown'}#{ref.chunkIndex || 0}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}