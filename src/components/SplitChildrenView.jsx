export default function SplitChildrenView({ children, parentId, onNavigate }) {
  if (!children || children.length === 0) {
    return <div className="splits-empty">No child requirements (requirement was not split)</div>
  }

  return (
    <div className="split-children-view">
      <div className="split-info">
        <span className="split-count">{children.length} child requirement{children.length !== 1 ? 's' : ''}</span>
        <span className="split-note">AtomicityAgent split this requirement into atomic parts</span>
      </div>

      <div className="split-tree">
        {children.map((childId, index) => (
          <div key={childId} className="split-node">
            <div className="split-connector">
              <div className="split-line-vertical" />
              <div className="split-line-horizontal" />
            </div>

            <div
              className="split-card"
              onClick={() => onNavigate && onNavigate(childId)}
              style={{ cursor: onNavigate ? 'pointer' : 'default' }}
            >
              <div className="split-header">
                <span className="split-index">#{index + 1}</span>
                <code className="split-id">{childId}</code>
              </div>

              {onNavigate && (
                <div className="split-action">
                  Click to view child manifest →
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="split-explanation">
        <strong>Why split?</strong> The original requirement did not meet the atomicity criterion
        (score &lt; 0.7) and was automatically decomposed into focused, testable requirements.
      </div>
    </div>
  )
}
