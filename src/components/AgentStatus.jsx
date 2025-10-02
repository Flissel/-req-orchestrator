export default function AgentStatus({ agents }) {
  const agentConfig = {
    planner: { icon: '📋', name: 'Planner Agent' },
    solver: { icon: '🔍', name: 'Solver Agent' },
    verifier: { icon: '✅', name: 'Verifier Agent' },
    kg: { icon: '🕸️', name: 'Knowledge Graph Agent' },
    'chunk-miner': { icon: '⛏️', name: 'Chunk Miner Agent' }
  }

  return (
    <div className="agents-grid">
      {Object.entries(agents).map(([key, agent]) => (
        <div key={key} className={`agent-card ${agent.status}`}>
          <div className="agent-name">
            {agentConfig[key]?.icon} {agentConfig[key]?.name}
          </div>
          <div className="agent-message">{agent.message}</div>
        </div>
      ))}
    </div>
  )
}