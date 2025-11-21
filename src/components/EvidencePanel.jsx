export default function EvidencePanel({ references }) {
  if (!references || references.length === 0) {
    return <div className="evidence-empty">Keine Evidence References verfügbar</div>
  }

  return (
    <div className="evidence-panel">
      <div className="evidence-list">
        {references.map((ref, index) => (
          <div
            key={index}
            className={`evidence-item ${ref.is_neighbor ? 'neighbor' : ''}`}
          >
            <div className="evidence-header">
              <span className="evidence-badge">
                {ref.is_neighbor ? '±1 Context' : 'Direct'}
              </span>
              {ref.source_file && (
                <span className="evidence-file">📄 {ref.source_file}</span>
              )}
            </div>

            <div className="evidence-details">
              {ref.sha1 && (
                <div className="evidence-row">
                  <span className="evidence-label">SHA1:</span>
                  <code className="evidence-value sha1">{ref.sha1}</code>
                </div>
              )}

              {ref.chunk_index !== null && ref.chunk_index !== undefined && (
                <div className="evidence-row">
                  <span className="evidence-label">Chunk Index:</span>
                  <span className="evidence-value">{ref.chunk_index}</span>
                </div>
              )}

              {ref.evidence_metadata && Object.keys(ref.evidence_metadata).length > 0 && (
                <div className="evidence-row">
                  <span className="evidence-label">Metadata:</span>
                  <pre className="evidence-value metadata">
                    {JSON.stringify(ref.evidence_metadata, null, 2)}
                  </pre>
                </div>
              )}
            </div>

            {ref.is_neighbor && (
              <div className="evidence-note">
                This chunk provides contextual evidence (±1 neighbor)
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="evidence-chain-summary">
        <strong>Evidence Chain:</strong> {references.length} reference{references.length !== 1 ? 's' : ''}
        ({references.filter(r => r.is_neighbor).length} neighbor context)
      </div>
    </div>
  )
}
