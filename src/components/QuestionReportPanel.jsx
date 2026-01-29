import React, { useState } from 'react'
import './QuestionReportPanel.css'

/**
 * QuestionReportPanel - Displays collected questions for batch enhancement
 * 
 * Shows all requirements with their identified gaps and generated questions.
 * Users can fill in answers which are then used to enhance the requirements.
 */
const QuestionReportPanel = ({ 
  report, 
  onApplyAnswers, 
  onClose,
  isApplying = false 
}) => {
  const [answers, setAnswers] = useState(() => {
    // Initialize answers object from report items
    const initial = {}
    report?.items?.forEach(item => {
      item.questions?.forEach(q => {
        initial[q.question_id] = q.answer || ''
      })
    })
    return initial
  })

  const handleAnswerChange = (questionId, value) => {
    setAnswers(prev => ({
      ...prev,
      [questionId]: value
    }))
  }

  const handleApply = () => {
    // Merge answers back into report items
    const itemsWithAnswers = report.items.map(item => ({
      ...item,
      questions: item.questions.map(q => ({
        ...q,
        answer: answers[q.question_id] || null
      }))
    }))

    onApplyAnswers({
      session_id: report.session_id,
      items: itemsWithAnswers
    })
  }

  // Count filled answers
  const totalQuestions = report?.total_questions || 0
  const filledAnswers = Object.values(answers).filter(a => a && a.trim()).length

  if (!report || !report.items) {
    return (
      <div className="question-report-panel">
        <div className="report-error">No report data available</div>
      </div>
    )
  }

  return (
    <div className="question-report-panel">
      <div className="report-header">
        <h3>🧠 Question Collection Report</h3>
        <button className="btn-close-report" onClick={onClose}>✕</button>
      </div>

      <div className="report-summary">
        <div className="summary-stat">
          <span className="stat-label">Requirements analyzed:</span>
          <span className="stat-value">{report.total_requirements}</span>
        </div>
        <div className="summary-stat">
          <span className="stat-label">Needing input:</span>
          <span className="stat-value">{report.requirements_needing_input}</span>
        </div>
        <div className="summary-stat">
          <span className="stat-label">Questions generated:</span>
          <span className="stat-value">{report.total_questions}</span>
        </div>
        <div className="summary-stat filled">
          <span className="stat-label">Answers filled:</span>
          <span className="stat-value">{filledAnswers}/{totalQuestions}</span>
        </div>
      </div>

      <div className="report-items-container">
        {report.items.map((item, idx) => (
          <div 
            key={item.req_id} 
            className={`report-item ${item.needs_improvement ? 'needs-improvement' : 'passing'}`}
          >
            <div className="item-header">
              <span className="item-id">{item.req_id}</span>
              <span className={`item-score ${item.current_score >= 0.7 ? 'pass' : 'fail'}`}>
                {Math.round(item.current_score * 100)}%
              </span>
            </div>

            <div className="item-text">{item.original_text}</div>

            {item.purpose && (
              <div className="item-purpose">
                <span className="label">🎯 Purpose:</span> {item.purpose}
              </div>
            )}

            {item.gaps?.length > 0 && (
              <div className="item-gaps">
                <span className="label">📋 Gaps:</span>
                <ul>
                  {item.gaps.map((gap, gIdx) => (
                    <li key={gIdx}>{gap}</li>
                  ))}
                </ul>
              </div>
            )}

            {item.questions?.length > 0 ? (
              <div className="item-questions">
                <span className="label">❓ Questions:</span>
                {item.questions.map((q, qIdx) => (
                  <div key={q.question_id} className="question-item">
                    <div className="question-text">
                      <span className="q-number">Q{qIdx + 1}:</span> {q.question}
                    </div>
                    {q.gap_addressed && (
                      <div className="question-gap">
                        <span className="gap-label">Addresses:</span> {q.gap_addressed}
                      </div>
                    )}
                    {q.examples?.length > 0 && (
                      <div className="question-examples">
                        <span className="examples-label">Examples:</span>
                        {q.examples.map((ex, eIdx) => (
                          <span key={eIdx} className="example-chip">{ex}</span>
                        ))}
                      </div>
                    )}
                    <div className="answer-input">
                      <input
                        type="text"
                        placeholder="Enter your answer..."
                        value={answers[q.question_id] || ''}
                        onChange={(e) => handleAnswerChange(q.question_id, e.target.value)}
                      />
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="no-questions">
                {item.current_score >= 0.7 
                  ? '✓ No questions needed - requirement passes quality threshold'
                  : '⚠️ No questions generated'}
              </div>
            )}

            {item.error && (
              <div className="item-error">❌ Error: {item.error}</div>
            )}
          </div>
        ))}
      </div>

      <div className="report-actions">
        <button 
          className="btn-cancel" 
          onClick={onClose}
          disabled={isApplying}
        >
          Cancel
        </button>
        <button 
          className="btn-apply-answers"
          onClick={handleApply}
          disabled={isApplying || filledAnswers === 0}
        >
          {isApplying 
            ? '⏳ Applying...' 
            : `✨ Apply ${filledAnswers} Answer${filledAnswers !== 1 ? 's' : ''} & Enhance`}
        </button>
      </div>
    </div>
  )
}

export default QuestionReportPanel