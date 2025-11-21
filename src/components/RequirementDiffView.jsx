import { useMemo } from 'react';
import { diffWords, diffChars } from 'diff';

/**
 * RequirementDiffView - Side-by-side comparison of requirement text changes
 *
 * Shows the before/after comparison of requirement text with highlighted changes.
 * Used within ClarificationModal to show real-time requirement updates during validation.
 *
 * Props:
 *   - oldText: Original requirement text
 *   - newText: Updated requirement text
 *   - criterion: Name of the criterion that was fixed (e.g., "clarity", "testability")
 *   - scoreBefore: Score before fix (0.0 - 1.0)
 *   - scoreAfter: Score after fix (0.0 - 1.0)
 *   - suggestion: The suggestion that was applied (optional)
 *   - compact: Use compact layout (default: false)
 */
export default function RequirementDiffView({
  oldText,
  newText,
  criterion,
  scoreBefore,
  scoreAfter,
  suggestion,
  compact = false
}) {
  // Calculate the diff using word-level comparison
  const diff = useMemo(() => {
    if (!oldText || !newText) return [];

    // Use word-level diff for better readability
    return diffWords(oldText, newText);
  }, [oldText, newText]);

  // Calculate score improvement
  const improvement = scoreAfter - scoreBefore;
  const improvementPercent = ((improvement / (1 - scoreBefore)) * 100).toFixed(1);

  // Format criterion name (e.g., "clarity" → "Clarity")
  const formattedCriterion = criterion
    ? criterion.charAt(0).toUpperCase() + criterion.slice(1).replace(/_/g, ' ')
    : 'Unknown';

  // Render diff with inline highlighting
  const renderInlineDiff = () => {
    return (
      <div className="diff-inline">
        {diff.map((part, index) => {
          const className = part.added
            ? 'diff-added'
            : part.removed
            ? 'diff-removed'
            : 'diff-unchanged';

          return (
            <span key={index} className={className}>
              {part.value}
            </span>
          );
        })}
      </div>
    );
  };

  // Render side-by-side diff
  const renderSideBySide = () => {
    return (
      <div className="diff-side-by-side">
        <div className="diff-column diff-column-old">
          <div className="diff-column-header">Original</div>
          <div className="diff-column-content">
            {diff.map((part, index) => {
              if (part.removed) {
                return (
                  <span key={index} className="diff-removed">
                    {part.value}
                  </span>
                );
              }
              if (!part.added) {
                return (
                  <span key={index} className="diff-unchanged">
                    {part.value}
                  </span>
                );
              }
              return null;
            })}
          </div>
        </div>

        <div className="diff-column diff-column-new">
          <div className="diff-column-header">Updated</div>
          <div className="diff-column-content">
            {diff.map((part, index) => {
              if (part.added) {
                return (
                  <span key={index} className="diff-added">
                    {part.value}
                  </span>
                );
              }
              if (!part.removed) {
                return (
                  <span key={index} className="diff-unchanged">
                    {part.value}
                  </span>
                );
              }
              return null;
            })}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className={`requirement-diff-view ${compact ? 'compact' : ''}`}>
      {/* Header with criterion and score info */}
      <div className="diff-header">
        <div className="diff-header-left">
          <span className="diff-criterion">{formattedCriterion}</span>
          <span className="diff-scores">
            <span className="score-before">{scoreBefore.toFixed(2)}</span>
            <span className="score-arrow">→</span>
            <span className={`score-after ${improvement > 0 ? 'improved' : 'declined'}`}>
              {scoreAfter.toFixed(2)}
            </span>
            {improvement > 0 && (
              <span className="score-improvement">
                (+{improvementPercent}%)
              </span>
            )}
          </span>
        </div>

        {!compact && improvement > 0 && (
          <div className="diff-header-right">
            <span className="diff-status-badge improved">Improved</span>
          </div>
        )}
      </div>

      {/* Suggestion (if provided) */}
      {!compact && suggestion && (
        <div className="diff-suggestion">
          <div className="diff-suggestion-label">Applied Fix:</div>
          <div className="diff-suggestion-text">{suggestion}</div>
        </div>
      )}

      {/* Diff visualization */}
      <div className="diff-content">
        {compact ? renderInlineDiff() : renderSideBySide()}
      </div>

      {/* Inline styles */}
      <style jsx>{`
        .requirement-diff-view {
          background: #f8f9fa;
          border: 1px solid #e0e0e0;
          border-radius: 6px;
          padding: 16px;
          margin: 12px 0;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }

        .requirement-diff-view.compact {
          padding: 12px;
          margin: 8px 0;
        }

        .diff-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 12px;
          padding-bottom: 12px;
          border-bottom: 1px solid #e0e0e0;
        }

        .diff-header-left {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .diff-criterion {
          font-weight: 600;
          font-size: 14px;
          color: #333;
          background: #e3f2fd;
          padding: 4px 10px;
          border-radius: 4px;
        }

        .diff-scores {
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 13px;
          font-family: 'Monaco', 'Courier New', monospace;
        }

        .score-before {
          color: #666;
        }

        .score-arrow {
          color: #999;
          font-size: 12px;
        }

        .score-after {
          font-weight: 600;
        }

        .score-after.improved {
          color: #2e7d32;
        }

        .score-after.declined {
          color: #c62828;
        }

        .score-improvement {
          color: #2e7d32;
          font-size: 11px;
          font-weight: 600;
        }

        .diff-status-badge {
          padding: 4px 10px;
          border-radius: 4px;
          font-size: 12px;
          font-weight: 600;
        }

        .diff-status-badge.improved {
          background: #c8e6c9;
          color: #2e7d32;
        }

        .diff-suggestion {
          background: #fff3e0;
          border: 1px solid #ffe0b2;
          border-radius: 4px;
          padding: 12px;
          margin-bottom: 12px;
        }

        .diff-suggestion-label {
          font-size: 12px;
          font-weight: 600;
          color: #e65100;
          margin-bottom: 6px;
        }

        .diff-suggestion-text {
          font-size: 13px;
          color: #555;
          line-height: 1.5;
        }

        .diff-content {
          background: white;
          border-radius: 4px;
          overflow: hidden;
        }

        /* Inline diff styles */
        .diff-inline {
          padding: 12px;
          line-height: 1.6;
          font-size: 14px;
          color: #333;
        }

        /* Side-by-side diff styles */
        .diff-side-by-side {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 1px;
          background: #e0e0e0;
        }

        .diff-column {
          background: white;
        }

        .diff-column-header {
          background: #f5f5f5;
          border-bottom: 1px solid #e0e0e0;
          padding: 8px 12px;
          font-size: 12px;
          font-weight: 600;
          color: #666;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .diff-column-content {
          padding: 12px;
          line-height: 1.6;
          font-size: 14px;
          color: #333;
          min-height: 80px;
          white-space: pre-wrap;
          word-break: break-word;
        }

        /* Diff highlighting */
        .diff-unchanged {
          color: #333;
        }

        .diff-added {
          background: #c8e6c9;
          color: #1b5e20;
          padding: 2px 0;
          border-radius: 2px;
        }

        .diff-removed {
          background: #ffcdd2;
          color: #b71c1c;
          padding: 2px 0;
          border-radius: 2px;
          text-decoration: line-through;
        }

        /* Responsive: Stack on small screens */
        @media (max-width: 768px) {
          .diff-side-by-side {
            grid-template-columns: 1fr;
          }

          .diff-column-old {
            border-bottom: 2px solid #e0e0e0;
          }

          .diff-header-left {
            flex-direction: column;
            align-items: flex-start;
            gap: 8px;
          }
        }
      `}</style>
    </div>
  );
}
