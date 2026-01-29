import React, { useState, useRef, useEffect } from 'react'
import './ValidationTab.css'
import ValidationRequirementCard from './ValidationRequirementCard'
import ValidationDetailPanel from './ValidationDetailPanel'
import QuestionPanel from './QuestionPanel'
import QuestionReportPanel from './QuestionReportPanel'

const ValidationTab = (props) => {
  const {
    requirements,
    onRequirementClick,
    onValidateAll,
    onValidationComplete,
    onEnhanceRequirement,
    batchValidationState,
    setBatchValidationState
  } = props;
  const [selectedReqId, setSelectedReqId] = useState(null)
  const [validatingReqId, setValidatingReqId] = useState(null)

  // Destructure batch validation state from props (lifted to AppV2)
  const {
    isValidating: isBatchValidating,
    progress: batchProgress,
    eventLog: batchEventLog,
    results: batchResults,
    status: batchStatus,
    currentReqId: currentBatchReqId,
    pendingQuestions: batchPendingQuestions,
    needsInputCount: batchNeedsInputCount
  } = batchValidationState

  // Helper functions to update lifted state
  const setIsBatchValidating = (val) => setBatchValidationState(prev => ({ ...prev, isValidating: val }))
  const setBatchProgress = (val) => setBatchValidationState(prev => ({ ...prev, progress: typeof val === 'function' ? val(prev.progress) : val }))
  const setBatchEventLog = (val) => setBatchValidationState(prev => ({ ...prev, eventLog: typeof val === 'function' ? val(prev.eventLog) : val }))
  const setBatchResults = (val) => setBatchValidationState(prev => ({ ...prev, results: typeof val === 'function' ? val(prev.results) : val }))
  const setBatchStatus = (val) => setBatchValidationState(prev => ({ ...prev, status: val }))
  const setCurrentBatchReqId = (val) => setBatchValidationState(prev => ({ ...prev, currentReqId: val }))
  const setPendingQuestions = (val) => setBatchValidationState(prev => ({ ...prev, pendingQuestions: typeof val === 'function' ? val(prev.pendingQuestions) : val }))
  const setNeedsInputCount = (val) => setBatchValidationState(prev => ({ ...prev, needsInputCount: typeof val === 'function' ? val(prev.needsInputCount) : val }))

  // Track selected requirement in needs-input section
  const [selectedNeedsInputReqId, setSelectedNeedsInputReqId] = useState(null)
  const [isSubmittingAnswer, setIsSubmittingAnswer] = useState(false)

  // NEW: Question Report state for batch enhancement
  const [questionReport, setQuestionReport] = useState(null)
  const [isCollectingQuestions, setIsCollectingQuestions] = useState(false)
  const [isApplyingAnswers, setIsApplyingAnswers] = useState(false)
  const [isAutoEnhancing, setIsAutoEnhancing] = useState(false)
  const [autoEnhanceResults, setAutoEnhanceResults] = useState(null)

  // NEW: All-in-One Mode State
  const [validationMode, setValidationMode] = useState('quick') // 'quick' | 'guided'
  const [pipelineStage, setPipelineStage] = useState('idle') // 'idle' | 'running' | 'awaiting_answers' | 'complete'
  const [pipelineEvents, setPipelineEvents] = useState([])

  const batchSessionIdRef = useRef(null)
  const batchEventSourceRef = useRef(null)
  const batchQueueRef = useRef([])
  const batchIndexRef = useRef(0)
  const eventLogRef = useRef(null)

  // Parallel validation tracking
  const MAX_PARALLEL_TREES = 5
  const activeTreesRef = useRef(new Set()) // Set of req_ids currently being validated
  const completedCountRef = useRef(0) // Total completed (successful + failed)
  const startedCountRef = useRef(0) // Total started

  // Get score for a requirement - check batch results first, then original
  const getUpdatedScore = (reqId) => {
    const batchResult = batchResults.find(r => r.req_id === reqId)
    if (batchResult) {
      return batchResult.score
    }
    const req = requirements.find(r => r.req_id === reqId)
    return req?.validation_score
  }

  // Get updated requirement with merged batch result
  const getMergedRequirement = (req) => {
    const batchResult = batchResults.find(r => r.req_id === req.req_id)
    if (batchResult) {
      return {
        ...req,
        validation_score: batchResult.score,
        validation_passed: batchResult.passed,
        title: batchResult.final_text || req.title
      }
    }
    return req
  }

  // Filter failing requirements - considering batch results
  // Only include requirements that have been validated AND have a score below 0.7
  // Requirements with null/undefined scores are "not validated" not "failing"
  const failingRequirements = requirements.filter(req => {
    const score = getUpdatedScore(req.req_id)
    // Must have a real score (not null/undefined) AND score < 0.7
    return score !== undefined && score !== null && score < 0.7
  })

  // Requirements that were failing but now pass after batch validation
  // Also include split children that pass (they won't exist in requirements array yet)
  const newlyPassingRequirements = batchResults.filter(r => {
    if (!r.passed || r.score < 0.7) return false

    const req = requirements.find(req => req.req_id === r.req_id)

    // Include split children (identified by -CHILD- in ID or parent_id property)
    if (!req && (r.req_id.includes('-CHILD-') || r.parent_id)) return true

    // Include if original requirement was failing and now passes
    const originalScore = req?.validation_score
    return originalScore !== undefined && originalScore < 0.7
  })

  const passingRequirements = requirements.filter(req => {
    const score = getUpdatedScore(req.req_id)
    // Must have a real score (not null/undefined) AND score >= 0.7
    return score !== undefined && score !== null && score >= 0.7
  })

  // Get selected requirement - also check passing requirements
  const selectedRequirement = requirements.find(r => r.req_id === selectedReqId) || null

  // Get batch validation status for a requirement
  const getBatchStatus = (reqId) => {
    if (currentBatchReqId === reqId) return 'validating'
    const result = batchResults.find(r => r.req_id === reqId)
    if (result) return result.passed ? 'passed' : 'failed'
    return 'pending'
  }

  const handleCardClick = (reqId) => {
    setSelectedReqId(reqId)
  }

  const handleValidationStart = (reqId) => {
    setValidatingReqId(reqId)
  }

  const handleInlineValidationComplete = (reqId, result) => {
    setValidatingReqId(null)
    // Bubble up to parent for state update and KG rebuild
    if (onValidationComplete) {
      onValidationComplete(reqId, result)
    }
  }

  // Handle answer submission for a requirement needing user input
  const handleSubmitAnswers = async (reqId, answeredQuestions) => {
    setIsSubmittingAnswer(true)
    addBatchEvent('info', `📝 Submitting ${answeredQuestions.length} answer(s) for ${reqId}...`)

    try {
      // Submit answers to backend
      const response = await fetch('/api/v1/clarification/answer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          requirement_id: reqId,
          answers: answeredQuestions,
          trigger_revalidation: true,
          session_id: batchSessionIdRef.current
        })
      })

      const data = await response.json()

      if (data.success) {
        addBatchEvent('success', `✅ Answers submitted for ${reqId}`)

        // If re-validation was triggered and completed
        if (data.revalidation_result) {
          const result = data.revalidation_result
          addBatchEvent(
            result.passed ? 'success' : 'warning',
            `🔄 ${reqId}: Re-validated ${(result.score * 100).toFixed(0)}% ${result.passed ? 'PASS' : 'FAIL'}`
          )

          // Remove from pending questions
          setPendingQuestions(prev => prev.filter(p => p.req_id !== reqId))
          setNeedsInputCount(prev => Math.max(0, prev - 1))
          setSelectedNeedsInputReqId(null)

          // Add to batch results
          setBatchResults(prev => [...prev, {
            req_id: reqId,
            passed: result.passed,
            score: result.score,
            final_text: result.final_text || result.text,
            evaluation: result.evaluation || []
          }])

          // Notify parent
          if (onValidationComplete) {
            onValidationComplete(reqId, result)
          }
        }
      } else {
        addBatchEvent('error', `❌ Failed to submit answers: ${data.error || 'Unknown error'}`)
      }
    } catch (err) {
      console.error('[ValidationTab] Answer submission error:', err)
      addBatchEvent('error', `❌ Error submitting answers: ${err.message}`)
    } finally {
      setIsSubmittingAnswer(false)
    }
  }

  // Handle skipping a question
  const handleSkipQuestion = async (questionId) => {
    try {
      await fetch(`/api/v1/clarification/skip/${questionId}`, {
        method: 'POST'
      })
      addBatchEvent('info', `⏭️ Skipped question ${questionId}`)
    } catch (err) {
      console.error('[ValidationTab] Skip question error:', err)
    }
  }

  // Get currently selected requirement needing input
  const selectedNeedsInputItem = batchPendingQuestions?.find(p => p.req_id === selectedNeedsInputReqId)

  // Auto-scroll event log
  useEffect(() => {
    if (eventLogRef.current) {
      eventLogRef.current.scrollTop = eventLogRef.current.scrollHeight
    }
  }, [batchEventLog])

  // Batch validation functions
  const addBatchEvent = (type, message) => {
    const timestamp = new Date().toLocaleTimeString()
    setBatchEventLog(prev => [...prev, { timestamp, type, message }])
  }

  const connectBatchSSE = (sessionId) => {
    const eventSource = new EventSource(`/api/v1/validation/stream/${sessionId}`)
    batchEventSourceRef.current = eventSource

    eventSource.addEventListener('requirement_updated', (e) => {
      const data = JSON.parse(e.data)
      addBatchEvent('update', `Fixed ${data.criterion}: ${(data.score_before * 100).toFixed(0)}% -> ${(data.score_after * 100).toFixed(0)}%`)
    })

    eventSource.addEventListener('requirement_split', (e) => {
      const data = JSON.parse(e.data)
      addBatchEvent('split', `Split into ${data.child_count || data.new_requirement_ids?.length || 0} atomic requirements`)
    })

    eventSource.addEventListener('validation_complete', (e) => {
      const data = JSON.parse(e.data)
      addBatchEvent('complete', `${data.requirement_id}: ${(data.final_score * 100).toFixed(0)}% ${data.passed ? 'PASS' : 'FAIL'}`)
    })

    eventSource.addEventListener('validation_error', (e) => {
      const data = JSON.parse(e.data)
      addBatchEvent('error', data.error || data.message)
    })

    // Human-in-the-loop: Handle requirements needing user input
    eventSource.addEventListener('needs_user_input', (e) => {
      const data = JSON.parse(e.data)
      addBatchEvent('needs_input', `⏸️ ${data.requirement_id}: Needs user input (${data.questions?.length || 0} questions)`)

      // Add to pending questions
      setPendingQuestions(prev => [
        ...prev.filter(p => p.req_id !== data.requirement_id), // Avoid duplicates
        {
          req_id: data.requirement_id,
          requirement_text: data.current_text,
          questions: data.questions || [],
          failing_criteria: data.failing_criteria || [],
          current_scores: data.current_scores || {},
          status: 'awaiting_input'
        }
      ])
      setNeedsInputCount(prev => prev + 1)
    })

    // Handle re-validation complete after user answers
    eventSource.addEventListener('revalidation_complete', (e) => {
      const data = JSON.parse(e.data)
      addBatchEvent(data.passed ? 'success' : 'warning', `🔄 ${data.requirement_id}: Re-validated ${(data.score * 100).toFixed(0)}% ${data.passed ? 'PASS' : 'FAIL'}`)

      // Remove from pending questions
      setPendingQuestions(prev => prev.filter(p => p.req_id !== data.requirement_id))
      setNeedsInputCount(prev => Math.max(0, prev - 1))

      // Add to batch results
      setBatchResults(prev => [...prev, {
        req_id: data.requirement_id,
        passed: data.passed,
        score: data.score,
        final_text: data.final_text,
        evaluation: data.evaluation || []
      }])
    })

    eventSource.onerror = () => {
      // Silent reconnect handled by browser
    }

    return eventSource
  }

  // Recursive tree validation function - validates requirement and all descendants
  const validateRequirementTree = async (req, depth = 0, maxDepth = 5) => {
    const indent = '  '.repeat(depth)

    // Prevent infinite recursion
    if (depth >= maxDepth) {
      addBatchEvent('warning', `${indent}⚠️ Max recursion depth ${maxDepth} reached for ${req.req_id}`)
      return []
    }

    // Phase 1: Validate this requirement
    addBatchEvent('info', `${indent}🔍 Validating ${req.req_id} (depth ${depth})`)

    try {
      const response = await fetch('/api/v1/validate/auto', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          requirement_id: req.req_id,
          requirement_text: req.text || req.title,
          session_id: batchSessionIdRef.current,
          threshold: 0.7,
          max_iterations: 3
        })
      })

      const data = await response.json()
      const finalScore = data.final_score ?? data.score ?? 0
      const passed = data.passed ?? (finalScore >= 0.7)
      const finalText = data.final_text || data.corrected_text || req.text || req.title

      // Log validation result
      const icon = passed ? '✅' : '❌'
      const percent = Math.round(finalScore * 100)
      addBatchEvent(
        passed ? 'success' : 'warning',
        `${indent}${icon} ${req.req_id}: ${percent}% ${passed ? 'PASS' : 'FAIL'}`
      )

      // Create result object
      const result = {
        req_id: req.req_id,
        passed,
        score: finalScore,
        validation_score: finalScore,
        validation_passed: passed,
        final_text: finalText,
        title: finalText,
        total_fixes: data.total_fixes || 0,
        evaluation: data.evaluation || [],
        split_occurred: data.split_occurred || false,
        split_children: data.split_children || [],
        depth,
        parent_id: req.parent_id,
        is_split_child: req.is_split_child || false,
        tag: req.tag,
        evidence_refs: req.evidence_refs
      }

      // Phase 2: Handle splits recursively
      if (data.split_occurred && data.split_children && data.split_children.length > 0) {
        addBatchEvent('split', `${indent}📋 ${req.req_id} split into ${data.split_children.length} children`)

        // Create child requirement objects
        const children = data.split_children.map((childText, idx) => ({
          req_id: `${req.req_id}-CHILD-${idx + 1}`,
          title: childText,
          text: childText,
          tag: req.tag || 'split',
          evidence_refs: req.evidence_refs || [],
          parent_id: req.req_id,
          is_split_child: true,
          depth: depth + 1
        }))

        // Phase 3: RECURSIVELY validate ALL children in parallel
        addBatchEvent('info', `${indent}🚀 Parallel validating ${children.length} children...`)

        const childResultsArrays = await Promise.all(
          children.map(child => validateRequirementTree(child, depth + 1, maxDepth))
        )

        // Flatten results (each recursive call returns an array)
        const flatChildResults = childResultsArrays.flat()

        // Phase 4: Auto-prune failing branches
        const passingChildren = flatChildResults.filter(r => r.passed && r.score >= 0.7)
        const failingChildren = flatChildResults.filter(r => !r.passed || r.score < 0.7)

        // Edge case: If ALL descendants fail, keep parent with warning
        if (passingChildren.length === 0 && flatChildResults.length > 0) {
          addBatchEvent('warning', `${indent}⚠️ All ${flatChildResults.length} descendants failed - keeping original`)
          return [result]
        }

        // Log cleanup summary
        if (failingChildren.length > 0) {
          addBatchEvent('info', `${indent}🗑️ Auto-pruned ${failingChildren.length} failed branch(es)`)
        }
        addBatchEvent('success', `${indent}✅ Kept ${passingChildren.length} passing children`)

        // Return only passing children (discard failing parent)
        return passingChildren
      }

      // No split - return this result
      return [result]

    } catch (err) {
      console.error(`[ValidationTab] Error validating ${req.req_id}:`, err)
      addBatchEvent('error', `${indent}❌ ${req.req_id}: ${err.message}`)
      return []
    }
  }

  // Check if batch is complete and finalize
  const checkBatchComplete = () => {
    const totalReqs = batchQueueRef.current.length
    const allStarted = startedCountRef.current >= totalReqs
    const allCompleted = completedCountRef.current >= totalReqs
    const noActiveValidations = activeTreesRef.current.size === 0

    console.log('[checkBatchComplete]', {
      started: startedCountRef.current,
      completed: completedCountRef.current,
      active: activeTreesRef.current.size,
      total: totalReqs,
      allStarted,
      allCompleted,
      noActiveValidations
    })

    if (allStarted && allCompleted && noActiveValidations) {
      // Batch complete
      setBatchStatus('completed')
      setCurrentBatchReqId(null)
      setIsBatchValidating(false)
      addBatchEvent('success', `Batch complete: ${batchResults.filter(r => r.passed).length} passed, ${batchResults.filter(r => !r.passed).length} failed`)

      // Close SSE
      if (batchEventSourceRef.current) {
        batchEventSourceRef.current.close()
        batchEventSourceRef.current = null
      }
    } else if (allStarted && !allCompleted) {
      // Still waiting for active validations to finish
      console.log('[checkBatchComplete] Waiting for', activeTreesRef.current.size, 'active validations')
    } else {
      // Start more validations if we haven't started all and have capacity
      validateNextInBatch()
    }
  }

  const validateNextInBatch = () => {
    // Check if we've started all requirements
    if (batchIndexRef.current >= batchQueueRef.current.length) {
      console.log('[validateNextInBatch] All requirements started, waiting for completion...')
      return
    }

    // Check if we have capacity for more parallel validations
    if (activeTreesRef.current.size >= MAX_PARALLEL_TREES) {
      console.log('[validateNextInBatch] Max parallel limit reached, waiting...')
      return
    }

    // Start next validation
    const req = batchQueueRef.current[batchIndexRef.current]
    const reqId = req.req_id

    // Track this validation
    activeTreesRef.current.add(reqId)
    startedCountRef.current += 1
    batchIndexRef.current += 1

    // Update progress (use started count for progress display)
    setBatchProgress({
      current: startedCountRef.current,
      total: batchQueueRef.current.length
    })
    setCurrentBatchReqId(reqId)
    addBatchEvent('start', `🚀 Starting ${reqId}: ${(req.title || req.text || '').substring(0, 40)}...`)

    console.log('[validateNextInBatch] Started', reqId, '- Active:', activeTreesRef.current.size, 'Started:', startedCountRef.current, 'Completed:', completedCountRef.current)

    // Fire-and-forget: Start validation WITHOUT await
    const treePromise = validateRequirementTree({
      req_id: req.req_id,
      text: req.title || req.text,
      title: req.title || req.text,
      tag: req.tag,
      evidence_refs: req.evidence_refs,
      parent_id: null,
      is_split_child: false
    }, 0, 5)

    // Handle completion asynchronously
    treePromise
      .then(treeResults => {
        console.log('[validateNextInBatch] Tree completed for', reqId, ':', treeResults.length, 'results')

        // Mark as completed and remove from active
        activeTreesRef.current.delete(reqId)
        completedCountRef.current += 1

        // Add all passing results to batch results
        treeResults.forEach(result => {
          setBatchResults(prev => [...prev, result])

          // Notify parent component for each passing requirement
          if (onValidationComplete) {
            onValidationComplete(result.req_id, {
              final_score: result.score,
              passed: result.passed,
              final_text: result.final_text,
              evaluation: result.evaluation,
              total_fixes: result.total_fixes,
              split_occurred: result.split_occurred,
              split_children: result.split_children
            }, {
              req_id: result.req_id,
              title: result.title,
              text: result.final_text,
              tag: result.tag,
              evidence_refs: result.evidence_refs,
              parent_id: result.parent_id,
              is_split_child: result.is_split_child
            })
          }
        })

        // Check if batch is complete or start more
        checkBatchComplete()
      })
      .catch(err => {
        console.error('[validateNextInBatch] Validation error for', reqId, ':', err)

        // Mark as completed (failed) and remove from active
        activeTreesRef.current.delete(reqId)
        completedCountRef.current += 1

        addBatchEvent('error', `❌ ${reqId}: ${err.message}`)
        setBatchResults(prev => [...prev, {
          req_id: reqId,
          passed: false,
          score: 0,
          final_text: req.title || req.text || ''
        }])

        // Check if batch is complete or start more
        checkBatchComplete()
      })

    // Immediately try to start next validation (up to MAX_PARALLEL_TREES)
    setTimeout(() => validateNextInBatch(), 100)
  }

  const startBatchValidation = () => {
    if (failingRequirements.length === 0) return

    // Reset state
    setIsBatchValidating(true)
    setBatchStatus('running')
    setBatchEventLog([])
    setBatchResults([])
    setBatchProgress({ current: 0, total: failingRequirements.length })
    setSelectedReqId(null) // Clear selection to show batch panel

    // Setup refs
    batchQueueRef.current = [...failingRequirements]
    batchIndexRef.current = 0
    batchSessionIdRef.current = `batch-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`

    // Reset parallel tracking refs
    activeTreesRef.current.clear()
    completedCountRef.current = 0
    startedCountRef.current = 0

    addBatchEvent('info', `🚀 Starting parallel batch validation of ${failingRequirements.length} requirements (max ${MAX_PARALLEL_TREES} concurrent)`)

    // Connect SSE
    connectBatchSSE(batchSessionIdRef.current)

    // Start first batch of validations (up to MAX_PARALLEL_TREES)
    for (let i = 0; i < Math.min(MAX_PARALLEL_TREES, failingRequirements.length); i++) {
      setTimeout(() => validateNextInBatch(), i * 100) // Stagger slightly
    }
  }

  const cancelBatchValidation = () => {
    setBatchStatus('completed')
    setIsBatchValidating(false)
    setCurrentBatchReqId(null)
    addBatchEvent('info', 'Batch validation cancelled')

    if (batchEventSourceRef.current) {
      batchEventSourceRef.current.close()
      batchEventSourceRef.current = null
    }
  }

  // =========================================================================
  // NEW: Batch Enhancement - Question Collection
  // =========================================================================

  const startBatchEnhancement = async () => {
    if (failingRequirements.length === 0) return

    setIsCollectingQuestions(true)
    setQuestionReport(null)
    addBatchEvent('info', `🧠 Starting batch enhancement - collecting questions for ${failingRequirements.length} requirements...`)

    try {
      const response = await fetch('/api/v1/enhance/batch-questions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          requirements: failingRequirements.map(req => ({
            req_id: req.req_id,
            text: req.title || req.text
          })),
          quality_threshold: 0.7
        })
      })

      const report = await response.json()

      if (report.success) {
        setQuestionReport(report)
        addBatchEvent('success', `✅ Collected ${report.total_questions} questions for ${report.requirements_needing_input} requirements`)
      } else {
        addBatchEvent('error', `❌ Question collection failed: ${report.error}`)
      }
    } catch (err) {
      console.error('[ValidationTab] Question collection error:', err)
      addBatchEvent('error', `❌ Error collecting questions: ${err.message}`)
    } finally {
      setIsCollectingQuestions(false)
    }
  }

  const handleApplyAnswers = async (answersData) => {
    setIsApplyingAnswers(true)
    addBatchEvent('info', `✨ Applying answers and enhancing requirements...`)

    try {
      const response = await fetch('/api/v1/enhance/apply-answers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(answersData)
      })

      const result = await response.json()

      if (result.success) {
        addBatchEvent('success', `✅ Enhanced ${result.total_enhanced} requirements - ${result.passed_count} passed, ${result.failed_count} failed`)

        // Add results to batch results and notify parent
        result.results.forEach(r => {
          if (!r.skipped) {
            const updatedResult = {
              req_id: r.req_id,
              passed: r.passed,
              score: r.final_score,
              final_text: r.enhanced_text,
              evaluation: []
            }
            setBatchResults(prev => [...prev, updatedResult])

            // Notify parent component
            if (onValidationComplete) {
              onValidationComplete(r.req_id, {
                final_score: r.final_score,
                passed: r.passed,
                final_text: r.enhanced_text
              })
            }
          }
        })

        // Close report panel
        setQuestionReport(null)
      } else {
        addBatchEvent('error', `❌ Enhancement failed: ${result.error}`)
      }
    } catch (err) {
      console.error('[ValidationTab] Apply answers error:', err)
      addBatchEvent('error', `❌ Error applying answers: ${err.message}`)
    } finally {
      setIsApplyingAnswers(false)
    }
  }

  const handleCloseReport = () => {
    setQuestionReport(null)
  }

  // =========================================================================
  // NEW: Auto-Enhance Batch - No User Input Required
  // =========================================================================

  const startAutoEnhancement = async () => {
    if (failingRequirements.length === 0) return

    setIsAutoEnhancing(true)
    setAutoEnhanceResults(null)
    addBatchEvent('info', `🤖 Starting AUTO-ENHANCE for ${failingRequirements.length} requirements (no user input needed)...`)

    try {
      const response = await fetch('/api/v1/enhance/auto-batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          requirements: failingRequirements.map(req => ({
            req_id: req.req_id,
            text: req.title || req.text
          })),
          quality_threshold: 0.7,
          max_iterations: 3
        })
      })

      const result = await response.json()

      if (result.success) {
        setAutoEnhanceResults(result)
        addBatchEvent('success', `✅ AUTO-ENHANCE complete: ${result.passed_count}/${result.total_processed} passed (avg ${Math.round(result.average_score * 100)}%)`)
        addBatchEvent('info', `📊 Improved: ${result.improved_count} | Time: ${result.total_time_ms}ms`)

        // Add results to batch results and notify parent
        result.results.forEach(r => {
          const updatedResult = {
            req_id: r.id,
            passed: r.verdict === 'pass',
            score: r.score,
            final_text: r.enhanced_text,
            evaluation: [],
            purpose: r.purpose,
            gaps_filled: r.gaps_filled || [],
            gaps_remaining: r.gaps_remaining || [],
            changes: r.changes || []
          }
          setBatchResults(prev => [...prev, updatedResult])

          // Notify parent component
          if (onValidationComplete) {
            onValidationComplete(r.id, {
              final_score: r.score,
              passed: r.verdict === 'pass',
              final_text: r.enhanced_text
            })
          }

          // Log individual results
          const icon = r.verdict === 'pass' ? '✅' : '⚠️'
          addBatchEvent(r.verdict === 'pass' ? 'success' : 'warning',
            `${icon} ${r.id}: ${Math.round(r.score * 100)}% (${r.iterations} iter)`)
        })
      } else {
        addBatchEvent('error', `❌ Auto-enhance failed: ${result.error}`)
      }
    } catch (err) {
      console.error('[ValidationTab] Auto-enhance error:', err)
      addBatchEvent('error', `❌ Error during auto-enhance: ${err.message}`)
    } finally {
      setIsAutoEnhancing(false)
    }
  }

  const handleCloseAutoResults = () => {
    setAutoEnhanceResults(null)
  }

  // =========================================================================
  // NEW: All-in-One Pipeline (Unified Mining → Validation → Enhancement)
  // =========================================================================

  const startAllInOnePipeline = async (mode = validationMode) => {
    const reqs = failingRequirements.length > 0 ? failingRequirements : requirements.filter(r => r.req_id)

    if (reqs.length === 0) {
      addBatchEvent('warning', '⚠️ No requirements to process')
      return
    }

    // Reset state
    setPipelineStage('running')
    setPipelineEvents([])
    setIsBatchValidating(true)
    setBatchEventLog([])
    setBatchResults([])

    const sessionId = `pipeline-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
    batchSessionIdRef.current = sessionId

    addBatchEvent('start', `🚀 Starting All-in-One Pipeline (${mode} mode) for ${reqs.length} requirements`)
    addBatchEvent('info', `📋 Session: ${sessionId}`)

    // Connect to SSE for real-time updates
    const eventSource = new EventSource(`/api/v1/validation/stream/${sessionId}`)
    batchEventSourceRef.current = eventSource

    eventSource.addEventListener('pipeline_start', (e) => {
      const data = JSON.parse(e.data)
      addBatchEvent('info', `📊 Pipeline started: ${data.total_count} requirements, mode: ${data.mode}`)
    })

    eventSource.addEventListener('stage_change', (e) => {
      const data = JSON.parse(e.data)
      const stageIcons = {
        validating: '🔍',
        enhancing: '✨',
        collecting_questions: '❓',
        applying_answers: '📝',
        complete: '✅'
      }
      addBatchEvent('info', `${stageIcons[data.stage] || '📌'} Stage: ${data.stage}`)
      setPipelineStage(data.stage)
    })

    eventSource.addEventListener('requirement_scored', (e) => {
      const data = JSON.parse(e.data)
      const icon = data.verdict === 'pass' ? '✅' : '⚠️'
      addBatchEvent(data.verdict === 'pass' ? 'success' : 'warning',
        `${icon} ${data.req_id}: ${Math.round(data.score * 100)}% ${data.enhanced ? '(enhanced)' : ''}`)
    })

    eventSource.addEventListener('question_generated', (e) => {
      const data = JSON.parse(e.data)
      addBatchEvent('needs_input', `❓ ${data.req_id}: ${data.questions?.length || 0} questions generated`)

      // In guided mode, store questions for user
      if (mode === 'guided') {
        setPendingQuestions(prev => [...prev, {
          req_id: data.req_id,
          questions: data.questions,
          gaps: data.gaps,
          current_score: data.current_score
        }])
      }
    })

    eventSource.addEventListener('enhancement_applied', (e) => {
      const data = JSON.parse(e.data)
      addBatchEvent('success', `✨ ${data.req_id}: ${Math.round(data.old_score * 100)}% → ${Math.round(data.new_score * 100)}%`)
    })

    eventSource.addEventListener('pipeline_complete', (e) => {
      const data = JSON.parse(e.data)
      addBatchEvent('success', `🎉 Pipeline complete: ${data.passed} passed, ${data.failed} failed`)
      if (data.improved) {
        addBatchEvent('info', `📈 Improved: ${data.improved} requirements`)
      }
    })

    eventSource.onerror = () => {
      // Silently handle reconnections
    }

    try {
      const response = await fetch('/api/v1/validate/all-in-one', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          requirements: reqs.map(req => ({
            id: req.req_id,
            text: req.title || req.text,
            tag: req.tag
          })),
          mode: mode,
          session_id: sessionId
        })
      })

      const result = await response.json()

      if (result.success) {
        // Process results
        const processedReqs = result.requirements || []

        processedReqs.forEach(r => {
          const updatedResult = {
            req_id: r.id,
            passed: r.verdict === 'pass' || r.score >= 0.7,
            score: r.score,
            final_text: r.enhanced_text || r.original_text,
            evaluation: [],
            purpose: r.purpose,
            questions: r.questions
          }
          setBatchResults(prev => [...prev, updatedResult])

          // Notify parent
          if (onValidationComplete) {
            onValidationComplete(r.id, {
              final_score: r.score,
              passed: r.verdict === 'pass' || r.score >= 0.7,
              final_text: r.enhanced_text || r.original_text
            })
          }
        })

        // Handle guided mode - show questions if any pending
        if (mode === 'guided' && result.pending_questions?.length > 0) {
          setPipelineStage('awaiting_answers')
          addBatchEvent('needs_input', `⏸️ Waiting for ${result.pending_questions.length} answers`)

          // Store questions for QuestionReportPanel
          setQuestionReport({
            items: processedReqs,
            total_questions: result.pending_questions.reduce((sum, p) => sum + (p.questions?.length || 0), 0),
            requirements_needing_input: result.pending_questions.length,
            session_id: sessionId
          })
        } else {
          setPipelineStage('complete')
          addBatchEvent('success', `✅ All-in-One complete: ${result.passed_count}/${result.total_processed} passed`)
        }
      } else {
        addBatchEvent('error', `❌ Pipeline failed: ${result.error}`)
        setPipelineStage('idle')
      }
    } catch (err) {
      console.error('[ValidationTab] All-in-One error:', err)
      addBatchEvent('error', `❌ Error: ${err.message}`)
      setPipelineStage('idle')
    } finally {
      setIsBatchValidating(false)
      // Keep SSE open for follow-up events, close after delay
      setTimeout(() => {
        if (batchEventSourceRef.current) {
          batchEventSourceRef.current.close()
        }
      }, 5000)
    }
  }

  // Handle "Proceed" for guided mode after answering questions
  const handleProceedWithAnswers = async () => {
    if (!questionReport) return

    setIsApplyingAnswers(true)
    addBatchEvent('info', '📝 Applying answers and continuing pipeline...')

    try {
      const response = await fetch('/api/v1/validate/all-in-one/apply-answers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: batchSessionIdRef.current,
          answers: questionReport.items?.map(item => ({
            req_id: item.id,
            original_text: item.original_text,
            answered_questions: item.questions?.map(q => ({
              question: q.question,
              answer: q.answer || q.suggested_answers?.[0] || ''
            }))
          })) || []
        })
      })

      const result = await response.json()

      if (result.success) {
        addBatchEvent('success', `✅ Enhanced ${result.improved_count} requirements`)
        setQuestionReport(null)
        setPipelineStage('complete')

        // Update results
        result.requirements?.forEach(r => {
          setBatchResults(prev => [...prev.filter(p => p.req_id !== r.id), {
            req_id: r.id,
            passed: r.verdict === 'pass',
            score: r.score,
            final_text: r.enhanced_text
          }])

          if (onValidationComplete) {
            onValidationComplete(r.id, {
              final_score: r.score,
              passed: r.verdict === 'pass',
              final_text: r.enhanced_text
            })
          }
        })
      } else {
        addBatchEvent('error', `❌ Apply answers failed: ${result.error}`)
      }
    } catch (err) {
      addBatchEvent('error', `❌ Error: ${err.message}`)
    } finally {
      setIsApplyingAnswers(false)
    }
  }

  // Calculate batch stats
  const batchPassedCount = batchResults.filter(r => r.passed).length
  const batchFailedCount = batchResults.filter(r => !r.passed).length
  const batchProgressPercent = batchProgress.total > 0
    ? Math.round((batchProgress.current / batchProgress.total) * 100)
    : 0

  return (
    <div className="validation-tab-container">
      {/* Stats Bar */}
      <div className="validation-stats-bar">
        <div className="stats-summary">
          <div className="stat-item">
            <span className="stat-label">Total:</span>
            <span className="stat-value">{requirements.length}</span>
          </div>
          <div className="stat-item pass">
            <span className="stat-label">Passing:</span>
            <span className="stat-value">{passingRequirements.length}</span>
          </div>
          <div className="stat-item fail">
            <span className="stat-label">Failing:</span>
            <span className="stat-value">{failingRequirements.length}</span>
          </div>
          {batchPendingQuestions && batchPendingQuestions.length > 0 && (
            <div className="stat-item needs-input">
              <span className="stat-label">Needs Input:</span>
              <span className="stat-value">{batchPendingQuestions.length}</span>
            </div>
          )}
        </div>

        {/* NEW: 2-Mode Selector + Single Start Button */}
        {requirements.length > 0 && !isBatchValidating && !questionReport && pipelineStage !== 'awaiting_answers' && (
          <div className="validation-mode-section">
            <div className="mode-selector">
              <button
                className={`mode-btn ${validationMode === 'quick' ? 'active' : ''}`}
                onClick={() => setValidationMode('quick')}
              >
                <span className="mode-icon">⚡</span>
                <span className="mode-name">Quick</span>
                <span className="mode-desc">Auto-fix, no questions</span>
              </button>
              <button
                className={`mode-btn ${validationMode === 'guided' ? 'active' : ''}`}
                onClick={() => setValidationMode('guided')}
              >
                <span className="mode-icon">🧠</span>
                <span className="mode-name">Guided</span>
                <span className="mode-desc">With clarification</span>
              </button>
            </div>
            <button
              className="btn-start-pipeline"
              onClick={() => startAllInOnePipeline(validationMode)}
              disabled={isBatchValidating || isAutoEnhancing}
            >
              {failingRequirements.length > 0
                ? `🚀 Start Validation (${failingRequirements.length} failing)`
                : `🚀 Validate All (${requirements.length})`}
            </button>
          </div>
        )}

        {/* Show Proceed button when awaiting answers in guided mode */}
        {pipelineStage === 'awaiting_answers' && questionReport && (
          <button
            className="btn-proceed"
            onClick={handleProceedWithAnswers}
            disabled={isApplyingAnswers}
          >
            {isApplyingAnswers ? '⏳ Applying...' : '✅ Proceed with Answers'}
          </button>
        )}

        {isAutoEnhancing && (
          <div className="auto-enhancing-indicator">
            <span className="spinner">⏳</span>
            <span>Auto-Enhancing {failingRequirements.length} requirements...</span>
          </div>
        )}

        {isBatchValidating && (
          <button
            className="btn-cancel-batch"
            onClick={cancelBatchValidation}
          >
            Cancel Batch
          </button>
        )}
      </div>

      {/* Split Layout */}
      <div className="validation-split-layout">
        {/* Left: Requirements List */}
        <div className="requirements-list-panel">
          <h3 className="panel-title">
            {isBatchValidating ? 'Batch Progress' : `Failing Requirements (${failingRequirements.length})`}
          </h3>

          <div className="requirements-scroll">
            {/* Show newly passing requirements during/after batch */}
            {newlyPassingRequirements.length > 0 && (isBatchValidating || batchStatus === 'completed') && (
              <div className="newly-passing-section">
                <h4 className="section-title passing">✓ Newly Passing ({newlyPassingRequirements.length})</h4>
                {newlyPassingRequirements.map(result => {
                  const req = requirements.find(r => r.req_id === result.req_id)

                  // If requirement doesn't exist, create a temporary one from batch result (for split children)
                  const displayReq = req || {
                    req_id: result.req_id,
                    title: result.final_text || result.title || result.text,
                    text: result.final_text || result.text,
                    tag: 'split',
                    validation_score: result.score,
                    validation_passed: result.passed,
                    is_split_child: true,
                    evaluation: result.evaluation || [],
                    evidence_refs: []
                  }

                  return (
                    <ValidationRequirementCard
                      key={result.req_id}
                      requirement={getMergedRequirement(displayReq)}
                      isSelected={result.req_id === selectedReqId}
                      onClick={() => handleCardClick(result.req_id)}
                      batchStatus="passed"
                    />
                  )
                })}
              </div>
            )}

            {/* Needs User Input section - human-in-the-loop */}
            {batchPendingQuestions && batchPendingQuestions.length > 0 && (
              <div className="needs-input-section">
                <h4 className="section-title needs-input">⏸️ needs Input ({batchPendingQuestions.length})</h4>
                {batchPendingQuestions.map(item => (
                  <div
                    key={item.req_id}
                    className={`needs-input-card ${selectedNeedsInputReqId === item.req_id ? 'selected' : ''}`}
                    onClick={() => setSelectedNeedsInputReqId(item.req_id)}
                  >
                    <div className="needs-input-header">
                      <span className="req-id">{item.req_id}</span>
                      <span className="question-count">{item.questions?.length || 0} questions</span>
                    </div>
                    <div className="needs-input-text">
                      {(item.requirement_text || '').substring(0, 80)}...
                    </div>
                    <div className="needs-input-criteria">
                      {item.failing_criteria?.map(c => (
                        <span key={c} className="criterion-tag">{c}</span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Still failing requirements */}
            {failingRequirements.length === 0 && newlyPassingRequirements.length === 0 ? (
              <div className="no-failing-state">
                <div className="success-icon">✓</div>
                <h4>All Requirements Pass!</h4>
                <p>Great job! All {requirements.length} requirements meet the quality criteria.</p>
              </div>
            ) : failingRequirements.length === 0 && newlyPassingRequirements.length > 0 ? (
              <div className="all-fixed-state">
                <div className="success-icon">🎉</div>
                <h4>All Fixed!</h4>
                <p>All {newlyPassingRequirements.length} requirements now pass validation.</p>
              </div>
            ) : (
              <>
                {(isBatchValidating || batchStatus === 'completed') && newlyPassingRequirements.length > 0 && (
                  <h4 className="section-title failing">✗ Still Failing ({failingRequirements.length})</h4>
                )}
                {failingRequirements.map(req => (
                  <ValidationRequirementCard
                    key={req.req_id}
                    requirement={getMergedRequirement(req)}
                    isSelected={req.req_id === selectedReqId}
                    onClick={() => handleCardClick(req.req_id)}
                    batchStatus={isBatchValidating ? getBatchStatus(req.req_id) : null}
                  />
                ))}
              </>
            )}
          </div>
        </div>

        {/* Right: Detail Panel or Batch Progress OR Question Report */}
        <div className="detail-panel-container">
          {isCollectingQuestions ? (
            // NEW: Show collecting progress indicator
            <div className="batch-validation-panel">
              <div className="batch-header">
                <h3>🧠 Collecting Questions</h3>
                <span className="batch-status running">Analyzing...</span>
              </div>
              <div className="batch-progress-section">
                <div className="progress-info">
                  <span className="progress-text">
                    Analyzing {failingRequirements.length} requirements for improvement gaps...
                  </span>
                </div>
                <div className="progress-bar">
                  <div className="progress-fill indeterminate" />
                </div>
                <div className="collecting-info">
                  <p>🔍 Identifying purpose and gaps</p>
                  <p>📊 Evaluating quality scores</p>
                  <p>❓ Generating targeted questions</p>
                </div>
              </div>
              <div className="batch-event-section">
                <h4>Event Log</h4>
                <div className="batch-event-log" ref={eventLogRef}>
                  {batchEventLog.map((event, idx) => (
                    <div key={idx} className={`batch-event-item event-${event.type}`}>
                      <span className="event-time">[{event.timestamp}]</span>
                      <span className="event-msg">{event.message}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : questionReport ? (
            // NEW: Question Report Panel for batch enhancement
            <QuestionReportPanel
              report={questionReport}
              onApplyAnswers={handleApplyAnswers}
              onClose={handleCloseReport}
              isApplying={isApplyingAnswers}
            />
          ) : isBatchValidating || batchStatus === 'completed' ? (
            // Inline Batch Validation Panel
            <div className="batch-validation-panel">
              <div className="batch-header">
                <h3>Batch Validation</h3>
                <span className={`batch-status ${batchStatus}`}>
                  {batchStatus === 'running' ? 'Running...' : batchStatus === 'completed' ? 'Completed' : batchStatus}
                </span>
              </div>

              {/* Progress Section */}
              <div className="batch-progress-section">
                <div className="progress-info">
                  <span className="progress-text">
                    Progress: {batchProgress.current}/{batchProgress.total}
                  </span>
                  <span className="progress-percent">{batchProgressPercent}%</span>
                </div>
                <div className="progress-bar">
                  <div
                    className="progress-fill"
                    style={{ width: `${batchProgressPercent}%` }}
                  />
                </div>

                {/* Stats Row */}
                <div className="batch-stats-row">
                  <span className="batch-stat pass">Passed: {batchPassedCount}</span>
                  <span className="batch-stat fail">Failed: {batchFailedCount}</span>
                  {batchPendingQuestions && batchPendingQuestions.length > 0 && (
                    <span className="batch-stat needs-input">Needs Input: {batchPendingQuestions.length}</span>
                  )}
                  <span className="batch-stat active">
                    Active: {activeTreesRef.current.size}
                  </span>
                  <span className="batch-stat completed">
                    Completed: {completedCountRef.current}/{batchProgress.total}
                  </span>
                </div>
              </div>

              {/* Event Log */}
              <div className="batch-event-section">
                <h4>Event Log</h4>
                <div className="batch-event-log" ref={eventLogRef}>
                  {batchEventLog.map((event, idx) => (
                    <div key={idx} className={`batch-event-item event-${event.type}`}>
                      <span className="event-time">[{event.timestamp}]</span>
                      <span className="event-msg">{event.message}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Actions */}
              {batchStatus === 'completed' && (
                <div className="batch-actions">
                  <button
                    className="btn-clear-batch"
                    onClick={() => {
                      setBatchValidationState({
                        isValidating: false,
                        progress: { current: 0, total: 0 },
                        eventLog: [],
                        results: [],
                        status: 'idle',
                        currentReqId: null,
                        pendingQuestions: [],
                        needsInputCount: 0
                      })
                      setSelectedNeedsInputReqId(null)
                    }}
                  >
                    Clear Results
                  </button>
                </div>
              )}

              {/* Question Panel for selected needs-input requirement */}
              {selectedNeedsInputItem && (
                <div className="question-panel-section">
                  <QuestionPanel
                    requirement={{
                      req_id: selectedNeedsInputItem.req_id,
                      title: selectedNeedsInputItem.requirement_text,
                      text: selectedNeedsInputItem.requirement_text
                    }}
                    questions={selectedNeedsInputItem.questions}
                    onAnswer={(questionId, answer) => {
                      // Individual answer handling if needed
                    }}
                    onSkip={handleSkipQuestion}
                    onSubmitAll={handleSubmitAnswers}
                    isSubmitting={isSubmittingAnswer}
                  />
                </div>
              )}
            </div>
          ) : selectedNeedsInputItem ? (
            // Show QuestionPanel when a needs-input requirement is selected (outside batch mode)
            <QuestionPanel
              requirement={{
                req_id: selectedNeedsInputItem.req_id,
                title: selectedNeedsInputItem.requirement_text,
                text: selectedNeedsInputItem.requirement_text
              }}
              questions={selectedNeedsInputItem.questions}
              onAnswer={(questionId, answer) => {}}
              onSkip={handleSkipQuestion}
              onSubmitAll={handleSubmitAnswers}
              isSubmitting={isSubmittingAnswer}
            />
          ) : (
            // Normal Detail Panel - pass merged requirement with batch results
            <ValidationDetailPanel
              requirement={selectedRequirement ? getMergedRequirement(selectedRequirement) : null}
              onValidationComplete={handleInlineValidationComplete}
              onValidationStart={handleValidationStart}
              onEnhanceRequirement={onEnhanceRequirement}
            />
          )}
        </div>
      </div>
    </div>
  )
}

export default ValidationTab
