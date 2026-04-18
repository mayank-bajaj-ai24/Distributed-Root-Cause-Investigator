import { useState } from 'react'
import './RootCausePanel.css'

export default function RootCausePanel({ result, confidenceImpact }) {
  const [expanded, setExpanded] = useState({})

  if (!result || !result.root_cause) {
    return (
      <div className="panel rca-panel rca-panel--healthy">
        <div className="panel__header">
          <span className="panel__title"><span className="panel__title-icon">🎯</span> Root Cause Analysis</span>
        </div>
        <div className="panel__body">
          <div className="rca-healthy">
            <span className="rca-healthy__icon">✅</span>
            <span>No significant anomalies detected. All services operating normally.</span>
          </div>
        </div>
      </div>
    )
  }

  const { root_cause, explanation, ranked_services, num_anomalous } = result
  const chain = explanation?.chain

  const toggleExpand = (service) => {
    setExpanded(prev => ({ ...prev, [service]: !prev[service] }))
  }

  return (
    <div className="panel rca-panel">
      <div className="panel__header">
        <span className="panel__title"><span className="panel__title-icon">🎯</span> Root Cause Analysis</span>
        <span className="badge badge-critical">
          {num_anomalous} service{num_anomalous !== 1 ? 's' : ''} affected
        </span>
      </div>

      <div className="panel__body">
        {/* Confidence & Impact Row */}
        {confidenceImpact && (
          <div className="rca-ci-row fade-in">
            {/* Confidence Gauge */}
            {confidenceImpact.confidence && (
              <div className="rca-ci-gauge">
                <div className="rca-ci-gauge__ring">
                  <svg viewBox="0 0 36 36" className="rca-ci-gauge__svg">
                    <path
                      className="rca-ci-gauge__bg"
                      d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                    />
                    <path
                      className="rca-ci-gauge__fg"
                      strokeDasharray={`${confidenceImpact.confidence.overall * 100}, 100`}
                      d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                    />
                  </svg>
                  <span className="rca-ci-gauge__value">
                    {(confidenceImpact.confidence.overall * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="rca-ci-gauge__info">
                  <span className="rca-ci-gauge__label">Confidence</span>
                  <span className={`rca-ci-gauge__tag rca-ci-gauge__tag--${confidenceImpact.confidence.label?.toLowerCase().replace(' ', '-')}`}>
                    {confidenceImpact.confidence.label}
                  </span>
                </div>
              </div>
            )}

            {/* Impact Score */}
            {confidenceImpact.impact && (
              <div className="rca-ci-impact">
                <div className="rca-ci-impact__score-box">
                  <span className="rca-ci-impact__number">{confidenceImpact.impact.score.toFixed(0)}</span>
                  <span className="rca-ci-impact__out-of">/100</span>
                </div>
                <div className="rca-ci-impact__info">
                  <span className="rca-ci-impact__label">Impact Score</span>
                  <span className={`rca-ci-impact__tag rca-ci-impact__tag--${confidenceImpact.impact.label?.toLowerCase()}`}>
                    {confidenceImpact.impact.label}
                  </span>
                </div>
              </div>
            )}

            {/* Blast Radius */}
            {confidenceImpact.impact && (
              <div className="rca-ci-blast">
                <div className="rca-ci-blast__visual">
                  <span className="rca-ci-blast__count">{confidenceImpact.impact.affected_services}</span>
                  <span className="rca-ci-blast__sep">/</span>
                  <span className="rca-ci-blast__total">{confidenceImpact.impact.total_services}</span>
                </div>
                <div className="rca-ci-blast__info">
                  <span className="rca-ci-blast__label">Blast Radius</span>
                  {confidenceImpact.impact.user_facing && (
                    <span className="rca-ci-blast__user-facing">👤 User-Facing</span>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Summary */}
        <div className="rca-summary fade-in">
          <div className="rca-summary__header">
            <span className="rca-summary__icon">🔴</span>
            <div>
              <div className="rca-summary__title">{explanation?.summary}</div>
              <div className="rca-summary__confidence">
                Confidence: {confidenceImpact?.confidence ? `${(confidenceImpact.confidence.overall * 100).toFixed(0)}%` : `${Math.min(99, (root_cause.fused_score * 100)).toFixed(0)}%`}
              </div>
            </div>
          </div>
        </div>

        {/* Failure Chain */}
        {chain && (
          <div className="rca-chain fade-in" style={{ animationDelay: '0.1s' }}>
            {/* Root Cause Node */}
            <div className="rca-chain__node rca-chain__node--root">
              <div className="rca-chain__node-header" onClick={() => toggleExpand('root')}>
                <span className="rca-chain__connector rca-chain__connector--root">●</span>
                <span className="rca-chain__node-label">ROOT CAUSE</span>
                <span className="rca-chain__node-service mono">{chain.root_cause.service}</span>
                <span className="rca-chain__node-issue">{chain.root_cause.issue}</span>
                <span className="rca-chain__expand">{expanded.root ? '▾' : '▸'}</span>
              </div>

              {expanded.root && (
                <div className="rca-chain__evidence">
                  {chain.root_cause.evidence?.map((ev, i) => (
                    <div key={i} className="rca-chain__evidence-item">
                      <span className="rca-chain__evidence-icon">
                        {ev.type === 'metric' ? '📈' : ev.type === 'graph' ? '🕸️' : '📝'}
                      </span>
                      <span className="rca-chain__evidence-text">{ev.description}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Impact Nodes */}
            {chain.impacts?.map((impact, idx) => (
              <div key={idx} className="rca-chain__node rca-chain__node--impact">
                <div className="rca-chain__branch-line"></div>
                <div className="rca-chain__node-header" onClick={() => toggleExpand(impact.service)}>
                  <span className="rca-chain__connector rca-chain__connector--impact">├</span>
                  <span className={`rca-chain__severity-badge rca-chain__severity-badge--${impact.severity.toLowerCase()}`}>
                    {impact.severity}
                  </span>
                  <span className="rca-chain__node-service mono">{impact.service}</span>
                  <span className="rca-chain__node-effect">{impact.effect}</span>
                  <span className="rca-chain__expand">{expanded[impact.service] ? '▾' : '▸'}</span>
                </div>

                {expanded[impact.service] && (
                  <div className="rca-chain__evidence">
                    {impact.evidence?.map((ev, i) => (
                      <div key={i} className="rca-chain__evidence-item">
                        <span className="rca-chain__evidence-icon">
                          {ev.type === 'metric' ? '📈' : ev.type === 'graph' ? '🕸️' : '📝'}
                        </span>
                        <span className="rca-chain__evidence-text">{ev.description}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Score Breakdown */}
        <div className="rca-scores fade-in" style={{ animationDelay: '0.2s' }}>
          <h4 className="rca-scores__title">Signal Breakdown</h4>
          <div className="rca-scores__grid">
            {ranked_services?.filter(s => s.is_anomaly).map(s => (
              <div key={s.service} className="rca-score-card">
                <div className="rca-score-card__header">
                  <span className="mono">{s.service}</span>
                  <span className="rca-score-card__total">{(s.fused_score * 100).toFixed(0)}%</span>
                </div>
                <div className="rca-score-card__bars">
                  <div className="rca-score-card__bar">
                    <span className="rca-score-card__bar-label">Log</span>
                    <div className="rca-score-card__bar-track">
                      <div className="rca-score-card__bar-fill rca-score-card__bar-fill--log"
                        style={{ width: `${s.log_score * 100}%` }}></div>
                    </div>
                  </div>
                  <div className="rca-score-card__bar">
                    <span className="rca-score-card__bar-label">Metric</span>
                    <div className="rca-score-card__bar-track">
                      <div className="rca-score-card__bar-fill rca-score-card__bar-fill--metric"
                        style={{ width: `${s.metric_score * 100}%` }}></div>
                    </div>
                  </div>
                  <div className="rca-score-card__bar">
                    <span className="rca-score-card__bar-label">Graph</span>
                    <div className="rca-score-card__bar-track">
                      <div className="rca-score-card__bar-fill rca-score-card__bar-fill--graph"
                        style={{ width: `${s.graph_score * 100}%` }}></div>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
