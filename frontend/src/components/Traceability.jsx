import React, { useEffect, useState } from 'react'

const styles = {
  section: { background: '#1e293b', borderRadius: 8, padding: '1.5rem', border: '1px solid #334155', marginBottom: '1.5rem' },
  h2: { fontSize: '1rem', fontWeight: 600, color: '#e2e8f0', marginBottom: '1rem' },
  input: { background: '#0f172a', border: '1px solid #334155', color: '#e2e8f0', padding: '0.5rem 0.75rem', borderRadius: 6, width: '100%', marginBottom: 8, fontSize: '0.9rem' },
  btn: { background: '#0284c7', color: '#fff', border: 'none', padding: '0.5rem 1.2rem', borderRadius: 6, cursor: 'pointer', fontWeight: 600 },
  table: { width: '100%', borderCollapse: 'collapse' },
  th: { textAlign: 'left', color: '#94a3b8', padding: '0.5rem', fontSize: '0.8rem', borderBottom: '1px solid #334155' },
  td: { padding: '0.6rem 0.5rem', borderBottom: '1px solid #1e293b', fontSize: '0.85rem' },
  badge: (dec) => ({
    background: dec === 'accepted' ? '#14532d' : dec === 'rejected' ? '#450a0a' : '#1e3a5f',
    color: dec === 'accepted' ? '#4ade80' : dec === 'rejected' ? '#f87171' : '#93c5fd',
    padding: '2px 8px', borderRadius: 12, fontSize: '0.75rem', fontWeight: 600,
  }),
}

export default function Traceability() {
  const [reviews, setReviews] = useState([])
  const [form, setForm] = useState({ source_id: '', target_id: '', decision: 'accepted', reviewer: '', comments: '' })

  const load = () => fetch('/api/v1/traceability/reviews').then(r => r.json()).then(setReviews).catch(() => {})
  useEffect(() => { load() }, [])

  const submit = (e) => {
    e.preventDefault()
    fetch('/api/v1/traceability/review', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(form),
    }).then(() => load()).catch(() => {})
  }

  return (
    <div>
      <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: '#f8fafc', marginBottom: '1.5rem' }}>Traceability Reviews</h1>

      <div style={styles.section}>
        <div style={styles.h2}>Submit Review Decision</div>
        <form onSubmit={submit}>
          {['source_id', 'target_id', 'reviewer', 'comments'].map(f => (
            <input key={f} style={styles.input} placeholder={f.replace('_', ' ')} value={form[f]}
              onChange={e => setForm(v => ({ ...v, [f]: e.target.value }))} />
          ))}
          <select style={{ ...styles.input, marginBottom: 12 }} value={form.decision}
            onChange={e => setForm(v => ({ ...v, decision: e.target.value }))}>
            <option value="accepted">Accepted</option>
            <option value="rejected">Rejected</option>
            <option value="pending">Pending</option>
          </select>
          <button type="submit" style={styles.btn}>Submit Review</button>
        </form>
      </div>

      <div style={styles.section}>
        <div style={styles.h2}>Review Records ({reviews.length})</div>
        {reviews.length === 0 ? <div style={{ color: '#94a3b8' }}>No reviews yet.</div> : (
          <table style={styles.table}>
            <thead>
              <tr>
                {['Source', 'Target', 'Decision', 'Reviewer', 'Comments'].map(h => <th key={h} style={styles.th}>{h}</th>)}
              </tr>
            </thead>
            <tbody>
              {reviews.map((r, i) => (
                <tr key={i}>
                  <td style={styles.td}>{r.source_id}</td>
                  <td style={styles.td}>{r.target_id}</td>
                  <td style={styles.td}><span style={styles.badge(r.decision)}>{r.decision}</span></td>
                  <td style={styles.td}>{r.reviewer}</td>
                  <td style={styles.td}>{r.comments}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
