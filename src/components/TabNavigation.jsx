import React from 'react'
import './TabNavigation.css'

const TabNavigation = ({ activeTab, setActiveTab }) => {
  const tabs = [
    { id: 'mining', label: 'Mining', icon: '⛏️' },
    { id: 'requirements', label: 'Requirements', icon: '📋' },
    { id: 'validation', label: 'Validation', icon: '✓' },
    { id: 'knowledge-graph', label: 'Knowledge Graph', icon: '🕸️' },
    { id: 'techstack', label: 'TechStack', icon: '🛠️' }
  ]

  return (
    <div className="tab-navigation">
      {tabs.map(tab => (
        <button
          key={tab.id}
          className={`tab-button ${activeTab === tab.id ? 'active' : ''}`}
          onClick={() => setActiveTab(tab.id)}
        >
          <span className="tab-icon">{tab.icon}</span>
          <span className="tab-label">{tab.label}</span>
        </button>
      ))}
    </div>
  )
}

export default TabNavigation
