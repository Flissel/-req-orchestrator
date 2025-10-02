export default function Requirements({ requirements }) {
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
        {requirements.map((req, idx) => (
          <div key={req.req_id || idx} className="requirement-card">
            <div className="req-id">{req.req_id || `REQ-${idx + 1}`}</div>
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
        ))}
      </div>
    </div>
  )
}