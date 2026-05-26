import React, { useState } from 'react'

const SOURCES = ['doors', 'jama', 'visure', 'word', 'pdf', 'sysml']

const styles = {
  section: { background: '#1e293b', borderRadius: 8, padding: '1.5rem', border: '1px solid #334155', marginBottom: '1.5rem' },
  h2: { fontSize: '1rem', fontWeight: 600, color: '#e2e8f0', marginBottom: '1rem' },
  select: { background: '#0f172a', border: '1px solid #334155', color: '#e2e8f0', padding: '0.5rem 0.75rem', borderRadius: 6, width: '100%', marginBottom: 12, fontSize: '0.9rem' },
  btn: { background: '#0284c7', color: '#fff', border: 'none', padding: '0.5rem 1.2rem', borderRadius: 6, cursor: 'pointer', fontWeight: 600 },
  result: { marginTop: '1rem', background: '#0f172a', borderRadius: 6, padding: '1rem', fontSize: '0.85rem', fontFamily: 'monospace', whiteSpace: 'pre-wrap', maxHeight: 400, overflowY: 'auto' },
  err: { color: '#f87171' },
  ok: { color: '#4ade80' },
}

export default function Ingestion() {
  const [source, setSource] = useState('doors')
  const [file, setFile] = useState(null)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  const upload = async (e) => {
    e.preventDefault()
    if (!file) return
    setLoading(true); setError(null); setResult(null)
    const fd = new FormData()
    fd.append('file', file)
    try {
      const r = await fetch(`/api/v1/ingestion/upload/${source}`, { method: 'POST', body: fd })
      const data = await r.json()
      if (!r.ok) setError(data.detail ?? JSON.stringify(data))
      else setResult(data)
    } catch (ex) {
      setError(ex.message)
    }
    setLoading(false)
  }

  return (
    <div>
      <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: '#f8fafc', marginBottom: '1.5rem' }}>Artifact Ingestion</h1>

      <div style={styles.section}>
        <div style={styles.h2}>Upload Artifact File</div>
        <form onSubmit={upload}>
          <label style={{ color: '#94a3b8', fontSize: '0.85rem' }}>Source adapter</label>
          <select style={styles.select} value={source} onChange={e => setSource(e.target.value)}>
            {SOURCES.map(s => <option key={s} value={s}>{s.toUpperCase()}</option>)}
          </select>
          <input type="file" style={{ color: '#e2e8f0', marginBottom: 12 }} onChange={e => setFile(e.target.files[0])} />
          <br />
          <button type="submit" style={styles.btn} disabled={loading || !file}>
            {loading ? 'Uploading...' : 'Ingest File'}
          </button>
        </form>

        {error && <div style={{ ...styles.result, ...styles.err }}>Error: {error}</div>}
        {result && (
          <div style={styles.result}>
            <span style={styles.ok}>Success!</span> Ingested {result.artifact_count} artifact(s) from {result.source_type}.{'\n\n'}
            {result.artifacts.map((a, i) => `[${i + 1}] ${a.artifact_id} (${a.artifact_type}) - ${a.title}`).join('\n')}
          </div>
        )}
      </div>
    </div>
  )
}
