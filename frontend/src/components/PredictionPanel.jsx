import { useState, useEffect } from 'react'
import './PredictionPanel.css'

export default function PredictionPanel({ predictions, apiBase }) {
  const [liveCountdowns, setLiveCountdowns] = useState({})

  // Auto-countdown timer
  useEffect(() => {
    if (!predictions?.predictions?.length) return

    const initial = {}
    predictions.predictions.forEach((p, i) => {
      initial[i] = p.predicted_failure_in
    })
    setLiveCountdowns(initial)

    const timer = setInterval(() => {
      setLiveCountdowns(prev => {
        const updated = { ...prev }
        Object.keys(updated).forEach(k => {
          updated[k] = Math.max(0, updated[k] - 1)
        })
        return updated
      })
    }, 1000)

    return () => clearInterval(timer)
  }, [predictions])

  if (!predictions || !predictions.predictions || predictions.predictions.length === 0) {
    return (
      <div className="panel prediction-panel prediction-panel--clear">
        <div className="panel__header">
          <span className="panel__title">
            <span className="panel__title-icon">🔮</span> Predictive Failure Engine
          </span>
        </div>
        <div className="panel__body">
          <div className="prediction-clear">
            <span className="prediction-clear__icon">✅</span>
            <span>No imminent failures predicted. All metric trends are stable.</span>
          </div>
        </div>
      </div>
    )
  }

  const formatCountdown = (seconds) => {
    if (seconds <= 0) return 'IMMINENT'
    const m = Math.floor(seconds / 60)
    const s = Math.floor(seconds % 60)
    return m > 0 ? `${m}m ${s}s` : `${s}s`
  }

  const getSeverityClass = (severity) => {
    return `prediction-card--${severity.toLowerCase()}`
  }

  return (
    <div className="panel prediction-panel">
      <div className="panel__header">
        <span className="panel__title">
          <span className="panel__title-icon">🔮</span> Predictive Failure Engine
        </span>
        <span className="badge badge-critical prediction-badge-pulse">
          ⚠️ {predictions.num_warnings} prediction{predictions.num_warnings !== 1 ? 's' : ''}
        </span>
      </div>

      <div className="panel__body">
        <div className="prediction-grid">
          {predictions.predictions.map((pred, idx) => {
            const countdown = liveCountdowns[idx] ?? pred.predicted_failure_in
            const isImminent = countdown < 120
            const isUrgent = countdown < 60

            return (
              <div
                key={idx}
                className={`prediction-card ${getSeverityClass(pred.severity)} ${isUrgent ? 'prediction-card--urgent' : ''}`}
              >
                <div className="prediction-card__header">
                  <div className="prediction-card__service">
                    <span className={`prediction-card__severity-dot prediction-card__severity-dot--${pred.severity.toLowerCase()}`} />
                    <span className="mono">{pred.service}</span>
                  </div>
                  <span className={`prediction-card__countdown ${isImminent ? 'prediction-card__countdown--imminent' : ''}`}>
                    {formatCountdown(countdown)}
                  </span>
                </div>

                <div className="prediction-card__message">
                  {pred.message}
                </div>

                <div className="prediction-card__details">
                  <div className="prediction-card__detail">
                    <span className="prediction-card__detail-label">Metric</span>
                    <span className="prediction-card__detail-value">{pred.metric.replace(/_/g, ' ')}</span>
                  </div>
                  <div className="prediction-card__detail">
                    <span className="prediction-card__detail-label">Current</span>
                    <span className="prediction-card__detail-value">{pred.current_value}</span>
                  </div>
                  <div className="prediction-card__detail">
                    <span className="prediction-card__detail-label">Threshold</span>
                    <span className="prediction-card__detail-value">{pred.threshold}</span>
                  </div>
                  <div className="prediction-card__detail">
                    <span className="prediction-card__detail-label">Trend</span>
                    <span className="prediction-card__detail-value">
                      {pred.trend === 'accelerating' ? '📈 Accelerating' : '↗️ Increasing'}
                    </span>
                  </div>
                </div>

                {/* Risk Progress Bar */}
                <div className="prediction-card__risk">
                  <div className="prediction-card__risk-label">
                    <span>Risk</span>
                    <span>{(pred.risk_score * 100).toFixed(0)}%</span>
                  </div>
                  <div className="prediction-card__risk-bar">
                    <div
                      className="prediction-card__risk-fill"
                      style={{
                        width: `${pred.risk_score * 100}%`,
                        background: pred.risk_score > 0.7
                          ? 'var(--accent-magenta)'
                          : pred.risk_score > 0.4
                            ? 'var(--accent-amber)'
                            : 'var(--accent-blue)',
                      }}
                    />
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
