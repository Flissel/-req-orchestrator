import React, { useState, useEffect } from 'react'
import './TechStackTab.css'

const API_BASE = ''

const TechStackTab = ({ requirements = [], onTemplateSelect }) => {
  const [templates, setTemplates] = useState([])
  const [selectedTemplate, setSelectedTemplate] = useState(null)
  const [projectName, setProjectName] = useState('')
  const [outputPath, setOutputPath] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [creating, setCreating] = useState(false)
  const [createResult, setCreateResult] = useState(null)
  const [filterCategory, setFilterCategory] = useState('all')
  
  // New Agent states
  const [detecting, setDetecting] = useState(false)
  const [detectionResult, setDetectionResult] = useState(null)
  const [kgStatus, setKgStatus] = useState(null)
  const [rebuildingKg, setRebuildingKg] = useState(false)
  const [pipelineResult, setPipelineResult] = useState(null)
  const [processingPipeline, setProcessingPipeline] = useState(false)
  const [activeTab, setActiveTab] = useState('templates') // templates | detect | pipeline | kg | projects

  // Projects state
  const [projects, setProjects] = useState([])
  const [projectsLoading, setProjectsLoading] = useState(false)
  const [selectedProject, setSelectedProject] = useState(null)

  // Multi-select merge state
  const [mergeMode, setMergeMode] = useState(false)
  const [selectedProjects, setSelectedProjects] = useState([])
  const [includeFailedReqs, setIncludeFailedReqs] = useState(false)
  const [sendingToEngine, setSendingToEngine] = useState(false)
  const [mergeResult, setMergeResult] = useState(null)

  // Load templates and KG status from backend
  useEffect(() => {
    loadTemplates()
    loadKgStatus()
  }, [])

  const loadTemplates = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch(`${API_BASE}/api/v1/techstack/templates`)
      if (!response.ok) throw new Error('Failed to load templates')
      const data = await response.json()
      setTemplates(data.templates || [])
    } catch (err) {
      setError(err.message)
      // Fallback: Load from static templates
      setTemplates(defaultTemplates)
    } finally {
      setLoading(false)
    }
  }

  const loadKgStatus = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/v1/techstack/kg/status`)
      if (response.ok) {
        const data = await response.json()
        setKgStatus(data)
      }
    } catch (err) {
      console.error('Failed to load KG status:', err)
    }
  }

  const loadProjects = async () => {
    setProjectsLoading(true)
    try {
      const response = await fetch(`${API_BASE}/api/v1/techstack/projects`)
      if (response.ok) {
        const data = await response.json()
        setProjects(data.projects || [])
      }
    } catch (err) {
      console.error('Failed to load projects:', err)
    } finally {
      setProjectsLoading(false)
    }
  }

  // Load projects when switching to projects tab
  useEffect(() => {
    if (activeTab === 'projects') {
      loadProjects()
    }
  }, [activeTab])

  // Toggle project selection for merge
  const toggleProjectSelection = (projectId) => {
    setSelectedProjects(prev => {
      if (prev.includes(projectId)) {
        return prev.filter(id => id !== projectId)
      } else {
        return [...prev, projectId]
      }
    })
  }

  // Calculate total requirements from selected projects
  const getSelectedRequirementsCount = () => {
    return selectedProjects.reduce((total, projectId) => {
      const project = projects.find(p => p.project_id === projectId)
      return total + (project?.requirements_count || 0)
    }, 0)
  }

  // Send selected projects to Coding Engine
  const sendToCodingEngine = async () => {
    if (selectedProjects.length === 0) return

    setSendingToEngine(true)
    setMergeResult(null)

    try {
      const response = await fetch(`${API_BASE}/api/v1/techstack/send-to-engine`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_ids: selectedProjects,
          include_failed: includeFailedReqs
        })
      })

      const result = await response.json()
      setMergeResult(result)

      if (result.success) {
        // Clear selection after successful send
        setSelectedProjects([])
        setMergeMode(false)
      }
    } catch (err) {
      setMergeResult({
        success: false,
        error: err.message
      })
    } finally {
      setSendingToEngine(false)
    }
  }

  // Cancel merge mode
  const cancelMergeMode = () => {
    setMergeMode(false)
    setSelectedProjects([])
    setMergeResult(null)
  }

  const handleAutoDetect = async () => {
    if (requirements.length === 0) {
      setDetectionResult({ error: 'No requirements loaded for detection' })
      return
    }

    setDetecting(true)
    setDetectionResult(null)

    try {
      const response = await fetch(`${API_BASE}/api/v1/techstack/detect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          requirements: requirements.map(r => ({
            req_id: r.req_id,
            title: r.title || r.original_text,
            description: r.description || r.enhanced_text || ''
          }))
        })
      })

      const result = await response.json()
      setDetectionResult(result)

      // Auto-select the recommended template
      if (result.recommended_template) {
        const template = templates.find(t => t.id === result.recommended_template)
        if (template) {
          setSelectedTemplate(template)
          setActiveTab('templates')
        }
      }
    } catch (err) {
      setDetectionResult({ error: err.message })
    } finally {
      setDetecting(false)
    }
  }

  const handleRebuildKg = async () => {
    setRebuildingKg(true)
    try {
      const response = await fetch(`${API_BASE}/api/v1/techstack/kg/rebuild`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ force: true })
      })
      const result = await response.json()
      if (result.success) {
        await loadKgStatus()
      }
    } catch (err) {
      console.error('Failed to rebuild KG:', err)
    } finally {
      setRebuildingKg(false)
    }
  }

  const handlePipelineProcess = async () => {
    if (requirements.length === 0) {
      setPipelineResult({ error: 'No requirements loaded for pipeline processing' })
      return
    }

    setProcessingPipeline(true)
    setPipelineResult(null)

    try {
      const response = await fetch(`${API_BASE}/api/v1/techstack/pipeline/process`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          requirements: requirements.map(r => ({
            req_id: r.req_id,
            title: r.title || r.original_text,
            description: r.description || r.enhanced_text || '',
            validation_passed: r.validation_passed
          })),
          auto_select: true
        })
      })

      const result = await response.json()
      setPipelineResult(result)

      // Auto-select the detected template
      if (result.selected_template) {
        const template = templates.find(t => t.id === result.selected_template)
        if (template) {
          setSelectedTemplate(template)
        }
      }
    } catch (err) {
      setPipelineResult({ error: err.message })
    } finally {
      setProcessingPipeline(false)
    }
  }

  const handleTemplateSelect = (template) => {
    setSelectedTemplate(template)
    setProjectName(template.placeholders?.PROJECT_NAME || 'my-project')
    setCreateResult(null)
  }

  const handleCreateProject = async () => {
    if (!selectedTemplate || !projectName.trim()) return

    setCreating(true)
    setCreateResult(null)

    try {
      const requestBody = {
        template_id: selectedTemplate.id,
        project_name: projectName.trim(),
        requirements: requirements.map(r => ({
          req_id: r.req_id,
          title: r.title,
          tag: r.tag
        }))
      }
      
      // Add output_path if specified
      if (outputPath.trim()) {
        requestBody.output_path = outputPath.trim()
      }

      const response = await fetch(`${API_BASE}/api/v1/techstack/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody)
      })

      const result = await response.json()
      if (result.success) {
        setCreateResult({
          success: true,
          message: `Project "${projectName}" created successfully!`,
          path: result.path
        })
        if (onTemplateSelect) {
          onTemplateSelect(selectedTemplate, result)
        }
      } else {
        throw new Error(result.error || 'Failed to create project')
      }
    } catch (err) {
      setCreateResult({
        success: false,
        message: err.message
      })
    } finally {
      setCreating(false)
    }
  }

  const categories = [
    { id: 'all', label: 'All', icon: '📚' },
    { id: 'web', label: 'Web', icon: '🌐' },
    { id: 'backend', label: 'Backend', icon: '⚙️' },
    { id: 'mobile', label: 'Mobile', icon: '📱' },
    { id: 'desktop', label: 'Desktop', icon: '🖥️' },
    { id: 'blockchain', label: 'Web3', icon: '⛓️' },
    { id: 'data-science', label: 'Data/ML', icon: '🤖' },
    { id: 'simulation', label: 'Simulation', icon: '🧪' },
    { id: 'systems', label: 'Systems', icon: '💾' },
    { id: 'iot', label: 'IoT', icon: '📡' }
  ]

  const filteredTemplates = filterCategory === 'all' 
    ? templates 
    : templates.filter(t => t.category === filterCategory)

  const getDifficultyColor = (difficulty) => {
    switch (difficulty) {
      case 'beginner': return '#10b981'
      case 'intermediate': return '#f59e0b'
      case 'advanced': return '#ef4444'
      default: return '#6b7280'
    }
  }

  return (
    <div className="techstack-tab">
      <div className="techstack-header">
        <h2>🛠️ TechStack Agent</h2>
        <p>AI-powered technology stack recommendation based on validated requirements</p>
      </div>

      {/* Requirements Summary */}
      {requirements.length > 0 && (
        <div className="requirements-summary">
          <span className="summary-badge">
            📋 {requirements.length} Requirements loaded
          </span>
          <span className="summary-badge validated">
            ✅ {requirements.filter(r => r.validation_passed).length} Validated
          </span>
        </div>
      )}

      {/* Agent Tabs */}
      <div className="agent-tabs">
        <button 
          className={`agent-tab ${activeTab === 'templates' ? 'active' : ''}`}
          onClick={() => setActiveTab('templates')}
        >
          📦 Templates
        </button>
        <button 
          className={`agent-tab ${activeTab === 'detect' ? 'active' : ''}`}
          onClick={() => setActiveTab('detect')}
        >
          🎯 Auto-Detect
        </button>
        <button 
          className={`agent-tab ${activeTab === 'pipeline' ? 'active' : ''}`}
          onClick={() => setActiveTab('pipeline')}
        >
          🔄 Pipeline
        </button>
        <button
          className={`agent-tab ${activeTab === 'kg' ? 'active' : ''}`}
          onClick={() => setActiveTab('kg')}
        >
          🧠 Knowledge Graph
        </button>
        <button
          className={`agent-tab ${activeTab === 'projects' ? 'active' : ''}`}
          onClick={() => setActiveTab('projects')}
        >
          📁 Projects
        </button>
      </div>

      {/* Auto-Detect Tab */}
      {activeTab === 'detect' && (
        <div className="detect-section">
          <div className="detect-panel">
            <h3>🎯 Automatic Template Detection</h3>
            <p>Analyze your requirements to find the best matching technology template.</p>
            
            <button 
              className="detect-btn"
              onClick={handleAutoDetect}
              disabled={detecting || requirements.length === 0}
            >
              {detecting ? '⏳ Analyzing...' : '🔍 Detect Best Template'}
            </button>

            {requirements.length === 0 && (
              <div className="detect-warning">
                ⚠️ Load requirements first to use auto-detection
              </div>
            )}

            {detectionResult && (
              <div className="detection-result">
                {detectionResult.error ? (
                  <div className="result-error">❌ {detectionResult.error}</div>
                ) : (
                  <>
                    <div className="result-recommended">
                      <h4>Recommended Template</h4>
                      <div className="recommended-template">
                        <span className="template-id">{detectionResult.recommended_template}</span>
                        <span className="confidence">
                          {(detectionResult.confidence * 100).toFixed(1)}% confidence
                        </span>
                      </div>
                    </div>

                    {detectionResult.reasons && (
                      <div className="result-reasons">
                        <h4>Detection Reasons</h4>
                        <ul>
                          {detectionResult.reasons.map((reason, idx) => (
                            <li key={idx}>{reason}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {detectionResult.alternatives && detectionResult.alternatives.length > 0 && (
                      <div className="result-alternatives">
                        <h4>Alternatives</h4>
                        {detectionResult.alternatives.map((alt, idx) => (
                          <div 
                            key={idx} 
                            className="alternative-item"
                            onClick={() => {
                              const template = templates.find(t => t.id === alt.template_id)
                              if (template) handleTemplateSelect(template)
                            }}
                          >
                            <span>{alt.template_id}</span>
                            <span className="alt-confidence">
                              {(alt.confidence * 100).toFixed(1)}%
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Pipeline Tab */}
      {activeTab === 'pipeline' && (
        <div className="pipeline-section">
          <div className="pipeline-panel">
            <h3>🔄 Full Pipeline Processing</h3>
            <p>Process validated requirements through the complete tech stack selection pipeline.</p>
            
            <div className="pipeline-flow">
              <div className="flow-step completed">📥 Extract</div>
              <div className="flow-arrow">→</div>
              <div className="flow-step completed">✨ Enhance</div>
              <div className="flow-arrow">→</div>
              <div className="flow-step completed">✅ Validate</div>
              <div className="flow-arrow">→</div>
              <div className="flow-step active">🛠️ Tech Stack</div>
            </div>

            <button 
              className="pipeline-btn"
              onClick={handlePipelineProcess}
              disabled={processingPipeline || requirements.length === 0}
            >
              {processingPipeline ? '⏳ Processing...' : '🚀 Run Pipeline'}
            </button>

            {pipelineResult && (
              <div className="pipeline-result">
                {pipelineResult.error ? (
                  <div className="result-error">❌ {pipelineResult.error}</div>
                ) : (
                  <>
                    <div className="result-header">
                      <span className="result-success">✅ Pipeline Completed</span>
                    </div>
                    
                    <div className="result-details">
                      <div className="detail-row">
                        <span>Selected Template:</span>
                        <strong>{pipelineResult.selected_template}</strong>
                      </div>
                      <div className="detail-row">
                        <span>Confidence:</span>
                        <strong>{(pipelineResult.confidence * 100).toFixed(1)}%</strong>
                      </div>
                      <div className="detail-row">
                        <span>KG Updated:</span>
                        <strong>{pipelineResult.kg_updated ? '✅' : '❌'}</strong>
                      </div>
                      <div className="detail-row">
                        <span>Traces Created:</span>
                        <strong>{pipelineResult.traces_created || 0}</strong>
                      </div>
                    </div>

                    {pipelineResult.transformed_requirements && (
                      <div className="transformed-requirements">
                        <h4>Transformed Requirements</h4>
                        <div className="transformed-list">
                          {pipelineResult.transformed_requirements.slice(0, 5).map((req, idx) => (
                            <div key={idx} className="transformed-item">
                              <span className="req-id">{req.req_id}</span>
                              <span className="req-title">{req.title}</span>
                              {req.tech_context && (
                                <span className="tech-context">{req.tech_context}</span>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Knowledge Graph Tab */}
      {activeTab === 'kg' && (
        <div className="kg-section">
          <div className="kg-panel">
            <h3>🧠 Knowledge Graph Status</h3>
            <p>Manage the technology stack knowledge graph for requirement tracing.</p>
            
            {kgStatus && (
              <div className="kg-status">
                <div className="status-row">
                  <span>Status:</span>
                  <span className={`status-badge ${kgStatus.status}`}>
                    {kgStatus.status === 'initialized' ? '✅ Initialized' : '⚠️ Not Initialized'}
                  </span>
                </div>
                {kgStatus.stats && (
                  <>
                    <div className="status-row">
                      <span>Templates Indexed:</span>
                      <strong>{kgStatus.stats.templates_indexed || 0}</strong>
                    </div>
                    <div className="status-row">
                      <span>Total Nodes:</span>
                      <strong>{kgStatus.stats.total_nodes || 0}</strong>
                    </div>
                    <div className="status-row">
                      <span>Requirement Traces:</span>
                      <strong>{kgStatus.stats.requirement_traces || 0}</strong>
                    </div>
                    {kgStatus.stats.last_updated && (
                      <div className="status-row">
                        <span>Last Updated:</span>
                        <strong>{new Date(kgStatus.stats.last_updated).toLocaleString()}</strong>
                      </div>
                    )}
                  </>
                )}
              </div>
            )}

            <div className="kg-actions">
              <button 
                className="rebuild-btn"
                onClick={handleRebuildKg}
                disabled={rebuildingKg}
              >
                {rebuildingKg ? '⏳ Rebuilding...' : '🔄 Rebuild Knowledge Graph'}
              </button>
              <button 
                className="refresh-btn"
                onClick={loadKgStatus}
              >
                🔃 Refresh Status
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Projects Tab */}
      {activeTab === 'projects' && (
        <div className="projects-section">
          <div className="projects-panel">
            <div className="projects-header">
              <h3>📁 Generated Projects</h3>
              <div className="header-actions">
                <button
                  className={`merge-toggle-btn ${mergeMode ? 'active' : ''}`}
                  onClick={() => {
                    if (mergeMode) {
                      cancelMergeMode()
                    } else {
                      setMergeMode(true)
                    }
                  }}
                >
                  {mergeMode ? '✕ Cancel Selection' : '☑ Select for Merge'}
                </button>
                <button className="refresh-btn" onClick={loadProjects} disabled={projectsLoading}>
                  {projectsLoading ? '⏳' : '🔃'} Refresh
                </button>
              </div>
            </div>
            <p>View all projects created from TechStack templates.</p>

            {projectsLoading && (
              <div className="loading-state">Loading projects...</div>
            )}

            {!projectsLoading && projects.length === 0 && (
              <div className="empty-state">
                <p>No projects created yet.</p>
                <p>Go to the Templates tab to create your first project.</p>
              </div>
            )}

            <div className="projects-list">
              {projects.map(project => (
                <div
                  key={project.project_id}
                  className={`project-card ${selectedProject?.project_id === project.project_id ? 'selected' : ''} ${mergeMode && selectedProjects.includes(project.project_id) ? 'merge-selected' : ''}`}
                  onClick={() => {
                    if (mergeMode) {
                      toggleProjectSelection(project.project_id)
                    } else {
                      setSelectedProject(selectedProject?.project_id === project.project_id ? null : project)
                    }
                  }}
                >
                  {/* Merge mode checkbox */}
                  {mergeMode && (
                    <div className="merge-checkbox">
                      <input
                        type="checkbox"
                        checked={selectedProjects.includes(project.project_id)}
                        onChange={() => toggleProjectSelection(project.project_id)}
                        onClick={(e) => e.stopPropagation()}
                      />
                    </div>
                  )}
                  <div className="project-header">
                    <h4>{project.project_name}</h4>
                    <span className="template-badge">{project.template_name || project.template_id}</span>
                  </div>

                  <div className="project-meta">
                    <span className="meta-item">
                      <span className="meta-icon">📋</span>
                      {project.requirements_count} Requirements
                    </span>
                    {project.template_category && (
                      <span className="meta-item">
                        <span className="meta-icon">📂</span>
                        {project.template_category}
                      </span>
                    )}
                    <span className="meta-item">
                      <span className="meta-icon">📅</span>
                      {new Date(project.created_at).toLocaleDateString()}
                    </span>
                  </div>

                  {project.tech_stack && project.tech_stack.length > 0 && (
                    <div className="project-tech-stack">
                      {project.tech_stack.slice(0, 4).map((tech, idx) => (
                        <span key={idx} className="tech-tag">{tech}</span>
                      ))}
                      {project.tech_stack.length > 4 && (
                        <span className="tech-tag more">+{project.tech_stack.length - 4}</span>
                      )}
                    </div>
                  )}

                  {project.validation_summary && (
                    <div className="project-validation">
                      <div className="validation-bar">
                        <div
                          className="validation-fill"
                          style={{
                            width: `${(project.validation_summary.passed / Math.max(project.validation_summary.total, 1)) * 100}%`
                          }}
                        />
                      </div>
                      <span className="validation-text">
                        {project.validation_summary.passed}/{project.validation_summary.total} passed
                        ({(project.validation_summary.avg_score * 100).toFixed(0)}% avg)
                      </span>
                    </div>
                  )}

                  {/* Expanded details */}
                  {selectedProject?.project_id === project.project_id && (
                    <div className="project-details">
                      <div className="detail-row">
                        <span className="detail-label">Project ID:</span>
                        <span className="detail-value">{project.project_id}</span>
                      </div>
                      <div className="detail-row">
                        <span className="detail-label">Path:</span>
                        <span className="detail-value path">{project.project_path}</span>
                      </div>
                      {project.source_file && (
                        <div className="detail-row">
                          <span className="detail-label">Source:</span>
                          <span className="detail-value">{project.source_file}</span>
                        </div>
                      )}
                      <div className="detail-row">
                        <span className="detail-label">Created:</span>
                        <span className="detail-value">
                          {new Date(project.created_at).toLocaleString()}
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* Merge Action Bar */}
            {mergeMode && selectedProjects.length > 0 && (
              <div className="merge-action-bar">
                <div className="merge-summary">
                  <span className="selected-count">
                    {selectedProjects.length} project{selectedProjects.length !== 1 ? 's' : ''} selected
                  </span>
                  <span className="req-count">
                    ({getSelectedRequirementsCount()} requirements)
                  </span>
                </div>

                <div className="merge-options">
                  <label className="include-failed-label">
                    <input
                      type="checkbox"
                      checked={includeFailedReqs}
                      onChange={(e) => setIncludeFailedReqs(e.target.checked)}
                    />
                    Include failed requirements
                  </label>
                </div>

                <div className="merge-actions">
                  <button className="cancel-btn" onClick={cancelMergeMode}>
                    Cancel
                  </button>
                  <button
                    className="send-btn"
                    onClick={sendToCodingEngine}
                    disabled={sendingToEngine}
                  >
                    {sendingToEngine ? '⏳ Sending...' : '🚀 Send to Coding Engine'}
                  </button>
                </div>
              </div>
            )}

            {/* Merge Result */}
            {mergeResult && (
              <div className={`merge-result ${mergeResult.success ? 'success' : 'error'}`}>
                {mergeResult.success ? (
                  <>
                    <span className="result-icon">✅</span>
                    <span className="result-text">
                      Successfully sent {mergeResult.requirements_sent} requirements from {mergeResult.projects_sent} projects to Coding Engine
                    </span>
                  </>
                ) : (
                  <>
                    <span className="result-icon">❌</span>
                    <span className="result-text">
                      {mergeResult.error || 'Failed to send to Coding Engine'}
                    </span>
                  </>
                )}
                <button className="dismiss-btn" onClick={() => setMergeResult(null)}>✕</button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Templates Tab */}
      {activeTab === 'templates' && (
        <>
          {/* Category Filter */}
          <div className="category-filter">
            {categories.map(cat => (
              <button
                key={cat.id}
                className={`category-btn ${filterCategory === cat.id ? 'active' : ''}`}
                onClick={() => setFilterCategory(cat.id)}
              >
                <span>{cat.icon}</span>
                <span>{cat.label}</span>
              </button>
            ))}
          </div>

          <div className="techstack-content">
            {/* Templates Grid */}
            <div className="templates-section">
              <h3>Available Templates ({filteredTemplates.length})</h3>
              
              {loading && (
                <div className="loading-state">Loading templates...</div>
              )}

              {error && (
                <div className="error-state">
                  ⚠️ {error}
                  <button onClick={loadTemplates}>Retry</button>
                </div>
              )}

              <div className="templates-grid">
                {filteredTemplates.map(template => (
                  <div 
                    key={template.id}
                    className={`template-card ${selectedTemplate?.id === template.id ? 'selected' : ''}`}
                    onClick={() => handleTemplateSelect(template)}
                  >
                    <div className="template-header">
                      <h4>{template.name}</h4>
                      <span 
                        className="difficulty-badge"
                        style={{ color: getDifficultyColor(template.difficulty) }}
                      >
                        {template.difficulty}
                      </span>
                    </div>
                    <p className="template-description">{template.description}</p>
                    <div className="template-tags">
                      {template.tags?.slice(0, 4).map(tag => (
                        <span key={tag} className="tag">{tag}</span>
                      ))}
                    </div>
                    <div className="template-footer">
                      <span className="setup-time">⏱️ {template.estimated_setup_time}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Selected Template Details */}
            {selectedTemplate && (
              <div className="template-details">
                <h3>📦 {selectedTemplate.name}</h3>
                
                <div className="detail-section">
                  <h4>Tech Stack</h4>
                  <div className="tech-stack-grid">
                    {selectedTemplate.tech_stack?.frontend && (
                      <div className="stack-item">
                        <span className="stack-label">Frontend</span>
                        <span className="stack-value">
                          {selectedTemplate.tech_stack.frontend.framework || 'N/A'}
                        </span>
                      </div>
                    )}
                    {selectedTemplate.tech_stack?.backend && (
                      <div className="stack-item">
                        <span className="stack-label">Backend</span>
                        <span className="stack-value">
                          {selectedTemplate.tech_stack.backend.framework || 
                           selectedTemplate.tech_stack.backend.language || 'N/A'}
                        </span>
                      </div>
                    )}
                    {selectedTemplate.tech_stack?.database && (
                      <div className="stack-item">
                        <span className="stack-label">Database</span>
                        <span className="stack-value">
                          {selectedTemplate.tech_stack.database.primary || 'N/A'}
                        </span>
                      </div>
                    )}
                  </div>
                </div>

                <div className="detail-section">
                  <h4>Features</h4>
                  <ul className="features-list">
                    {selectedTemplate.features?.map((feature, idx) => (
                      <li key={idx}>✓ {feature}</li>
                    ))}
                  </ul>
                </div>

                <div className="detail-section">
                  <h4>Prerequisites</h4>
                  <ul className="prereq-list">
                    {selectedTemplate.prerequisites?.map((prereq, idx) => (
                      <li key={idx}>• {prereq}</li>
                    ))}
                  </ul>
                </div>

                <div className="create-section">
                  <h4>Create Project</h4>
                  <div className="create-form">
                    <input
                      type="text"
                      value={projectName}
                      onChange={(e) => setProjectName(e.target.value)}
                      placeholder="Project name"
                      className="project-name-input"
                    />
                    <input
                      type="text"
                      value={outputPath}
                      onChange={(e) => setOutputPath(e.target.value)}
                      placeholder="Output path (optional, e.g. C:/Dev/Projects)"
                      className="output-path-input"
                    />
                    <button 
                      className="create-btn"
                      onClick={handleCreateProject}
                      disabled={creating || !projectName.trim()}
                    >
                      {creating ? '⏳ Creating...' : '🚀 Create Project'}
                    </button>
                  </div>

                  {createResult && (
                    <div className={`create-result ${createResult.success ? 'success' : 'error'}`}>
                      {createResult.success ? '✅' : '❌'} {createResult.message}
                      {createResult.path && (
                        <div className="result-path">
                          📁 {createResult.path}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}

// Default templates as fallback
const defaultTemplates = [
  {
    id: '01-web-app',
    name: 'Web App (Next.js)',
    description: 'Full-stack Web-App mit Next.js 14, Prisma ORM und Tailwind CSS.',
    category: 'web',
    tags: ['nextjs', 'react', 'prisma', 'tailwind'],
    difficulty: 'intermediate',
    estimated_setup_time: '10 minutes',
    tech_stack: {
      frontend: { framework: 'Next.js 14' },
      backend: { framework: 'Next.js API Routes' },
      database: { primary: 'PostgreSQL' }
    },
    features: ['Server Components', 'API Routes', 'Prisma ORM', 'Tailwind CSS'],
    prerequisites: ['Node.js 20+', 'Docker'],
    placeholders: { PROJECT_NAME: 'my-webapp' }
  },
  {
    id: '02-api-service',
    name: 'API Service (FastAPI)',
    description: 'REST API Service mit FastAPI, SQLAlchemy und PostgreSQL.',
    category: 'backend',
    tags: ['fastapi', 'python', 'postgresql', 'rest'],
    difficulty: 'intermediate',
    estimated_setup_time: '10 minutes',
    tech_stack: {
      backend: { framework: 'FastAPI', language: 'Python 3.12' },
      database: { primary: 'PostgreSQL' }
    },
    features: ['Async Support', 'OpenAPI Docs', 'SQLAlchemy ORM', 'Docker Ready'],
    prerequisites: ['Python 3.12+', 'Docker'],
    placeholders: { PROJECT_NAME: 'my-api' }
  },
  {
    id: '03-desktop-electron',
    name: 'Desktop App (Electron)',
    description: 'Cross-platform Desktop-App mit Electron und Python Backend.',
    category: 'desktop',
    tags: ['electron', 'python', 'desktop', 'cross-platform'],
    difficulty: 'intermediate',
    estimated_setup_time: '10 minutes',
    tech_stack: {
      frontend: { framework: 'Electron', ui: 'React' },
      backend: { language: 'Python (optional)' },
      database: { primary: 'SQLite' }
    },
    features: ['Cross-Platform', 'Native APIs', 'Auto-Updates', 'IPC Communication'],
    prerequisites: ['Node.js 20+', 'Python 3.12+'],
    placeholders: { PROJECT_NAME: 'my-desktop-app' }
  },
  {
    id: '04-mobile-expo',
    name: 'Mobile App (Expo)',
    description: 'Cross-platform Mobile App für iOS und Android mit Expo.',
    category: 'mobile',
    tags: ['expo', 'react-native', 'mobile', 'ios', 'android'],
    difficulty: 'intermediate',
    estimated_setup_time: '5 minutes',
    tech_stack: {
      frontend: { framework: 'Expo SDK 51' },
      database: { local: 'Expo SQLite' }
    },
    features: ['iOS + Android', 'Expo Go Testing', 'OTA Updates', 'Native APIs'],
    prerequisites: ['Node.js 20+', 'Expo Go App'],
    placeholders: { PROJECT_NAME: 'my-mobile-app' }
  }
]

export default TechStackTab