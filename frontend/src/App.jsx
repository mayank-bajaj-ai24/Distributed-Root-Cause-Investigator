import { useState, useEffect, useCallback } from 'react'
import './App.css'
import Dashboard from './components/Dashboard'
import ServiceGraph from './components/ServiceGraph'
import AnomalyTimeline from './components/AnomalyTimeline'
import RootCausePanel from './components/RootCausePanel'
import LogViewer from './components/LogViewer'
import MetricCharts from './components/MetricCharts'
import CausalGraph from './components/CausalGraph'
import PredictionPanel from './components/PredictionPanel'
import PatternMatchPanel from './components/PatternMatchPanel'

const API_BASE = 'http://localhost:5000/api'

function App() {
  const [services, setServices] = useState([])
  const [graph, setGraph] = useState(null)
  const [selectedService, setSelectedService] = useState(null)
  const [selectedScenario, setSelectedScenario] = useState('')
  const [scenarios, setScenarios] = useState([])
  const [activeScenario, setActiveScenario] = useState(null)
  const [analysisResult, setAnalysisResult] = useState(null)
  const [anomalies, setAnomalies] = useState(null)
  const [loading, setLoading] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError] = useState(null)
  const [systemStatus, setSystemStatus] = useState('healthy')
  const [theme, setTheme] = useState('dark')

  useEffect(() => {
    if (theme === 'dark') {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }, [theme])

  const toggleTheme = () => {
    setTheme(t => t === 'dark' ? 'light' : 'dark')
  }

  // ── Fetch helpers ──────────────────────────────────────────
  const fetchJSON = useCallback(async (path, options = {}) => {
    try {
      const res = await fetch(`${API_BASE}${path}`, options)
      if (!res.ok) throw new Error(`API error: ${res.status}`)
      return await res.json()
    } catch (err) {
      console.error(`Fetch failed: ${path}`, err)
      throw err
    }
  }, [])

  // ── Initial load ───────────────────────────────────────────
  useEffect(() => {
    const init = async () => {
      try {
        const [svcData, graphData, scenarioData] = await Promise.all([
          fetchJSON('/services'),
          fetchJSON('/graph'),
          fetchJSON('/scenarios'),
        ])
        setServices(svcData.services || [])
        setActiveScenario(svcData.active_scenario)
        setGraph(graphData)
        setScenarios(scenarioData.scenarios || [])
        updateSystemStatus(svcData.services || [])
      } catch (err) {
        setError('Failed to connect to backend. Make sure the API server is running on port 5000.')
      }
    }
    init()
  }, [fetchJSON])

  const updateSystemStatus = (svcs) => {
    const hasCritical = svcs.some(s => s.status === 'critical')
    const hasWarning = svcs.some(s => s.status === 'warning')
    setSystemStatus(hasCritical ? 'critical' : hasWarning ? 'warning' : 'healthy')
  }

  // ── Inject scenario ───────────────────────────────────────
  const handleInjectScenario = async () => {
    if (!selectedScenario) return
    setLoading(true)
    setError(null)
    setAnalysisResult(null)
    setAnomalies(null)

    try {
      const result = await fetchJSON(`/scenarios/${selectedScenario}/inject`, { method: 'POST' })
      setActiveScenario(result.scenario)

      // Refresh services
      const svcData = await fetchJSON('/services')
      setServices(svcData.services || [])
      updateSystemStatus(svcData.services || [])

      // Fetch anomalies
      const anomData = await fetchJSON('/anomalies')
      setAnomalies(anomData)
    } catch (err) {
      setError('Failed to inject scenario')
    } finally {
      setLoading(false)
    }
  }

  // ── Run analysis ──────────────────────────────────────────
  const handleAnalyze = async () => {
    setAnalyzing(true)
    setError(null)

    try {
      const result = await fetchJSON('/analyze', { method: 'POST' })
      setAnalysisResult(result)

      // Refresh anomalies
      const anomData = await fetchJSON('/anomalies')
      setAnomalies(anomData)

      // Refresh services
      const svcData = await fetchJSON('/services')
      setServices(svcData.services || [])
      updateSystemStatus(svcData.services || [])
    } catch (err) {
      setError('Analysis failed — check backend logs')
    } finally {
      setAnalyzing(false)
    }
  }

  // ── Reset system ──────────────────────────────────────────
  const handleReset = async () => {
    setLoading(true)
    try {
      await fetchJSON('/reset', { method: 'POST' })
      setActiveScenario(null)
      setAnalysisResult(null)
      setAnomalies(null)
      setSelectedScenario('')

      const svcData = await fetchJSON('/services')
      setServices(svcData.services || [])
      updateSystemStatus(svcData.services || [])
    } catch (err) {
      setError('Reset failed')
    } finally {
      setLoading(false)
    }
  }

  const getSystemHealthStr = () => {
    if (!services || services.length === 0) return '99.98%'
    let score = 0
    services.forEach(s => {
      if (s.status === 'healthy') score += 100
      else if (s.status === 'warning') score += 75
      else score += 30 // critical
    })
    const avg = score / services.length
    if (avg >= 99) return '99.98%'
    return `${avg.toFixed(2)}%`
  }

  return (
    <div className="min-h-screen bg-white dark:bg-[#0D0D0F] text-[#18181B] dark:text-[#e5e1e4] font-body selection:bg-primary-container/30">
      {/* TopNavBar */}
      <header className="fixed top-0 w-full z-50 border-b border-black/10 dark:border-[#FF6B00]/10 bg-[#FFFFFF] dark:bg-[#16161A] backdrop-blur-md shadow-[0_4px_24px_rgba(0,0,0,0.5)] flex justify-between items-center h-14 px-6 relative">
        <div className="flex items-center gap-8">
          <div className="text-xl font-bold uppercase tracking-widest text-[#FF6B00] font-headline">
              Investigator
          </div>
          <button
            onClick={toggleTheme}
            className="flex items-center justify-center w-8 h-8 rounded-full bg-black/5 dark:bg-white/10 hover:bg-black/10 dark:hover:bg-white/20 transition-all text-[#18181B] dark:text-[#e5e1e4]"
            title="Toggle Theme"
          >
            {theme === 'dark' ? '☀️' : '🌙'}
          </button>
          <div className="hidden md:flex items-center gap-4">
            <select
              className="bg-white dark:bg-[#0D0D0F] border border-black/10 dark:border-outline-variant/20 rounded-sm px-3 py-1 text-xs font-label uppercase tracking-wider text-[#18181B] dark:text-on-surface w-64 focus:ring-[#FF6B00]"
              value={selectedScenario}
              onChange={e => setSelectedScenario(e.target.value)}
            >
              <option value="">Select Failure Scenario...</option>
              {scenarios.map(s => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
            <button
              className="bg-[#FF6B00]/10 text-[#FF6B00] border border-[#FF6B00]/30 hover:bg-[#FF6B00]/20 text-xs px-3 py-1 rounded-sm uppercase tracking-widest font-bold transition-all disabled:opacity-50"
              onClick={handleInjectScenario}
              disabled={!selectedScenario || loading}
            >
              {loading ? 'Injecting...' : 'Inject Failure'}
            </button>
            <button
              className="bg-[#FF6B00] text-[#0D0D0F] text-xs px-3 py-1 rounded-sm uppercase tracking-widest font-bold transition-all disabled:opacity-50 hover:bg-[#ff8a33]"
              onClick={handleAnalyze}
              disabled={analyzing}
            >
              {analyzing ? 'Analyzing...' : 'Run Analysis'}
            </button>
            <button
              className="bg-[#F4F4F5] dark:bg-surface-container text-secondary border border-black/10 dark:border-outline-variant/20 hover:bg-surface-bright text-xs px-3 py-1 rounded-sm uppercase tracking-widest transition-all"
              onClick={handleReset}
              disabled={loading}
            >
              Reset
            </button>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 px-3 py-1 border border-[#FF6B00]/30 rounded-sm">
            <div className={`w-2 h-2 rounded-full ${systemStatus === 'healthy' ? 'bg-tertiary' : 'bg-[#FF6B00]'} animate-pulse`}></div>
            <span className="text-[10px] font-label uppercase tracking-widest text-[#FF6B00]">
              Env: Production Mode
            </span>
          </div>
        </div>
      </header>

      {/* SideNavBar - Simplified single view */}
      <aside className="fixed left-0 top-0 h-full w-64 border-r border-black/5 dark:border-[#FF6B00]/5 bg-white dark:bg-[#0D0D0F] flex flex-col pt-20 pb-6 px-4 z-40 hidden md:flex">
        <div className="mb-8 px-2">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-[var(--bg-card)] rounded-sm flex items-center justify-center border border-black/10 dark:border-outline-variant/20">
              <span className="material-symbols-outlined text-[#FF6B00]">terminal</span>
            </div>
            <div>
              <div className="text-xs font-headline font-bold text-[#18181B] dark:text-on-surface leading-none tracking-tight">AI RCA Engine</div>
              <div className="text-[10px] font-label text-[#52525B] dark:text-[#8E9196] uppercase mt-1">Distributed Engine v2.4</div>
            </div>
          </div>
        </div>
        <nav className="flex-1 space-y-1">
          <div className="flex items-center gap-3 px-3 py-2 bg-[#FF6B00] text-[#0D0D0F] font-bold rounded-sm font-headline text-sm uppercase tracking-wider">
            <span className="material-symbols-outlined" style={{fontVariationSettings: "'FILL' 1"}}>dashboard</span>
            <span>Global Dashboard</span>
          </div>
        </nav>
      </aside>

      {/* Main Content Area */}
      <main className="md:ml-64 pt-20 px-6 pb-12 min-h-screen">
        {error && (
          <div className="bg-error-container text-on-error-container border border-error p-3 mb-4 rounded-sm text-sm uppercase tracking-wider font-bold shadow-lg">
            ⚠️ {error}
          </div>
        )}

        {/* Dashboard Header */}
        <div className="flex justify-between items-end mb-8">
          <div>
            <h1 className="font-headline text-3xl font-bold text-[#18181B] dark:text-[#F8F9FA] tracking-tight uppercase">System Overview</h1>
            <p className="text-[#3F3F46] dark:text-secondary font-label text-sm mt-1 uppercase tracking-widest opacity-60">
              {activeScenario ? `Active Chaos: ${activeScenario.name}` : 'Real-time Telemetry & Intelligence Shell'}
            </p>
          </div>
          <div className="flex gap-4">
            <div className="text-right">
              <div className="text-[10px] font-label text-[#3F3F46] dark:text-secondary uppercase tracking-[0.2em]">Global Health</div>
              <div className={`text-3xl font-headline font-bold ${systemStatus === 'healthy' ? 'text-[#059669]' : 'text-[#dc2626]'}`}>
                {getSystemHealthStr()}
              </div>
            </div>
            <div className="w-[1px] bg-outline-variant/20 h-10"></div>
            <div className="text-right">
              <div className="text-[10px] font-label text-[#3F3F46] dark:text-secondary uppercase tracking-[0.2em]">Active Nodes</div>
              <div className="text-3xl font-headline font-bold text-[#18181B] dark:text-[#F8F9FA]">11</div>
            </div>
          </div>
        </div>

        {/* ORIGINAL LAYOUT (Wrapped in Stitch UI Containers) */}
        
        <div className="dashboard-grid">
          
          {/* Service Overview (Full Width) */}
          <div className="dashboard-grid__item--full bg-[#f3f4f6] dark:bg-surface-container-low border border-black/10 dark:border-outline-variant/10 p-6 rounded-sm slide-up" style={{ animationDelay: '0.05s' }}>
            <Dashboard services={services} onSelectService={setSelectedService} />
          </div>

          {/* Service Dependency Graph (Full Width) */}
          <div className="dashboard-grid__item--full bg-[#f3f4f6] dark:bg-surface-container-lowest border border-black/10 dark:border-outline-variant/10 rounded-sm slide-up relative overflow-hidden group" style={{ animationDelay: '0.1s' }}>
             <div className="absolute top-4 left-6 z-10 flex items-center gap-3 bg-white dark:bg-[#0D0D0F]/80 backdrop-blur-sm px-4 py-2 border border-black/10 dark:border-outline-variant/20 rounded-sm">
                 <span className="material-symbols-outlined text-[#FF6B00] text-[16px]">hub</span>
                 <span className="text-xs font-label uppercase text-[#3F3F46] dark:text-secondary tracking-widest font-bold">Network Topology Map</span>
             </div>
             <div className="pt-16 min-h-[420px]">
                <ServiceGraph
                graph={graph}
                services={services}
                anomalies={anomalies}
                analysisResult={analysisResult}
                onSelectService={setSelectedService}
              />
             </div>
          </div>

          {/* Intelligence Engine Stack */}
          <div className="dashboard-grid__item--full flex flex-col gap-6 slide-up">
            
            <div className={`bg-[#f3f4f6] dark:bg-[#16161A] border ${analysisResult ? 'border-black/5 dark:border-[#FF6B00]/50' : 'border-[#FF6B00]/20'} p-6 rounded-sm relative overflow-hidden h-full`} style={{ animationDelay: '0.12s' }}>
                <div className="absolute top-0 right-0 w-24 h-24 bg-[#FF6B00]/5 -rotate-45 translate-x-12 -translate-y-12 border-b border-black/10 dark:border-[#FF6B00]/10"></div>
                <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                    <span className="material-symbols-outlined text-[#FF6B00]">psychology</span>
                    <h3 className="font-headline font-bold uppercase text-sm tracking-widest text-[#FF6B00]">Predictive Failure Engine</h3>
                    </div>
                </div>

                {!analysisResult ? (
                    <div className="space-y-4 pt-4">
                        <div className="p-3 bg-[#f3f4f6] dark:bg-[#0D0D0F] border-l-2 border-outline-variant font-mono text-[11px] text-[#65a30d] dark:text-[#A3E635] opacity-50 dark:opacity-50">
                            &gt; status: waiting for execution<br/>
                            &gt; models: ready
                        </div>
                    </div>
                ) : (
                    <PredictionPanel
                        predictions={analysisResult?.predictions}
                        apiBase={API_BASE}
                    />
                )}
            </div>

            <div className={`bg-[#f3f4f6] dark:bg-[#16161A] border ${analysisResult ? 'border-black/5 dark:border-[#FF6B00]/50' : 'border-[#FF6B00]/20'} p-6 rounded-sm relative overflow-hidden h-full`} style={{ animationDelay: '0.15s' }}>
                <div className="absolute top-0 right-0 w-24 h-24 bg-[#FF6B00]/5 -rotate-45 translate-x-12 -translate-y-12 border-b border-black/10 dark:border-[#FF6B00]/10"></div>
                <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                    <span className="material-symbols-outlined text-[#FF6B00]">error</span>
                    <h3 className="font-headline font-bold uppercase text-sm tracking-widest text-[#FF6B00]">Root Cause Inference</h3>
                    </div>
                </div>

                {!analysisResult ? (
                    <div className="space-y-4 pt-4">
                        <div className="p-3 bg-[#f3f4f6] dark:bg-[#0D0D0F] border-l-2 border-outline-variant font-mono text-[11px] text-[#65a30d] dark:text-[#A3E635] opacity-50 dark:opacity-50">
                            &gt; status: waiting for execution<br/>
                            &gt; models: ready
                        </div>
                    </div>
                ) : (
                    <RootCausePanel
                        result={analysisResult}
                        confidenceImpact={analysisResult?.confidence_impact}
                    />
                )}
            </div>

          </div>

          {/* Causal Inference Graph */}
          {analysisResult?.causal_analysis && (
            <div className="dashboard-grid__item--full bg-[#f3f4f6] dark:bg-surface-container-lowest border border-black/10 dark:border-outline-variant/10 p-6 rounded-sm slide-up" style={{ animationDelay: '0.18s' }}>
              <CausalGraph causalAnalysis={analysisResult.causal_analysis} />
            </div>
          )}

          {/* Pattern Match Panel */}
          {analysisResult?.pattern_matches && (
            <div className="dashboard-grid__item--full bg-[#f3f4f6] dark:bg-surface-container-lowest border border-black/10 dark:border-outline-variant/10 p-6 rounded-sm slide-up" style={{ animationDelay: '0.2s' }}>
              <PatternMatchPanel patternMatches={analysisResult.pattern_matches} />
            </div>
          )}

          {/* Anomaly Timeline */}
          <div className="dashboard-grid__item--full bg-[#f3f4f6] dark:bg-surface-container-lowest border border-black/10 dark:border-outline-variant/10 p-6 rounded-sm slide-up" style={{ animationDelay: '0.22s' }}>
            <h3 className="font-headline font-bold uppercase text-sm tracking-widest mb-6">Health Timeline <span className="ml-2 text-[10px] text-[#3F3F46] dark:text-secondary font-normal font-label tracking-normal lowercase opacity-60">(past 5m)</span></h3>
            <AnomalyTimeline anomalies={anomalies} services={services} />
          </div>

          {/* Metric Charts */}
          <div className="bg-[#f3f4f6] dark:bg-surface-container-lowest border border-black/10 dark:border-outline-variant/10 p-6 rounded-sm slide-up" style={{ animationDelay: '0.25s' }}>
            <MetricCharts
              selectedService={selectedService || 'api-gateway'}
              apiBase={API_BASE}
            />
          </div>

          {/* Log Viewer */}
          <div className="bg-[#f3f4f6] dark:bg-surface-container-lowest border border-black/10 dark:border-outline-variant/10 p-4 rounded-sm slide-up h-[400px] flex flex-col" style={{ animationDelay: '0.3s' }}>
            <div className="flex items-center justify-between mb-4 border-b border-outline-variant/10 pb-2">
                <span className="text-[10px] font-label uppercase tracking-[0.2em] font-bold text-[#18181B] dark:text-[#e5e1e4]">System Log Stream</span>
                <span className="material-symbols-outlined text-xs text-[#52525B] dark:text-[#8E9196]">terminal</span>
            </div>
            <div className="flex-1 overflow-auto">
                <LogViewer
                selectedService={selectedService || 'api-gateway'}
                apiBase={API_BASE}
                services={services}
                />
            </div>
          </div>

        </div>
      </main>
    </div>
  )
}

export default App
