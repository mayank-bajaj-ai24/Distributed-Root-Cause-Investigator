import { useMemo } from 'react'
import './CausalGraph.css'

export default function CausalGraph({ causalAnalysis }) {
  if (!causalAnalysis || !causalAnalysis.causal_edges || causalAnalysis.causal_edges.length === 0) {
    return null
  }

  const { causal_edges, causal_chain, root_cause, causality_type } = causalAnalysis

  const typeConfig = {
    confirmed: { label: 'Confirmed', color: 'var(--accent-emerald)', icon: '✅' },
    probable: { label: 'Probable', color: 'var(--accent-amber)', icon: '🔶' },
    uncertain: { label: 'Uncertain', color: 'var(--text-tertiary)', icon: '❓' },
    single_service: { label: 'Single Service', color: 'var(--accent-blue)', icon: 'ℹ️' },
  }

  const config = typeConfig[causality_type] || typeConfig.uncertain

  return (
    <div className="panel causal-panel">
      <div className="panel__header">
        <span className="panel__title">
          <span className="panel__title-icon">🔗</span> Causal Inference
        </span>
        <span className="causal-type-badge" style={{ color: config.color, borderColor: config.color }}>
          {config.icon} {config.label} Causality
        </span>
      </div>

      <div className="panel__body">
        {/* Causal Chain Visualization */}
        <div className="causal-chain-flow">
          {causal_chain.map((service, idx) => {
            const isRoot = idx === 0
            const isLast = idx === causal_chain.length - 1
            const edge = causal_edges.find(e => e.source === service)

            return (
              <div key={service} className="causal-chain-flow__item">
                <div className={`causal-chain-flow__node ${isRoot ? 'causal-chain-flow__node--root' : ''}`}>
                  <div className="causal-chain-flow__node-label">
                    {isRoot && <span className="causal-chain-flow__root-badge">ROOT CAUSE</span>}
                    <span className="causal-chain-flow__node-name mono">{service}</span>
                  </div>
                </div>

                {!isLast && edge && (
                  <div className="causal-chain-flow__arrow">
                    <div className="causal-chain-flow__arrow-line">
                      <div
                        className="causal-chain-flow__arrow-fill"
                        style={{ width: `${edge.strength * 100}%` }}
                      />
                    </div>
                    <div className="causal-chain-flow__arrow-info">
                      <span className="causal-chain-flow__lag">
                        {edge.lag_seconds}s lag
                      </span>
                      <span className="causal-chain-flow__strength">
                        {(edge.strength * 100).toFixed(0)}% causal
                      </span>
                    </div>
                    <div className="causal-chain-flow__arrow-head">→</div>
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* Edge Details Table */}
        <div className="causal-edges">
          <h4 className="causal-edges__title">Causal Evidence</h4>
          <div className="causal-edges__grid">
            {causal_edges.map((edge, idx) => (
              <div key={idx} className="causal-edge-card">
                <div className="causal-edge-card__header">
                  <span className="mono">{edge.source}</span>
                  <span className="causal-edge-card__arrow">→</span>
                  <span className="mono">{edge.target}</span>
                </div>
                <div className="causal-edge-card__metrics">
                  <div className="causal-edge-card__metric">
                    <span className="causal-edge-card__metric-label">Time Lag</span>
                    <span className="causal-edge-card__metric-value">{edge.lag_seconds}s</span>
                  </div>
                  <div className="causal-edge-card__metric">
                    <span className="causal-edge-card__metric-label">Strength</span>
                    <span className="causal-edge-card__metric-value">{(edge.strength * 100).toFixed(0)}%</span>
                  </div>
                  <div className="causal-edge-card__metric">
                    <span className="causal-edge-card__metric-label">Correlation</span>
                    <span className="causal-edge-card__metric-value">{(edge.correlation * 100).toFixed(0)}%</span>
                  </div>
                </div>
                <div className="causal-edge-card__bar">
                  <div
                    className="causal-edge-card__bar-fill"
                    style={{
                      width: `${edge.strength * 100}%`,
                      background: edge.strength > 0.7
                        ? 'var(--accent-emerald)'
                        : edge.strength > 0.4
                          ? 'var(--accent-amber)'
                          : 'var(--text-tertiary)',
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
