import React, { useState } from 'react'
import './QuestionPanel.css'

/**
 * QuestionPanel - Displays clarifying questions for requirements needing user input
 *
 * Props:
 * - requirement: The requirement object with pending questions
 * - questions: Array of question objects [{id, criterion, question, suggested_answers, context_hint}]
 * - onAnswer: Callback when user answers a question (questionId, answer)
 * - onSkip: Callback when user skips a question (questionId)
 * - onSubmitAll: Callback when all answers are submitted
 */
const QuestionPanel = ({ requirement, questions, onAnswer, onSkip, onSubmitAll, isSubmitting }) => {
  const [answers, setAnswers] = useState({})
  const [customAnswers, setCustomAnswers] = useState({})

  if (!requirement || !questions || questions.length === 0) {
    return (
      <div className="question-panel empty-state">
        <div className="empty-icon">💬</div>
        <h4>No Questions</h4>
        <p>Select a requirement needing input to see clarifying questions.</p>
      </div>
    )
  }

  const handleSuggestionClick = (questionId, suggestion) => {
    setAnswers(prev => ({ ...prev, [questionId]: suggestion }))
    setCustomAnswers(prev => ({ ...prev, [questionId]: '' }))
  }

  const handleCustomChange = (questionId, value) => {
    setCustomAnswers(prev => ({ ...prev, [questionId]: value }))
    if (value) {
      setAnswers(prev => ({ ...prev, [questionId]: value }))
    }
  }

  const handleSkip = (questionId) => {
    if (onSkip) {
      onSkip(questionId)
    }
  }

  const handleSubmitAll = () => {
    // Collect all answered questions
    const answeredQuestions = questions
      .filter(q => answers[q.id] || answers[q.criterion])
      .map(q => ({
        question_id: q.id,
        criterion: q.criterion,
        answer: answers[q.id] || answers[q.criterion]
      }))

    if (onSubmitAll && answeredQuestions.length > 0) {
      onSubmitAll(requirement.req_id, answeredQuestions)
    }
  }

  const answeredCount = questions.filter(q => answers[q.id] || answers[q.criterion]).length
  const allAnswered = answeredCount === questions.length

  return (
    <div className="question-panel">
      {/* Header */}
      <div className="question-panel-header">
        <div className="header-info">
          <h3>Clarifying Questions</h3>
          <span className="req-id-badge">{requirement.req_id}</span>
        </div>
        <div className="progress-indicator">
          <span className="progress-text">{answeredCount}/{questions.length} answered</span>
          <div className="progress-dots">
            {questions.map((q, idx) => (
              <div
                key={idx}
                className={`progress-dot ${answers[q.id] || answers[q.criterion] ? 'filled' : ''}`}
              />
            ))}
          </div>
        </div>
      </div>

      {/* Requirement Context */}
      <div className="requirement-context">
        <div className="context-label">Current Requirement:</div>
        <div className="context-text">
          {requirement.title || requirement.text || requirement.current_text}
        </div>
      </div>

      {/* Questions List */}
      <div className="questions-list">
        {questions.map((question, index) => {
          const questionKey = question.id || question.criterion
          const currentAnswer = answers[questionKey] || ''
          const isAnswered = !!currentAnswer

          return (
            <div key={questionKey} className={`question-item ${isAnswered ? 'answered' : ''}`}>
              <div className="question-header">
                <span className="question-number">Q{index + 1}</span>
                <span className="criterion-badge">{question.criterion}</span>
                {isAnswered && <span className="answered-check">✓</span>}
              </div>

              <div className="question-text">{question.question}</div>

              {question.context_hint && (
                <div className="context-hint">
                  <span className="hint-icon">💡</span>
                  {question.context_hint}
                </div>
              )}

              {/* Suggested Answers */}
              {question.suggested_answers && question.suggested_answers.length > 0 && (
                <div className="suggested-answers">
                  {question.suggested_answers.map((suggestion, sIdx) => (
                    <button
                      key={sIdx}
                      className={`suggestion-chip ${currentAnswer === suggestion ? 'selected' : ''}`}
                      onClick={() => handleSuggestionClick(questionKey, suggestion)}
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              )}

              {/* Custom Answer Input */}
              <div className="custom-answer-section">
                <input
                  type="text"
                  className="custom-answer-input"
                  placeholder="Or type a custom answer..."
                  value={customAnswers[questionKey] || ''}
                  onChange={(e) => handleCustomChange(questionKey, e.target.value)}
                />
              </div>

              {/* Question Actions */}
              <div className="question-actions">
                <button
                  className="btn-skip"
                  onClick={() => handleSkip(question.id)}
                  disabled={isSubmitting}
                >
                  Skip
                </button>
              </div>
            </div>
          )
        })}
      </div>

      {/* Submit Section */}
      <div className="submit-section">
        <div className="submit-info">
          {!allAnswered && (
            <span className="submit-hint">
              Answer all questions or skip to continue
            </span>
          )}
        </div>
        <button
          className={`btn-submit-answers ${allAnswered ? 'ready' : ''}`}
          onClick={handleSubmitAll}
          disabled={answeredCount === 0 || isSubmitting}
        >
          {isSubmitting ? (
            <>
              <span className="spinner"></span>
              Re-validating...
            </>
          ) : (
            `Submit ${answeredCount} Answer${answeredCount !== 1 ? 's' : ''} & Re-validate`
          )}
        </button>
      </div>
    </div>
  )
}

export default QuestionPanel
