import React, { useState } from 'react'
import Dashboard from './components/Dashboard.jsx'
import Traceability from './components/Traceability.jsx'
import Ingestion from './components/Ingestion.jsx'

const NAV = [
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'traceability', label: 'Traceability' },
  { id: 'ingestion', label: 'Ingestion' },
]

const styles = {
  nav: { background: '#1e293b', padding: '1rem 2rem', display: 'flex', alignItems: 'center', gap: '2rem', borderBottom: '1px solid #334155' },
  brand: { fontWeight: 700, fontSize: '1.2rem', color: '#38bdf8', letterSpacing: 1 },
  navBtn: (active) => ({
    background: active ? '#0284c7' : 'transparent',
    color: active ? '#fff' : '#94a3b8',
    border: 'none', cursor: 'pointer', padding: '0.4rem 1rem',
    borderRadius: 6, fontWeight: 500, fontSize: '0.9rem',
  }),
  main: { padding: '2rem', maxWidth: 1200, margin: '0 auto' },
}

export default function App() {
  const [page, setPage] = useState('dashboard')
  return (
    <div>
      <nav style={styles.nav}>
        <span style={styles.brand}>ATRI</span>
        {NAV.map(({ id, label }) => (
          <button key={id} style={styles.navBtn(page === id)} onClick={() => setPage(id)}>{label}</button>
        ))}
      </nav>
      <main style={styles.main}>
        {page === 'dashboard' && <Dashboard />}
        {page === 'traceability' && <Traceability />}
        {page === 'ingestion' && <Ingestion />}
      </main>
    </div>
  )
}
