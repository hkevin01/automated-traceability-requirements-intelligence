/**
 * ID: ATRI-UI-APP-001
 * Purpose: Root application shell - navigation bar and page routing.
 * Inputs: None.
 * Outputs: Single-page app with Dashboard, Traceability, Impact Analysis,
 *          Ingestion, and Live Feed pages.
 */

import React, { useState } from 'react'
import Dashboard from './components/Dashboard.jsx'
import ImpactAnalysis from './components/ImpactAnalysis.jsx'
import Ingestion from './components/Ingestion.jsx'
import LiveFeed from './components/LiveFeed.jsx'
import Traceability from './components/Traceability.jsx'

const NAV = [
  { id: 'dashboard',   label: 'Dashboard' },
  { id: 'traceability', label: 'Traceability' },
  { id: 'impact',      label: 'Impact' },
  { id: 'ingestion',   label: 'Ingestion' },
  { id: 'livefeed',    label: '● Live Feed' },
]

const styles = {
  nav: {
    background: '#1e293b', padding: '1rem 2rem', display: 'flex',
    alignItems: 'center', gap: '1.5rem', borderBottom: '1px solid #334155',
    flexWrap: 'wrap',
  },
  brand: { fontWeight: 700, fontSize: '1.2rem', color: '#38bdf8', letterSpacing: 1, marginRight: '0.5rem' },
  navBtn: (active, id) => ({
    background: active ? '#0284c7' : 'transparent',
    color: active ? '#fff' : id === 'livefeed' ? '#4ade80' : '#94a3b8',
    border: 'none', cursor: 'pointer', padding: '0.4rem 1rem',
    borderRadius: 6, fontWeight: 500, fontSize: '0.9rem',
    transition: 'background 0.15s',
  }),
  main: { padding: '2rem', maxWidth: 1280, margin: '0 auto' },
}

export default function App() {
  const [page, setPage] = useState('dashboard')
  return (
    <div style={{ minHeight: '100vh', background: '#0f172a' }}>
      <nav style={styles.nav}>
        <span style={styles.brand}>ATRI</span>
        {NAV.map(({ id, label }) => (
          <button key={id} style={styles.navBtn(page === id, id)} onClick={() => setPage(id)}>
            {label}
          </button>
        ))}
      </nav>
      <main style={styles.main}>
        {page === 'dashboard'    && <Dashboard />}
        {page === 'traceability' && <Traceability />}
        {page === 'impact'       && <ImpactAnalysis />}
        {page === 'ingestion'    && <Ingestion />}
        {page === 'livefeed'     && <LiveFeed />}
      </main>
    </div>
  )
}
