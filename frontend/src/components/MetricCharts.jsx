import { useState, useEffect } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Area, AreaChart
} from 'recharts'
import './MetricCharts.css'

const METRIC_CONFIG = {
  cpu_percent:    { label: 'CPU %',       color: '#00d4ff', unit: '%' },
  memory_percent: { label: 'Memory %',    color: '#8b5cf6', unit: '%' },
  latency_ms:     { label: 'Latency (ms)',color: '#ffbe0b', unit: 'ms' },
  error_rate:     { label: 'Error Rate',  color: '#ff006e', unit: '' },
  connections:    { label: 'Connections',  color: '#00ff88', unit: '' },
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip__time">{label}</div>
      {payload.map((item, i) => (
        <div key={i} className="chart-tooltip__item">
          <span className="chart-tooltip__dot" style={{ background: item.color }}></span>
          <span>{item.value?.toFixed(2)}</span>
        </div>
      ))}
    </div>
  )
}

export default function MetricCharts({ selectedService, apiBase }) {
  const [metrics, setMetrics] = useState([])
  const [activeMetric, setActiveMetric] = useState('cpu_percent')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!selectedService) return
    setLoading(true)

    fetch(`${apiBase}/metrics/${selectedService}?limit=300`)
      .then(res => res.json())
      .then(data => {
        // Downsample for chart performance
        const raw = data.metrics || []
        const step = Math.max(1, Math.floor(raw.length / 150))
        const sampled = raw.filter((_, i) => i % step === 0).map((m, i) => ({
          ...m,
          idx: i,
          time: `${i * step}s`,
        }))
        setMetrics(sampled)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [selectedService, apiBase])

  const cfg = METRIC_CONFIG[activeMetric]

  return (
    <div className="panel metric-panel">
      <div className="panel__header">
        <span className="panel__title">
          <span className="panel__title-icon">📈</span>
          <span>Metrics</span>
          <span className="panel__title-service mono">{selectedService}</span>
        </span>
      </div>

      {/* Metric selector tabs */}
      <div className="metric-tabs">
        {Object.entries(METRIC_CONFIG).map(([key, conf]) => (
          <button
            key={key}
            className={`metric-tab ${activeMetric === key ? 'active' : ''}`}
            onClick={() => setActiveMetric(key)}
            style={{ '--tab-color': conf.color }}
          >
            {conf.label}
          </button>
        ))}
      </div>

      <div className="panel__body--compact">
        {loading ? (
          <div className="loading-overlay"><span className="spinner"></span></div>
        ) : metrics.length === 0 ? (
          <div className="loading-overlay">No metric data available</div>
        ) : (
          <div className="chart-wrapper">
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={metrics} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                <defs>
                  <linearGradient id={`grad-${activeMetric}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={cfg.color} stopOpacity={0.3} />
                    <stop offset="100%" stopColor={cfg.color} stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                <XAxis
                  dataKey="time"
                  tick={{ fill: 'var(--text-tertiary)', fontSize: 10 }}
                  axisLine={{ stroke: 'rgba(255,255,255,0.06)' }}
                  tickLine={false}
                  interval="preserveStartEnd"
                />
                <YAxis
                  tick={{ fill: 'var(--text-tertiary)', fontSize: 10 }}
                  axisLine={false}
                  tickLine={false}
                  width={40}
                />
                <Tooltip content={<CustomTooltip />} />
                <Area
                  type="monotone"
                  dataKey={activeMetric}
                  stroke={cfg.color}
                  strokeWidth={1.5}
                  fill={`url(#grad-${activeMetric})`}
                  dot={false}
                  animationDuration={500}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  )
}
