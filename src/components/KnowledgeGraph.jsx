import { useEffect, useRef } from 'react'

export default function KnowledgeGraph({ data, requirements }) {
  const cyRef = useRef(null)
  const cyInstance = useRef(null)

  const stats = {
    nodes: data.nodes?.length || 0,
    edges: data.edges?.length || 0,
    requirements: requirements?.length || 0,
    tags: new Set(requirements?.map(r => r.tag).filter(Boolean)).size || 0
  }

  useEffect(() => {
    if (!cyRef.current || stats.nodes === 0) return

    // Load cytoscape dynamically
    if (typeof window !== 'undefined' && !window.cytoscape) {
      const script = document.createElement('script')
      script.src = 'https://unpkg.com/cytoscape@3.26.0/dist/cytoscape.min.js'
      script.onload = () => initGraph()
      document.head.appendChild(script)
    } else if (window.cytoscape) {
      initGraph()
    }

    function initGraph() {
      if (cyInstance.current) {
        cyInstance.current.destroy()
      }

      const elements = {
        nodes: data.nodes.map(n => ({
          data: {
            id: n.id || n.node_id,
            name: n.name,
            type: n.type,
            ...n.payload
          }
        })),
        edges: data.edges.map(e => ({
          data: {
            id: e.id || e.edge_id,
            source: e.from || e.from_node_id,
            target: e.to || e.to_node_id,
            rel: e.rel,
            ...e.payload
          }
        }))
      }

      cyInstance.current = window.cytoscape({
        container: cyRef.current,
        elements: elements,
        style: [
          {
            selector: 'node',
            style: {
              'label': 'data(name)',
              'color': '#e6e6e6',
              'background-color': '#4cc9f0',
              'font-size': '10px',
              'text-wrap': 'wrap',
              'text-max-width': '100px',
              'text-valign': 'center',
              'text-halign': 'center',
              'width': '60px',
              'height': '60px'
            }
          },
          {
            selector: 'node[type="Requirement"]',
            style: {
              'shape': 'round-rectangle',
              'background-color': '#38bdf8',
              'width': '80px',
              'height': '50px'
            }
          },
          {
            selector: 'node[type="Tag"]',
            style: {
              'shape': 'hexagon',
              'background-color': '#60a5fa'
            }
          },
          {
            selector: 'node[type="Actor"]',
            style: {
              'shape': 'ellipse',
              'background-color': '#a78bfa'
            }
          },
          {
            selector: 'node[type="Action"]',
            style: {
              'shape': 'diamond',
              'background-color': '#22c55e'
            }
          },
          {
            selector: 'node[type="Entity"]',
            style: {
              'shape': 'round-rectangle',
              'background-color': '#f59e0b'
            }
          },
          {
            selector: 'edge',
            style: {
              'width': 2,
              'line-color': '#64748b',
              'target-arrow-color': '#64748b',
              'target-arrow-shape': 'triangle',
              'label': 'data(rel)',
              'font-size': '8px',
              'color': '#94a3b8',
              'curve-style': 'bezier',
              'text-rotation': 'autorotate'
            }
          }
        ],
        layout: {
          name: 'cose',
          animate: false,
          padding: 30,
          nodeRepulsion: 8000,
          idealEdgeLength: 100
        }
      })

      // Add click handler
      cyInstance.current.on('tap', 'node', (evt) => {
        const node = evt.target
        console.log('Node clicked:', node.data())
      })
    }

    return () => {
      if (cyInstance.current) {
        cyInstance.current.destroy()
      }
    }
  }, [data])

  const handleFit = () => {
    if (cyInstance.current) {
      cyInstance.current.fit(null, 50)
    }
  }

  const handleExportPNG = () => {
    if (cyInstance.current) {
      const png = cyInstance.current.png({ full: true, scale: 2 })
      const link = document.createElement('a')
      link.download = 'knowledge-graph.png'
      link.href = png
      link.click()
    }
  }

  return (
    <div className="kg-panel">
      <h2>🕸️ Knowledge Graph</h2>

      <div className="kg-stats">
        <div className="stat-card">
          <div className="stat-number">{stats.nodes}</div>
          <div className="stat-label">Knoten</div>
        </div>
        <div className="stat-card">
          <div className="stat-number">{stats.edges}</div>
          <div className="stat-label">Kanten</div>
        </div>
        <div className="stat-card">
          <div className="stat-number">{stats.requirements}</div>
          <div className="stat-label">Requirements</div>
        </div>
        <div className="stat-card">
          <div className="stat-number">{stats.tags}</div>
          <div className="stat-label">Tags</div>
        </div>
      </div>

      <div className="kg-controls">
        <button className="btn btn-sm" onClick={handleFit} disabled={stats.nodes === 0}>
          🎯 Fit View
        </button>
        <button className="btn btn-sm" onClick={handleExportPNG} disabled={stats.nodes === 0}>
          📷 Export PNG
        </button>
      </div>

      <div className="kg-container" ref={cyRef} style={{
        width: '100%',
        height: '400px',
        background: '#0d1220',
        border: '1px solid #1f2937',
        borderRadius: '12px',
        marginTop: '12px'
      }}>
        {stats.nodes === 0 && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
            color: '#64748b'
          }}>
            Noch kein Knowledge Graph vorhanden
          </div>
        )}
      </div>

      {stats.nodes > 0 && (
        <div className="kg-legend">
          <strong>Knoten-Typen:</strong>
          {Array.from(new Set(data.nodes.map(n => n.type))).map(type => (
            <span key={type} className="legend-item">{type}</span>
          ))}
        </div>
      )}
    </div>
  )
}
