import { useState } from 'react'

export default function TimelineView({ stages }) {
  const [expandedStage, setExpandedStage] = useState(null)

  if (!stages || stages.length === 0) {
    return <div className="timeline-empty">Keine Stages verfügbar</div>
  }

  const getStatusColor = (status) => {
    const colors = {
      completed: 'var(--ok)',
      in_progress: 'var(--warn)',
      failed: 'var(--err)',
      pending: 'var(--muted)'
    }
    return colors[status] || 'var(--muted)'
  }

  const formatDuration = (startedAt, completedAt) => {
    if (!completedAt) return 'In Progress'
    const start = new Date(startedAt)
    const end = new Date(completedAt)
    const durationMs = end - start
    if (durationMs < 1000) return `${durationMs}ms`
    if (durationMs < 60000) return `${(durationMs / 1000).toFixed(1)}s`
    return `${(durationMs / 60000).toFixed(1)}m`
  }

  const formatTimestamp = (timestamp) => {
    if (!timestamp) return 'N/A'
    return new Date(timestamp).toLocaleString('de-DE', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  }

  const toggleExpand = (stageId) => {
    setExpandedStage(expandedStage === stageId ? null : stageId)
  }

  return (
    <div className="timeline">
      {stages.map((stage, index) => {
        const isExpanded = expandedStage === stage.id
        const isLast = index === stages.length - 1

        return (
          <div key={stage.id || index} className="timeline-item">
            <div className="timeline-connector-wrapper">
              <div
                className="timeline-dot"
                style={{ backgroundColor: getStatusColor(stage.status) }}
              />
              {!isLast && <div className="timeline-line" />}
            </div>

            <div className="timeline-content">
              <div
                className="timeline-header"
                onClick={() => toggleExpand(stage.id)}
                style={{ cursor: 'pointer' }}
              >
                <div className="timeline-header-left">
                  <span className="stage-name">{stage.stage_name}</span>
                  <span
                    className="stage-status-badge"
                    style={{
                      backgroundColor: getStatusColor(stage.status),
                      color: 'white',
                      padding: '2px 8px',
                      borderRadius: '4px',
                      fontSize: '11px',
                      marginLeft: '8px'
                    }}
                  >
                    {stage.status}
                  </span>
                </div>
                <div className="timeline-header-right">
                  <span className="stage-duration">
                    {formatDuration(stage.started_at, stage.completed_at)}
                  </span>
                  <span className="expand-icon" style={{ marginLeft: '8px' }}>
                    {isExpanded ? '▼' : '▶'}
                  </span>
                </div>
              </div>

              {isExpanded && (
                <div className="timeline-details">
                  <div className="detail-row">
                    <span className="detail-label">Started:</span>
                    <span className="detail-value">{formatTimestamp(stage.started_at)}</span>
                  </div>
                  {stage.completed_at && (
                    <div className="detail-row">
                      <span className="detail-label">Completed:</span>
                      <span className="detail-value">{formatTimestamp(stage.completed_at)}</span>
                    </div>
                  )}

                  {stage.score !== null && stage.score !== undefined && (
                    <div className="detail-row">
                      <span className="detail-label">Score:</span>
                      <span className="detail-value">{stage.score.toFixed(2)}</span>
                    </div>
                  )}

                  {stage.verdict && (
                    <div className="detail-row">
                      <span className="detail-label">Verdict:</span>
                      <span className="detail-value verdict">{stage.verdict}</span>
                    </div>
                  )}

                  {stage.atomic_score !== null && stage.atomic_score !== undefined && (
                    <div className="detail-row">
                      <span className="detail-label">Atomic Score:</span>
                      <span className="detail-value">{stage.atomic_score.toFixed(2)}</span>
                    </div>
                  )}

                  {stage.was_split !== null && stage.was_split !== undefined && (
                    <div className="detail-row">
                      <span className="detail-label">Was Split:</span>
                      <span className="detail-value">{stage.was_split ? 'Yes' : 'No'}</span>
                    </div>
                  )}

                  {stage.model_used && (
                    <div className="detail-row">
                      <span className="detail-label">Model:</span>
                      <span className="detail-value model">{stage.model_used}</span>
                    </div>
                  )}

                  {stage.latency_ms !== null && stage.latency_ms !== undefined && (
                    <div className="detail-row">
                      <span className="detail-label">Latency:</span>
                      <span className="detail-value">{stage.latency_ms}ms</span>
                    </div>
                  )}

                  {stage.token_usage && Object.keys(stage.token_usage).length > 0 && (
                    <div className="detail-row">
                      <span className="detail-label">Tokens:</span>
                      <span className="detail-value">
                        {stage.token_usage.total_tokens ||
                         (stage.token_usage.prompt_tokens || 0) + (stage.token_usage.completion_tokens || 0)} total
                        {stage.token_usage.prompt_tokens && ` (${stage.token_usage.prompt_tokens} prompt, ${stage.token_usage.completion_tokens} completion)`}
                      </span>
                    </div>
                  )}

                  {stage.error_message && (
                    <div className="detail-row error">
                      <span className="detail-label">Error:</span>
                      <span className="detail-value">{stage.error_message}</span>
                    </div>
                  )}

                  {stage.stage_metadata && Object.keys(stage.stage_metadata).length > 0 && (
                    <div className="detail-row">
                      <span className="detail-label">Metadata:</span>
                      <pre className="detail-value metadata">
                        {JSON.stringify(stage.stage_metadata, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
