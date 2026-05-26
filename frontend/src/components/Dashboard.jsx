import React, { useEffect, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts'

const COLORS = ['#38bdf8', '#22d3ee', '#818cf8', '#f472b6', '#fb923c']

const styles = {
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '2rem' },
  card: { background: '#1e293b', borderRadius: 8, padding: '1.2rem', border: '1px solid #334155' },
  label: { color: '#94a3b8', fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: 1 },
  value: { fontSize: '2rem', fontWeight: 700, color: '#38bdf8', marginTop: 4 },
  section: { background: '#1e293b', borderRadius: 8, padding: '1.5rem', border: '1px solid #334155', marginBottom: '1.5rem' },
  h2: { fontSize: '1rem', fontWeight: 600, color: '#e2e8f0', marginBottom: '1rem' },
  err: { color: '#f87171', padding: '1rem', background: '#450a0a', borderRadius: 6 },
}

function MetricCard({ label, value }) {
  return (
    <div style={styles.card}>
      <div style={styles.label}>{label}</div>
      <div style={styles.value}>{value ?? '-'}</div>
    </div>
  )
}

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch('/api/v1/dashboard/summary')
      .then(r => r.json())
      .then(setData)
      .catch(e => setError(e.message))
  }, [])

  if (error) return <div style={styles.err}>API Error: {error}. Is the ATRI server running?</div>
  if (!data) return <div style={{ color: '#94a3b8', padding: '2rem' }}>Loading dashboard...</div>

  const reviewData = [
    { name: 'Accepted', value: data.review_summary?.accepted_reviews ?? 0 },
    { name: 'Rejected', value: data.review_summary?.rejected_reviews ?? 0 },
    { name: 'Pending', value: data.review_summary?.pending_reviews ?? 0 },
  ]

  const eventData = Object.entries(data.audit_summary?.event_counts ?? {}).map(([name, value]) => ({ name, value }))

  return (
    <div>
      <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: '#f8fafc', marginBottom: '1.5rem' }}>
        ATRI Platform Dashboard
      </h1>

      <div style={styles.grid}>
        <MetricCard label="Trace Coverage" value={data.trace_coverage ?? 'N/A'} />
        <MetricCard label="Total Artifacts" value={data.graph_summary?.total_nodes} />
        <MetricCard label="Trace Links" value={data.graph_summary?.total_edges} />
        <MetricCard label="Suspect Links" value={data.suspect_links ?? 0} />
        <MetricCard label="Total Reviews" value={data.review_summary?.total_reviews} />
        <MetricCard label="Audit Events" value={data.audit_summary?.total_events} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
        <div style={styles.section}>
          <div style={styles.h2}>Review Decisions</div>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={reviewData} cx="50%" cy="50%" outerRadius={80} dataKey="value" label={({ name, value }) => `${name}: ${value}`}>
                {reviewData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div style={styles.section}>
          <div style={styles.h2}>Audit Events by Type</div>
          {eventData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={eventData}>
                <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 11 }} />
                <YAxis tick={{ fill: '#94a3b8' }} />
                <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 6 }} />
                <Bar dataKey="value" fill="#38bdf8" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ color: '#94a3b8', textAlign: 'center', paddingTop: '3rem' }}>No audit events yet</div>
          )}
        </div>
      </div>
    </div>
  )
}
