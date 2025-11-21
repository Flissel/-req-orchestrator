import { useState, useEffect } from 'react'
import './ManifestViewer.css'
import TimelineView from './TimelineView'
import EvidencePanel from './EvidencePanel'
import SplitChildrenView from './SplitChildrenView'

const API_BASE = ''

export default function ManifestViewer({ requirementId, onClose, onNavigate }) {
  const [manifest, setManifest] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!requirementId) {
      setLoading(false)
      return
    }

    const fetchManifest = async () => {
      try {
        setLoading(true)
        setError(null)

        const response = await fetch(`${API_BASE}/api/v1/manifest/${requirementId}`)

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`)
        }

        const data = await response.json()
        setManifest(data)
      } catch (err) {
        console.error('Failed to fetch manifest:', err)
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }

    fetchManifest()
  }, [requirementId])

  if (!requirementId) {
    return (
      <div className="manifest-viewer empty">
        <div className="manifest-empty-state">
          <div className="empty-icon">📄</div>
          <h3>No Requirement Selected</h3>
          <p>Click on a requirement ID to view its lifecycle manifest</p>
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="manifest-viewer loading">
        <div className="manifest-loading-state">
          <div className="spinner" />
          <p>Loading manifest...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="manifest-viewer error">
        <div className="manifest-error-state">
          <div className="error-icon">❌</div>
          <h3>Failed to Load Manifest</h3>
          <p>{error}</p>
          {onClose && (
            <button className="btn-close" onClick={onClose}>Close</button>
          )}
        </div>
      </div>
    )
  }

  if (!manifest) {
    return (
      <div className="manifest-viewer empty">
        <div className="manifest-empty-state">
          <div className="empty-icon">🔍</div>
          <h3>Manifest Not Found</h3>
          <p>No manifest data available for requirement: {requirementId}</p>
          {onClose && (
            <button className="btn-close" onClick={onClose}>Close</button>
          )}
        </div>
      </div>
    )
  }

  const getSourceTypeIcon = (sourceType) => {
    const icons = {
      upload: '📤',
      manual: '✍️',
      chunk_miner: '⛏️',
      api: '🔌',
      atomic_split: '✂️'
    }
    return icons[sourceType] || '📄'
  }

  const getStageIcon = (stage) => {
    const icons = {
      input: '📥',
      mining: '⛏️',
      evaluation: '📊',
      atomicity: '🔬',
      suggestion: '💡',
      rewrite: '✏️',
      validation: '✅',
      completed: '🏁',
      failed: '❌'
    }
    return icons[stage] || '🔄'
  }

  return (
    <div className="manifest-viewer">
      <div className="manifest-header">
        <div className="manifest-title">
          <h2>📄 Requirement Manifest</h2>
          {onClose && (
            <button className="btn-close-x" onClick={onClose} title="Close">×</button>
          )}
        </div>
        <code className="manifest-id">{manifest.requirement_id}</code>
      </div>

      <div className="manifest-grid">
        {/* Metadata Card */}
        <div className="manifest-card metadata-card">
          <h3>ℹ️ Metadata</h3>
          <div className="metadata-content">
            <div className="metadata-row">
              <span className="label">Source Type:</span>
              <span className="value">
                <span className="source-icon">{getSourceTypeIcon(manifest.source_type)}</span>
                {manifest.source_type}
              </span>
            </div>

            {manifest.source_file && (
              <div className="metadata-row">
                <span className="label">Source File:</span>
                <span className="value file">{manifest.source_file}</span>
              </div>
            )}

            {manifest.source_file_sha1 && (
              <div className="metadata-row">
                <span className="label">File SHA1:</span>
                <code className="value sha1">{manifest.source_file_sha1}</code>
              </div>
            )}

            {manifest.chunk_index !== null && manifest.chunk_index !== undefined && (
              <div className="metadata-row">
                <span className="label">Chunk Index:</span>
                <span className="value">{manifest.chunk_index}</span>
              </div>
            )}

            {manifest.current_stage && (
              <div className="metadata-row">
                <span className="label">Current Stage:</span>
                <span className="stage-badge">
                  <span className="stage-icon">{getStageIcon(manifest.current_stage)}</span>
                  {manifest.current_stage}
                </span>
              </div>
            )}

            {manifest.parent_id && (
              <div className="metadata-row">
                <span className="label">Parent ID:</span>
                <code
                  className="value parent-link"
                  onClick={() => onNavigate && onNavigate(manifest.parent_id)}
                  style={{ cursor: onNavigate ? 'pointer' : 'default' }}
                >
                  {manifest.parent_id}
                </code>
              </div>
            )}

            <div className="metadata-row">
              <span className="label">Created:</span>
              <span className="value timestamp">
                {new Date(manifest.created_at).toLocaleString('de-DE')}
              </span>
            </div>

            <div className="metadata-row">
              <span className="label">Updated:</span>
              <span className="value timestamp">
                {new Date(manifest.updated_at).toLocaleString('de-DE')}
              </span>
            </div>

            <div className="metadata-row">
              <span className="label">Checksum:</span>
              <code className="value checksum">{manifest.requirement_checksum}</code>
            </div>
          </div>
        </div>

        {/* Text Comparison Card */}
        <div className="manifest-card text-card">
          <h3>📝 Text Evolution</h3>
          <div className="text-comparison">
            <div className="text-section">
              <h4>Original Text</h4>
              <div className="text-content original">{manifest.original_text}</div>
            </div>

            {manifest.original_text !== manifest.current_text && (
              <>
                <div className="text-divider">→</div>
                <div className="text-section">
                  <h4>Current Text</h4>
                  <div className="text-content current">{manifest.current_text}</div>
                </div>
              </>
            )}

            {manifest.original_text === manifest.current_text && (
              <div className="text-note">✓ Text unchanged through pipeline</div>
            )}
          </div>
        </div>

        {/* Timeline Card */}
        <div className="manifest-card timeline-card">
          <h3>⏱️ Processing Timeline</h3>
          {manifest.processing_stages && manifest.processing_stages.length > 0 ? (
            <TimelineView stages={manifest.processing_stages} />
          ) : (
            <div className="timeline-empty">No processing stages recorded</div>
          )}
        </div>

        {/* Evidence Card */}
        {manifest.evidence_refs && manifest.evidence_refs.length > 0 && (
          <div className="manifest-card evidence-card">
            <h3>🔍 Evidence Chain</h3>
            <EvidencePanel references={manifest.evidence_refs} />
          </div>
        )}

        {/* Split Children Card */}
        {manifest.split_children && manifest.split_children.length > 0 && (
          <div className="manifest-card splits-card">
            <h3>🌳 Split Children</h3>
            <SplitChildrenView
              children={manifest.split_children}
              parentId={manifest.requirement_id}
              onNavigate={onNavigate}
            />
          </div>
        )}

        {/* Metadata JSON Card (if additional metadata exists) */}
        {manifest.metadata && Object.keys(manifest.metadata).length > 0 && (
          <div className="manifest-card json-card">
            <h3>🔧 Additional Metadata</h3>
            <pre className="json-content">
              {JSON.stringify(manifest.metadata, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  )
}
