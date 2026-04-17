import { useState, useEffect } from 'react'
import './LogViewer.css'

const LEVEL_CONFIG = {
  DEBUG: { color: 'var(--text-tertiary)',    bg: 'transparent' },
  INFO:  { color: 'var(--accent-blue)',      bg: 'var(--accent-blue-dim)' },
  WARN:  { color: 'var(--accent-amber)',     bg: 'var(--accent-amber-dim)' },
  ERROR: { color: 'var(--accent-magenta)',   bg: 'var(--accent-magenta-dim)' },
  FATAL: { color: '#ff3366',                 bg: 'rgba(255, 51, 102, 0.15)' },
}

export default function LogViewer({ selectedService, apiBase, services }) {
  const [logs, setLogs] = useState([])
  const [filterLevel, setFilterLevel] = useState('')
  const [loading, setLoading] = useState(false)
  const [service, setService] = useState(selectedService)

  useEffect(() => {
    setService(selectedService)
  }, [selectedService])

  useEffect(() => {
    if (!service) return
    setLoading(true)

    const params = new URLSearchParams({ limit: '200' })
    if (filterLevel) params.set('level', filterLevel)

    fetch(`${apiBase}/logs/${service}?${params}`)
      .then(res => res.json())
      .then(data => setLogs(data.logs || []))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [service, filterLevel, apiBase])

  return (
    <div className="panel log-panel">
      <div className="panel__header">
        <span className="panel__title">
          <span className="panel__title-icon">📝</span>
          <span>Logs</span>
          <span className="panel__title-service mono">{service}</span>
        </span>
      </div>

      {/* Filters */}
      <div className="log-filters">
        <select
          className="log-filter-select"
          value={service}
          onChange={e => setService(e.target.value)}
        >
          {(services || []).map(s => (
            <option key={s.id} value={s.id}>{s.id}</option>
          ))}
        </select>

        <div className="log-level-filters">
          <button
            className={`log-level-btn ${filterLevel === '' ? 'active' : ''}`}
            onClick={() => setFilterLevel('')}
          >
            All
          </button>
          {['INFO', 'WARN', 'ERROR', 'FATAL'].map(level => (
            <button
              key={level}
              className={`log-level-btn ${filterLevel === level ? 'active' : ''}`}
              onClick={() => setFilterLevel(level)}
              style={{ '--level-color': LEVEL_CONFIG[level]?.color }}
            >
              {level}
            </button>
          ))}
        </div>
      </div>

      {/* Log entries */}
      <div className="log-entries">
        {loading ? (
          <div className="loading-overlay"><span className="spinner"></span></div>
        ) : logs.length === 0 ? (
          <div className="loading-overlay">No logs found</div>
        ) : (
          logs.slice(-100).map((log, i) => {
            const levelCfg = LEVEL_CONFIG[log.level] || LEVEL_CONFIG.INFO
            const isError = log.level === 'ERROR' || log.level === 'FATAL'

            return (
              <div
                key={i}
                className={`log-entry ${isError ? 'log-entry--error' : ''}`}
              >
                <span className="log-entry__time mono">
                  {log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : ''}
                </span>
                <span
                  className="log-entry__level"
                  style={{ color: levelCfg.color, background: levelCfg.bg }}
                >
                  {log.level}
                </span>
                <span className="log-entry__message mono">{log.message}</span>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
