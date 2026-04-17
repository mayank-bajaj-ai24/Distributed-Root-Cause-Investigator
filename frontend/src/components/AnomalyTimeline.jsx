import './AnomalyTimeline.css'

export default function AnomalyTimeline({ anomalies, services }) {
  if (!anomalies || !anomalies.anomalies || Object.keys(anomalies.anomalies).length === 0) {
    return (
      <div className="panel">
        <div className="panel__header">
          <span className="panel__title"><span className="panel__title-icon">📡</span> Anomaly Timeline</span>
        </div>
        <div className="panel__body">
          <div className="timeline-empty">
            <span className="timeline-empty__icon">✅</span>
            <span>No anomalies detected. Inject a failure scenario to see anomalies.</span>
          </div>
        </div>
      </div>
    )
  }

  const anomalyData = anomalies.anomalies
  const totalPoints = 600 // approximate duration

  return (
    <div className="panel">
      <div className="panel__header">
        <span className="panel__title"><span className="panel__title-icon">📡</span> Anomaly Timeline</span>
        <span className="badge badge-warning">
          {anomalies.num_services_affected} service{anomalies.num_services_affected !== 1 ? 's' : ''} affected
        </span>
      </div>

      <div className="panel__body--compact">
        <div className="timeline">
          {/* Time axis */}
          <div className="timeline__axis">
            <span>0s</span>
            <span>120s</span>
            <span>240s</span>
            <span>360s</span>
            <span>480s</span>
            <span>600s</span>
          </div>

          {/* Service rows */}
          {Object.entries(anomalyData).map(([service, data]) => {
            const startPct = (data.anomaly_start_idx / totalPoints) * 100
            const endPct = (data.anomaly_end_idx / totalPoints) * 100
            const widthPct = Math.max(2, endPct - startPct)

            return (
              <div key={service} className="timeline__row fade-in">
                <div className="timeline__service-name mono">{service}</div>
                <div className="timeline__track">
                  <div
                    className="timeline__anomaly-bar"
                    style={{
                      left: `${startPct}%`,
                      width: `${widthPct}%`,
                    }}
                    title={`${data.num_anomalous_points} anomalous points (score: ${data.max_score.toFixed(2)})`}
                  >
                    <div className="timeline__anomaly-glow"></div>
                  </div>

                  {/* Score sparkline */}
                  {data.scores && (
                    <svg className="timeline__sparkline" viewBox={`0 0 ${data.scores.length} 20`} preserveAspectRatio="none">
                      <polyline
                        points={data.scores.map((s, i) => `${i},${20 - s * 20}`).join(' ')}
                        fill="none"
                        stroke="rgba(255, 0, 110, 0.4)"
                        strokeWidth="0.8"
                      />
                    </svg>
                  )}
                </div>
                <div className="timeline__score">
                  <span className={`timeline__score-value ${data.max_score > 0.8 ? 'critical' : 'warning'}`}>
                    {(data.max_score * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
