import './PatternMatchPanel.css'

export default function PatternMatchPanel({ patternMatches }) {
  if (!patternMatches || !patternMatches.matches || patternMatches.matches.length === 0) {
    return null
  }

  const { matches, best_match, recommendation } = patternMatches

  return (
    <div className="panel pattern-panel">
      <div className="panel__header">
        <span className="panel__title">
          <span className="panel__title-icon">🧠</span> Failure Pattern Memory
        </span>
        <span className="badge badge-info">
          {matches.length} match{matches.length !== 1 ? 'es' : ''} found
        </span>
      </div>

      <div className="panel__body">
        {/* Recommendation Banner */}
        {recommendation && (
          <div className="pattern-recommendation fade-in">
            <div className="pattern-recommendation__icon">💡</div>
            <div className="pattern-recommendation__text">{recommendation}</div>
          </div>
        )}

        {/* Matches List */}
        <div className="pattern-matches">
          {matches.map((match, idx) => (
            <div
              key={match.incident_id}
              className={`pattern-match-card ${idx === 0 ? 'pattern-match-card--best' : ''}`}
              style={{ animationDelay: `${idx * 0.1}s` }}
            >
              <div className="pattern-match-card__header">
                <div className="pattern-match-card__title-row">
                  {idx === 0 && <span className="pattern-match-card__best-badge">BEST MATCH</span>}
                  <span className="pattern-match-card__id">{match.incident_id}</span>
                </div>
                <div className="pattern-match-card__similarity">
                  <div className="pattern-match-card__similarity-ring">
                    <svg viewBox="0 0 36 36" className="pattern-match-card__circle">
                      <path
                        className="pattern-match-card__circle-bg"
                        d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                      />
                      <path
                        className="pattern-match-card__circle-fg"
                        strokeDasharray={`${match.similarity * 100}, 100`}
                        d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                        style={{
                          stroke: match.similarity > 0.75
                            ? 'var(--accent-emerald)'
                            : match.similarity > 0.5
                              ? 'var(--accent-amber)'
                              : 'var(--accent-blue)',
                        }}
                      />
                    </svg>
                    <span className="pattern-match-card__similarity-text">
                      {(match.similarity * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
              </div>

              <div className="pattern-match-card__title">{match.title}</div>

              <div className="pattern-match-card__meta">
                <div className="pattern-match-card__meta-item">
                  <span className="pattern-match-card__meta-icon">🔧</span>
                  <span className="mono">{match.root_cause_service}</span>
                </div>
                {match.occurrence_count > 1 && (
                  <div className="pattern-match-card__meta-item">
                    <span className="pattern-match-card__meta-icon">🔄</span>
                    <span>Seen {match.occurrence_count} times</span>
                  </div>
                )}
                {match.time_to_resolve && match.time_to_resolve !== 'Unknown' && (
                  <div className="pattern-match-card__meta-item">
                    <span className="pattern-match-card__meta-icon">⏱️</span>
                    <span>Fixed in {match.time_to_resolve}</span>
                  </div>
                )}
              </div>

              {/* Matched On Tags */}
              <div className="pattern-match-card__tags">
                {match.matched_on.map(factor => (
                  <span key={factor} className="pattern-match-card__tag">
                    {factor.replace(/_/g, ' ')}
                  </span>
                ))}
              </div>

              {/* Resolution */}
              <div className="pattern-match-card__resolution">
                <div className="pattern-match-card__resolution-label">Recommended Fix</div>
                <div className="pattern-match-card__resolution-text">{match.resolution}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
