/**
 * ID: ATRI-UI-IMPACT-001
 * Purpose: Impact analysis page - submit changed artifact IDs and visualise
 *          upstream/downstream impact chain from POST /api/v1/impact/analyze.
 * Inputs: User-supplied artifact IDs and direction selection.
 * Outputs: Collapsible result tree showing impacted artifacts with distance.
 * Failure modes: API error rendered inline; loading state shown during request.
 */

import React, { useState } from 'react'

const styles = {
  section: { background: '#1e293b', borderRadius: 8, padding: '1.5rem', border: '1px solid #334155', marginBottom: '1.5rem' },
  h2: { fontSize: '1rem', fontWeight: 600, color: '#e2e8f0', marginBottom: '1rem' },
  label: { color: '#94a3b8', fontSize: '0.8rem', display: 'block', marginBottom: 4 },
  input: { background: '#0f172a', border: '1px solid #334155', color: '#e2e8f0', padding: '0.5rem 0.75rem', borderRadius: 6, width: '100%', marginBottom: 12, fontSize: '0.9rem' },
  row: { display: 'flex', gap: '0.75rem', marginBottom: 12 },
  dirBtn: (active) => ({
    flex: 1, background: active ? '#0284c7' : '#0f172a', color: active ? '#fff' : '#94a3b8',
    border: '1px solid #334155', padding: '0.45rem', borderRadius: 6, cursor: 'pointer', fontWeight: 500, fontSize: '0.85rem',
  }),
  btn: { background: '#0284c7', color: '#fff', border: 'none', padding: '0.5rem 1.4rem', borderRadius: 6, cursor: 'pointer', fontWeight: 600 },
  err: { color: '#f87171', background: '#450a0a', borderRadius: 6, padding: '0.75rem 1rem', marginTop: 8 },
  resultHeader: { display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' },
  count: { background: '#1e3a5f', color: '#93c5fd', borderRadius: 12, padding: '2px 10px', fontSize: '0.8rem', fontWeight: 600 },
  table: { width: '100%', borderCollapse: 'collapse' },
  th: { textAlign: 'left', color: '#94a3b8', padding: '0.5rem', fontSize: '0.8rem', borderBottom: '1px solid #334155' },
  td: { padding: '0.55rem 0.5rem', borderBottom: '1px solid #1e293b', fontSize: '0.85rem', color: '#e2e8f0' },
  distBadge: (d) => ({
    display: 'inline-block', padding: '1px 7px', borderRadius: 10,
    background: d === 1 ? '#7c3aed33' : d === 2 ? '#0369a133' : '#33333344',
    color: d === 1 ? '#c4b5fd' : d === 2 ? '#7dd3fc' : '#94a3b8',
    fontSize: '0.75rem', fontWeight: 600,
  }),
  typeBadge: {
    display: 'inline-block', padding: '1px 7px', borderRadius: 10,
    background: '#1e3a5f', color: '#93c5fd', fontSize: '0.75rem', fontWeight: 600,
  },
}

export default function ImpactAnalysis() {
  const [ids, setIds] = useState('')
  const [direction, setDirection] = useState('both')
  const [maxDepth, setMaxDepth] = useState('3')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const analyze = async (e) => {
    e.preventDefault()
    const changedIds = ids.split(/[\n,]+/).map(s => s.trim()).filter(Boolean)
    if (!changedIds.length) return
    setLoading(true); setError(null); setResult(null)
    try {
      const resp = await fetch('/api/v1/impact/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ changed_artifact_ids: changedIds, direction, max_depth: parseInt(maxDepth, 10) || 3 }),
      })
      const data = await resp.json()
      if (!resp.ok) { setError(data.detail ?? JSON.stringify(data)); return }
      setResult(data)
    } catch (ex) {
      setError(ex.message)
    } finally {
      setLoading(false)
    }
  }

  const impacts = result ? [
    ...(result.upstream_impacts ?? []).map(a => ({ ...a, dir: 'upstream' })),
    ...(result.downstream_impacts ?? []).map(a => ({ ...a, dir: 'downstream' })),
  ] : []

  return (
    <div>
      <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: '#f8fafc', marginBottom: '1.5rem' }}>Impact Analysis</h1>

      <div style={styles.section}>
        <div style={styles.h2}>Analyze Changed Artifacts</div>
        <form onSubmit={analyze}>
          <label style={styles.label}>Changed artifact IDs (one per line or comma-separated)</label>
          <textarea
            style={{ ...styles.input, height: 90, resize: 'vertical' }}
            placeholder="REQ-001&#10;REQ-042"
            value={ids}
            onChange={e => setIds(e.target.value)}
          />
          <div style={styles.row}>
            {['upstream', 'downstream', 'both'].map(d => (
              <button key={d} type="button" style={styles.dirBtn(direction === d)} onClick={() => setDirection(d)}>
                {d.charAt(0).toUpperCase() + d.slice(1)}
              </button>
            ))}
          </div>
          <label style={styles.label}>Max traversal depth</label>
          <input style={{ ...styles.input, width: 80 }} type="number" min="1" max="10" value={maxDepth} onChange={e => setMaxDepth(e.target.value)} />
          <br />
          <button type="submit" style={styles.btn} disabled={loading || !ids.trim()}>
            {loading ? 'Analyzing...' : 'Run Analysis'}
          </button>
        </form>
        {error && <div style={styles.err}>{error}</div>}
      </div>

      {result && (
        <div style={styles.section}>
          <div style={styles.resultHeader}>
            <div style={styles.h2}>Results</div>
            <span style={styles.count}>{impacts.length} impacted artifact{impacts.length !== 1 ? 's' : ''}</span>
          </div>
          {impacts.length === 0 ? (
            <div style={{ color: '#94a3b8' }}>No impacted artifacts found for the given IDs and direction.</div>
          ) : (
            <table style={styles.table}>
              <thead>
                <tr>
                  {['Artifact ID', 'Type', 'Title', 'Direction', 'Distance'].map(h => (
                    <th key={h} style={styles.th}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {impacts.map((a, i) => (
                  <tr key={i}>
                    <td style={styles.td}><code style={{ color: '#7dd3fc' }}>{a.artifact_id}</code></td>
                    <td style={styles.td}><span style={styles.typeBadge}>{a.artifact_type ?? '-'}</span></td>
                    <td style={styles.td}>{a.title ?? '-'}</td>
                    <td style={{ ...styles.td, color: a.dir === 'upstream' ? '#f9a8d4' : '#86efac' }}>{a.dir}</td>
                    <td style={styles.td}><span style={styles.distBadge(a.distance)}>{a.distance ?? '-'}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}
