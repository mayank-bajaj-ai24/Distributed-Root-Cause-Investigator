import { useRef, useEffect, useState, useCallback } from 'react'
import * as d3 from 'd3'
import { forceSimulation, forceLink, forceManyBody, forceCenter, forceCollide } from 'd3-force'
import './ServiceGraph.css'

const STATUS_COLORS = {
  healthy:  '#00ff88',
  warning:  '#ffbe0b',
  critical: '#ff006e',
}

const TYPE_SHAPES = {
  service:   { symbol: '⬡', size: 28 },
  datastore: { symbol: '⬡', size: 24 },
  gateway:   { symbol: '⬡', size: 32 },
}

export default function ServiceGraph({ graph, services, anomalies, analysisResult, onSelectService }) {
  const svgRef = useRef(null)
  const containerRef = useRef(null)
  const [dimensions, setDimensions] = useState({ width: 800, height: 420 })

  const getServiceStatus = useCallback((id) => {
    const svc = services?.find(s => s.id === id)
    return svc?.status || 'healthy'
  }, [services])

  const isRootCause = useCallback((id) => {
    if (!analysisResult?.root_cause) return false
    return analysisResult.root_cause.service === id
  }, [analysisResult])

  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    const obs = new ResizeObserver(entries => {
      const { width, height } = entries[0].contentRect
      setDimensions({ width: Math.max(400, width), height: Math.max(300, height) })
    })
    obs.observe(container)
    return () => obs.disconnect()
  }, [])

  useEffect(() => {
    if (!graph || !svgRef.current) return

    const { width, height } = dimensions
    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()

    // Build simulation data
    const nodes = graph.nodes.map(n => ({
      ...n,
      status: getServiceStatus(n.id),
      isRoot: isRootCause(n.id),
    }))
    const links = graph.edges.map(e => ({ source: e.source, target: e.target }))

    // Defs for gradients and filters
    const defs = svg.append('defs')

    // Glow filter
    const filter = defs.append('filter').attr('id', 'glow')
    filter.append('feGaussianBlur').attr('stdDeviation', 4).attr('result', 'blur')
    filter.append('feMerge').selectAll('feMergeNode')
      .data(['blur', 'SourceGraphic']).enter()
      .append('feMergeNode').attr('in', d => d)

    // Root cause glow
    const rcFilter = defs.append('filter').attr('id', 'rc-glow')
    rcFilter.append('feGaussianBlur').attr('stdDeviation', 8).attr('result', 'blur')
    rcFilter.append('feMerge').selectAll('feMergeNode')
      .data(['blur', 'SourceGraphic']).enter()
      .append('feMergeNode').attr('in', d => d)

    // Arrow marker
    defs.append('marker')
      .attr('id', 'arrowhead')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 32)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('class', 'graph-arrow')

    // Simulation
    const simulation = forceSimulation(nodes)
      .force('link', forceLink(links).id(d => d.id).distance(120))
      .force('charge', forceManyBody().strength(-400))
      .force('center', forceCenter(width / 2, height / 2))
      .force('collide', forceCollide(45))

    // Main group
    const g = svg.append('g')

    // Zoom
    const zoom = d3.zoom()
      .scaleExtent([0.3, 3])
      .on('zoom', (event) => g.attr('transform', event.transform))
    svg.call(zoom)

    // Links
    const link = g.append('g')
      .selectAll('line')
      .data(links)
      .join('line')
      .attr('class', 'graph-link')

    // Node groups
    const node = g.append('g')
      .selectAll('g')
      .data(nodes)
      .join('g')
      .attr('class', d => `graph-node ${d.status} ${d.isRoot ? 'root-cause' : ''}`)
      .style('cursor', 'pointer')
      .on('click', (event, d) => onSelectService(d.id))
      .call(d3.drag()
        .on('start', (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart()
          d.fx = d.x; d.fy = d.y
        })
        .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y })
        .on('end', (event, d) => {
          if (!event.active) simulation.alphaTarget(0)
          d.fx = null; d.fy = null
        })
      )

    // Outer ring (status indicator)
    node.append('circle')
      .attr('r', d => d.type === 'gateway' ? 26 : d.type === 'datastore' ? 22 : 24)
      .attr('fill', 'none')
      .attr('stroke', d => STATUS_COLORS[d.status])
      .attr('stroke-width', d => d.isRoot ? 3 : 1.5)
      .attr('stroke-opacity', d => d.status === 'healthy' ? 0.3 : 0.7)
      .attr('filter', d => d.isRoot ? 'url(#rc-glow)' : d.status !== 'healthy' ? 'url(#glow)' : null)

    // Inner circle
    node.append('circle')
      .attr('r', d => d.type === 'gateway' ? 20 : d.type === 'datastore' ? 16 : 18)
      .attr('fill', d => {
        const c = STATUS_COLORS[d.status]
        return d.status === 'healthy' ? 'rgba(0,255,136,0.08)' : `${c}15`
      })
      .attr('stroke', d => STATUS_COLORS[d.status])
      .attr('stroke-width', 0.5)
      .attr('stroke-opacity', 0.2)

    // Icon
    node.append('text')
      .attr('text-anchor', 'middle')
      .attr('dominant-baseline', 'central')
      .attr('font-size', d => d.type === 'datastore' ? '12px' : '14px')
      .text(d => d.type === 'datastore' ? '🗄️' : d.type === 'gateway' ? '🌐' : '⚙️')

    // Label
    node.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', d => (d.type === 'gateway' ? 26 : 24) + 14)
      .attr('class', 'graph-node-label')
      .text(d => d.id)

    // Root cause label
    node.filter(d => d.isRoot)
      .append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', -34)
      .attr('class', 'graph-root-label')
      .text('ROOT CAUSE')

    // Pulse animation for critical nodes
    node.filter(d => d.status === 'critical')
      .append('circle')
      .attr('r', 30)
      .attr('fill', 'none')
      .attr('stroke', STATUS_COLORS.critical)
      .attr('stroke-width', 1)
      .attr('opacity', 0)
      .attr('class', 'pulse-ring')

    // Tick
    simulation.on('tick', () => {
      link
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y)

      node.attr('transform', d => `translate(${d.x}, ${d.y})`)
    })

    return () => simulation.stop()
  }, [graph, dimensions, services, analysisResult, getServiceStatus, isRootCause, onSelectService])

  if (!graph) {
    return (
      <div className="panel">
        <div className="panel__header">
          <span className="panel__title"><span className="panel__title-icon">🕸️</span> Service Dependency Graph</span>
        </div>
        <div className="loading-overlay">
          <span className="spinner"></span> Loading graph...
        </div>
      </div>
    )
  }

  return (
    <div className="panel service-graph-panel">
      <div className="panel__header">
        <span className="panel__title"><span className="panel__title-icon">🕸️</span> Service Dependency Graph</span>
        <div className="graph-legend">
          <span className="graph-legend__item">
            <span className="graph-legend__dot" style={{ background: STATUS_COLORS.healthy }}></span>
            Healthy
          </span>
          <span className="graph-legend__item">
            <span className="graph-legend__dot" style={{ background: STATUS_COLORS.warning }}></span>
            Warning
          </span>
          <span className="graph-legend__item">
            <span className="graph-legend__dot" style={{ background: STATUS_COLORS.critical }}></span>
            Critical
          </span>
        </div>
      </div>
      <div className="graph-container" ref={containerRef}>
        <svg ref={svgRef} width={dimensions.width} height={dimensions.height}></svg>
      </div>
    </div>
  )
}
