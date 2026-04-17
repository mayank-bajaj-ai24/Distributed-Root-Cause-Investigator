import { useMemo } from 'react'
import './Dashboard.css'

const STATUS_CONFIG = {
  healthy:  { color: 'var(--status-healthy)',  label: 'Healthy',  icon: '✓' },
  warning:  { color: 'var(--status-warning)',  label: 'Warning',  icon: '⚠' },
  critical: { color: 'var(--status-critical)', label: 'Critical', icon: '✕' },
}

export default function Dashboard({ services, onSelectService }) {
  const grouped = useMemo(() => {
    const critical = services.filter(s => s.status === 'critical')
    const warning  = services.filter(s => s.status === 'warning')
    const healthy  = services.filter(s => s.status === 'healthy')
    return [...critical, ...warning, ...healthy]
  }, [services])

  if (!services.length) {
    return (
      <div className="panel">
        <div className="panel__header">
          <span className="panel__title"><span className="panel__title-icon">📊</span> Service Overview</span>
        </div>
        <div className="loading-overlay">
          <span className="spinner"></span> Loading services...
        </div>
      </div>
    )
  }

  const counts = {
    healthy:  services.filter(s => s.status === 'healthy').length,
    warning:  services.filter(s => s.status === 'warning').length,
    critical: services.filter(s => s.status === 'critical').length,
  }

  return (
    <div className="w-full h-full flex flex-col">
      <div className="flex items-center justify-between mb-4 pb-2 border-b border-outline-variant/10">
        <span className="font-headline font-bold text-sm uppercase tracking-widest text-on-surface">
          <span className="mr-2">📊</span> Service Overview
        </span>
        <div className="flex gap-3 text-xs font-label">
          <span className="text-tertiary">{counts.healthy} healthy</span>
          <span className="text-[#FF6B00]">{counts.warning} degraded</span>
          <span className="text-error">{counts.critical} critical</span>
        </div>
      </div>

      <div className="panel__body--compact">
        <div className="service-grid">
          {grouped.map((svc, i) => {
            const cfg = STATUS_CONFIG[svc.status] || STATUS_CONFIG.healthy
            return (
              <button
                key={svc.id}
                className={`service-card service-card--${svc.status}`}
                onClick={() => onSelectService(svc.id)}
                style={{ animationDelay: `${i * 0.03}s` }}
              >
                <div className="service-card__header">
                  <span className="service-card__status-dot" style={{ background: cfg.color }}></span>
                  <span className="service-card__name">{svc.id}</span>
                  <span className={`badge badge-${svc.status}`}>{cfg.label}</span>
                </div>

                <div className="service-card__metrics">
                  <div className="service-card__metric">
                    <span className="service-card__metric-label">CPU</span>
                    <div className="service-card__metric-bar-track">
                      <div
                        className="service-card__metric-bar"
                        style={{
                          width: `${Math.min(100, svc.metrics.cpu_percent)}%`,
                          background: svc.metrics.cpu_percent > 80 ? 'var(--accent-magenta)' : 'var(--accent-blue)',
                        }}
                      ></div>
                    </div>
                    <span className="service-card__metric-value">{svc.metrics.cpu_percent}%</span>
                  </div>

                  <div className="service-card__metric">
                    <span className="service-card__metric-label">MEM</span>
                    <div className="service-card__metric-bar-track">
                      <div
                        className="service-card__metric-bar"
                        style={{
                          width: `${Math.min(100, svc.metrics.memory_percent)}%`,
                          background: svc.metrics.memory_percent > 80 ? 'var(--accent-magenta)' : 'var(--accent-purple)',
                        }}
                      ></div>
                    </div>
                    <span className="service-card__metric-value">{svc.metrics.memory_percent}%</span>
                  </div>

                  <div className="service-card__metric-row">
                    <span className="service-card__metric-detail">
                      <span className="service-card__metric-label">Latency</span>
                      <span className="service-card__metric-value mono">{svc.metrics.latency_ms}ms</span>
                    </span>
                    <span className="service-card__metric-detail">
                      <span className="service-card__metric-label">Errors</span>
                      <span className="service-card__metric-value mono">{(svc.metrics.error_rate * 100).toFixed(2)}%</span>
                    </span>
                  </div>
                </div>
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}
