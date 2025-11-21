import { useState, useEffect } from 'react'

export default function ValidationAnalytics({ days = 30 }) {
  const [analytics, setAnalytics] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchAnalytics()
  }, [days])

  const fetchAnalytics = async () => {
    setLoading(true)
    setError(null)

    try {
      const response = await fetch(`/api/v1/validation/analytics?days=${days}`)
      const data = await response.json()

      if (!response.ok || !data.success) {
        throw new Error(data.message || 'Failed to fetch analytics')
      }

      setAnalytics(data.analytics)
    } catch (err) {
      console.error('[ValidationAnalytics] Error:', err)
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="card">
        <h2>📊 Validation Analytics (Last {days} Days)</h2>
        <div style={{ padding: '40px', textAlign: 'center', color: 'var(--muted)' }}>
          Loading analytics...
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="card">
        <h2>📊 Validation Analytics (Last {days} Days)</h2>
        <div style={{ padding: '20px', color: '#f44336' }}>
          ❌ Error: {error}
        </div>
      </div>
    )
  }

  if (!analytics || analytics.total_validations === 0) {
    return (
      <div className="card">
        <h2>📊 Validation Analytics (Last {days} Days)</h2>
        <div style={{ padding: '20px', textAlign: 'center', color: 'var(--muted)' }}>
          No validation data available for the selected period.
        </div>
      </div>
    )
  }

  const passRate = analytics.total_validations > 0
    ? ((analytics.passed_count / analytics.total_validations) * 100).toFixed(1)
    : 0

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <h2>📊 Validation Analytics</h2>
        <div style={{ fontSize: '13px', color: 'var(--muted)' }}>
          Last {days} days
        </div>
      </div>

      {/* Summary Statistics */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
        gap: '15px',
        marginBottom: '20px'
      }}>
        {/* Total Validations */}
        <div style={{
          padding: '15px',
          background: 'var(--bg-secondary)',
          borderRadius: '8px',
          border: '1px solid var(--border)'
        }}>
          <div style={{ fontSize: '12px', color: 'var(--muted)', marginBottom: '5px', fontWeight: '600' }}>
            Total Validations
          </div>
          <div style={{ fontSize: '28px', fontWeight: '700', color: 'var(--primary)' }}>
            {analytics.total_validations}
          </div>
        </div>

        {/* Pass Rate */}
        <div style={{
          padding: '15px',
          background: 'var(--bg-secondary)',
          borderRadius: '8px',
          border: '1px solid var(--border)'
        }}>
          <div style={{ fontSize: '12px', color: 'var(--muted)', marginBottom: '5px', fontWeight: '600' }}>
            Pass Rate
          </div>
          <div style={{ fontSize: '28px', fontWeight: '700', color: passRate >= 70 ? '#4caf50' : '#f44336' }}>
            {passRate}%
          </div>
          <div style={{ fontSize: '11px', color: 'var(--muted)', marginTop: '2px' }}>
            {analytics.passed_count} passed / {analytics.failed_count} failed
          </div>
        </div>

        {/* Average Final Score */}
        <div style={{
          padding: '15px',
          background: 'var(--bg-secondary)',
          borderRadius: '8px',
          border: '1px solid var(--border)'
        }}>
          <div style={{ fontSize: '12px', color: 'var(--muted)', marginBottom: '5px', fontWeight: '600' }}>
            Avg Final Score
          </div>
          <div style={{ fontSize: '28px', fontWeight: '700', color: 'var(--primary)' }}>
            {analytics.avg_final_score !== null ? (analytics.avg_final_score * 100).toFixed(0) : 'N/A'}
            {analytics.avg_final_score !== null && '%'}
          </div>
        </div>

        {/* Average Improvement */}
        <div style={{
          padding: '15px',
          background: 'var(--bg-secondary)',
          borderRadius: '8px',
          border: '1px solid var(--border)'
        }}>
          <div style={{ fontSize: '12px', color: 'var(--muted)', marginBottom: '5px', fontWeight: '600' }}>
            Avg Improvement
          </div>
          <div style={{ fontSize: '28px', fontWeight: '700', color: '#4caf50' }}>
            {analytics.avg_improvement !== null ? '+' + (analytics.avg_improvement * 100).toFixed(0) : 'N/A'}
            {analytics.avg_improvement !== null && '%'}
          </div>
        </div>

        {/* Average Fixes */}
        <div style={{
          padding: '15px',
          background: 'var(--bg-secondary)',
          borderRadius: '8px',
          border: '1px solid var(--border)'
        }}>
          <div style={{ fontSize: '12px', color: 'var(--muted)', marginBottom: '5px', fontWeight: '600' }}>
            Avg Fixes per Validation
          </div>
          <div style={{ fontSize: '28px', fontWeight: '700', color: 'var(--primary)' }}>
            {analytics.avg_fixes !== null ? analytics.avg_fixes.toFixed(1) : 'N/A'}
          </div>
        </div>

        {/* Average Iterations */}
        <div style={{
          padding: '15px',
          background: 'var(--bg-secondary)',
          borderRadius: '8px',
          border: '1px solid var(--border)'
        }}>
          <div style={{ fontSize: '12px', color: 'var(--muted)', marginBottom: '5px', fontWeight: '600' }}>
            Avg Iterations
          </div>
          <div style={{ fontSize: '28px', fontWeight: '700', color: 'var(--primary)' }}>
            {analytics.avg_iterations !== null ? analytics.avg_iterations.toFixed(1) : 'N/A'}
          </div>
        </div>

        {/* Average Latency */}
        <div style={{
          padding: '15px',
          background: 'var(--bg-secondary)',
          borderRadius: '8px',
          border: '1px solid var(--border)'
        }}>
          <div style={{ fontSize: '12px', color: 'var(--muted)', marginBottom: '5px', fontWeight: '600' }}>
            Avg Processing Time
          </div>
          <div style={{ fontSize: '28px', fontWeight: '700', color: 'var(--primary)' }}>
            {analytics.avg_latency_ms !== null ? (analytics.avg_latency_ms / 1000).toFixed(1) : 'N/A'}
            {analytics.avg_latency_ms !== null && 's'}
          </div>
        </div>
      </div>

      {/* Most Common Failing Criteria */}
      {analytics.failing_criteria && analytics.failing_criteria.length > 0 && (
        <div>
          <h3 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '12px', marginTop: '20px' }}>
            Most Common Failing Criteria
          </h3>
          <div style={{
            background: 'var(--bg-secondary)',
            borderRadius: '8px',
            border: '1px solid var(--border)',
            overflow: 'hidden'
          }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: 'var(--bg)', borderBottom: '1px solid var(--border)' }}>
                  <th style={{ padding: '12px', textAlign: 'left', fontSize: '12px', fontWeight: '600', color: 'var(--muted)' }}>
                    Criterion
                  </th>
                  <th style={{ padding: '12px', textAlign: 'right', fontSize: '12px', fontWeight: '600', color: 'var(--muted)' }}>
                    Fix Count
                  </th>
                  <th style={{ padding: '12px', textAlign: 'right', fontSize: '12px', fontWeight: '600', color: 'var(--muted)' }}>
                    Avg Improvement
                  </th>
                </tr>
              </thead>
              <tbody>
                {analytics.failing_criteria.map((criterion, idx) => (
                  <tr key={idx} style={{ borderBottom: idx < analytics.failing_criteria.length - 1 ? '1px solid var(--border)' : 'none' }}>
                    <td style={{ padding: '12px', fontSize: '13px', fontWeight: '500' }}>
                      {criterion.criterion}
                    </td>
                    <td style={{ padding: '12px', textAlign: 'right', fontSize: '13px', fontWeight: '600', color: 'var(--primary)' }}>
                      {criterion.fix_count}
                    </td>
                    <td style={{ padding: '12px', textAlign: 'right', fontSize: '13px', fontWeight: '600', color: '#4caf50' }}>
                      +{(criterion.avg_improvement * 100).toFixed(0)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Refresh Button */}
      <div style={{ marginTop: '20px', textAlign: 'right' }}>
        <button
          onClick={() => fetchAnalytics()}
          style={{
            padding: '8px 16px',
            borderRadius: '6px',
            border: '1px solid var(--border)',
            background: 'var(--bg)',
            color: 'var(--text)',
            cursor: 'pointer',
            fontSize: '13px',
            fontWeight: '500'
          }}
        >
          🔄 Refresh
        </button>
      </div>
    </div>
  )
}
