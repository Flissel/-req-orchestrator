import { useState, useEffect } from 'react'

const API_BASE = ''

export default function ProjectSelectorModal({ isOpen, onClose, onSelect }) {
  const [sources, setSources] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedSource, setSelectedSource] = useState(null)

  useEffect(() => {
    if (isOpen) {
      fetchSources()
    }
  }, [isOpen])

  const fetchSources = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch(`${API_BASE}/api/v1/manifest/sources`)
      const data = await response.json()
      
      if (data.sources) {
        setSources(data.sources)
      } else {
        setSources([])
      }
    } catch (err) {
      console.error('[ProjectSelectorModal] Failed to fetch sources:', err)
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleSelect = () => {
    if (selectedSource) {
      onSelect(selectedSource)
      onClose()
    }
  }

  const handleLoadAll = () => {
    onSelect(null) // null = load all
    onClose()
  }

  if (!isOpen) return null

  return (
    <div 
      className="modal-overlay" 
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0, 0, 0, 0.7)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        backdropFilter: 'blur(4px)'
      }}
    >
      <div 
        className="modal-content project-selector-modal"
        onClick={e => e.stopPropagation()}
        style={{
          background: '#1e293b',
          borderRadius: '12px',
          padding: '24px',
          maxWidth: '600px',
          width: '90%',
          maxHeight: '80vh',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column'
        }}
      >
        <div className="modal-header" style={{ marginBottom: '16px' }}>
          <h2 style={{ margin: 0, color: '#38bdf8', fontSize: '20px' }}>
            🗄️ Projekt auswählen
          </h2>
          <p style={{ margin: '8px 0 0', color: '#94a3b8', fontSize: '14px' }}>
            Wähle ein Projekt/Datei aus, um die zugehörigen Requirements zu laden
          </p>
        </div>

        <div className="modal-body" style={{ flex: 1, overflowY: 'auto', marginBottom: '16px' }}>
          {loading && (
            <div style={{ textAlign: 'center', padding: '40px', color: '#94a3b8' }}>
              ⏳ Lade Projekte...
            </div>
          )}

          {error && (
            <div style={{ textAlign: 'center', padding: '40px', color: '#ef4444' }}>
              ❌ Fehler: {error}
            </div>
          )}

          {!loading && !error && sources.length === 0 && (
            <div style={{ textAlign: 'center', padding: '40px', color: '#94a3b8' }}>
              📭 Keine Projekte in der Datenbank gefunden
            </div>
          )}

          {!loading && !error && sources.length > 0 && (
            <div className="sources-list" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {sources.map((source, idx) => (
                <div
                  key={idx}
                  className={`source-item ${selectedSource?.source_file === source.source_file ? 'selected' : ''}`}
                  onClick={() => setSelectedSource(source)}
                  style={{
                    padding: '12px 16px',
                    borderRadius: '8px',
                    border: selectedSource?.source_file === source.source_file 
                      ? '2px solid #38bdf8' 
                      : '1px solid #334155',
                    background: selectedSource?.source_file === source.source_file 
                      ? 'rgba(56, 189, 248, 0.1)' 
                      : '#0f172a',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <div style={{ fontWeight: '600', color: '#e2e8f0', fontSize: '14px' }}>
                        📄 {source.source_file}
                      </div>
                      <div style={{ fontSize: '12px', color: '#64748b', marginTop: '4px' }}>
                        {source.source_type} • {new Date(source.last_created).toLocaleDateString('de-DE')}
                      </div>
                    </div>
                    <div style={{ 
                      background: '#334155', 
                      padding: '4px 12px', 
                      borderRadius: '12px',
                      fontSize: '13px',
                      fontWeight: '600',
                      color: '#38bdf8'
                    }}>
                      {source.requirement_count} Req.
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="modal-footer" style={{ 
          display: 'flex', 
          gap: '12px', 
          justifyContent: 'flex-end',
          borderTop: '1px solid #334155',
          paddingTop: '16px'
        }}>
          <button
            onClick={handleLoadAll}
            style={{
              padding: '10px 20px',
              borderRadius: '6px',
              border: '1px solid #64748b',
              background: 'transparent',
              color: '#94a3b8',
              cursor: 'pointer',
              fontSize: '14px'
            }}
          >
            Alle laden ({sources.reduce((sum, s) => sum + s.requirement_count, 0)})
          </button>
          <button
            onClick={onClose}
            style={{
              padding: '10px 20px',
              borderRadius: '6px',
              border: '1px solid #64748b',
              background: 'transparent',
              color: '#94a3b8',
              cursor: 'pointer',
              fontSize: '14px'
            }}
          >
            Abbrechen
          </button>
          <button
            onClick={handleSelect}
            disabled={!selectedSource}
            style={{
              padding: '10px 20px',
              borderRadius: '6px',
              border: 'none',
              background: selectedSource ? '#38bdf8' : '#334155',
              color: selectedSource ? '#0f172a' : '#64748b',
              cursor: selectedSource ? 'pointer' : 'not-allowed',
              fontWeight: '600',
              fontSize: '14px'
            }}
          >
            Projekt laden
          </button>
        </div>
      </div>
    </div>
  )
}