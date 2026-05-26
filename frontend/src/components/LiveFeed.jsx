/**
 * ID: ATRI-UI-LIVEFEED-001
 * Purpose: Real-time audit event feed via WebSocket connection to /api/v1/stream/events.
 * Inputs: none (reads VITE_API_BASE from env or defaults to window.location.host)
 * Outputs: Scrollable live event list with connection status indicator.
 * Failure modes: WebSocket error shows reconnect message; reconnects automatically every 5s.
 */

import React, { useEffect, useRef, useState } from 'react'

const MAX_EVENTS = 200

const styles = {
  wrapper: { display: 'flex', flexDirection: 'column', height: '100%' },
  header: { display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' },
  h1: { fontSize: '1.5rem', fontWeight: 700, color: '#f8fafc', margin: 0 },
  dot: (status) => ({
    width: 10, height: 10, borderRadius: '50%',
    background: status === 'connected' ? '#4ade80' : status === 'connecting' ? '#fbbf24' : '#f87171',
    flexShrink: 0,
  }),
  statusLabel: (status) => ({
    fontSize: '0.8rem',
    color: status === 'connected' ? '#4ade80' : status === 'connecting' ? '#fbbf24' : '#f87171',
  }),
  controls: { display: 'flex', gap: '0.75rem', marginBottom: '1rem', alignItems: 'center' },
  btn: (active) => ({
    background: active ? '#0284c7' : '#1e293b',
    color: active ? '#fff' : '#94a3b8',
    border: '1px solid #334155', padding: '0.3rem 0.9rem',
    borderRadius: 6, cursor: 'pointer', fontSize: '0.8rem', fontWeight: 500,
  }),
  clearBtn: {
    background: 'transparent', color: '#64748b', border: '1px solid #334155',
    padding: '0.3rem 0.9rem', borderRadius: 6, cursor: 'pointer', fontSize: '0.8rem',
    marginLeft: 'auto',
  },
  feed: {
    flex: 1, overflowY: 'auto', background: '#0f172a', borderRadius: 8,
    border: '1px solid #334155', padding: '0.75rem', fontFamily: 'monospace',
    fontSize: '0.8rem', minHeight: 400, maxHeight: 600,
  },
  event: (type) => ({
    padding: '0.35rem 0.5rem', borderBottom: '1px solid #1e293b',
    color: type === 'audit' ? '#93c5fd' : type === 'dashboard' ? '#86efac' : '#e2e8f0',
  }),
  ts: { color: '#475569', marginRight: '0.5rem' },
  tag: (type) => ({
    display: 'inline-block', padding: '1px 6px', borderRadius: 4, fontSize: '0.7rem',
    fontWeight: 600, marginRight: '0.5rem',
    background: type === 'audit' ? '#1e3a5f' : type === 'dashboard' ? '#14532d' : '#2d1b69',
    color: type === 'audit' ? '#93c5fd' : type === 'dashboard' ? '#86efac' : '#c4b5fd',
  }),
  empty: { color: '#475569', textAlign: 'center', paddingTop: '3rem' },
}

const TOPICS = ['all', 'audit', 'dashboard']

export default function LiveFeed() {
  const [events, setEvents] = useState([])
  const [status, setStatus] = useState('disconnected')
  const [topic, setTopic] = useState('all')
  const wsRef = useRef(null)
  const feedRef = useRef(null)
  const reconnectRef = useRef(null)
  const autoScrollRef = useRef(true)

  const connect = (topicValue) => {
    if (wsRef.current) {
      wsRef.current.onclose = null
      wsRef.current.close()
    }
    setStatus('connecting')
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const host = import.meta.env.VITE_API_HOST ?? window.location.host
    const ws = new WebSocket(`${proto}://${host}/api/v1/stream/events?topic=${topicValue}`)
    wsRef.current = ws

    ws.onopen = () => setStatus('connected')
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data)
        const entry = {
          id: Date.now() + Math.random(),
          ts: new Date().toLocaleTimeString(),
          type: msg.type ?? 'message',
          payload: msg,
          raw: typeof msg === 'object' ? JSON.stringify(msg, null, 2) : String(msg),
        }
        setEvents((prev) => {
          const next = [entry, ...prev]
          return next.length > MAX_EVENTS ? next.slice(0, MAX_EVENTS) : next
        })
      } catch {
        // ignore malformed frames
      }
    }
    ws.onerror = () => setStatus('error')
    ws.onclose = () => {
      setStatus('disconnected')
      reconnectRef.current = setTimeout(() => connect(topicValue), 5000)
    }
  }

  useEffect(() => {
    connect(topic)
    return () => {
      clearTimeout(reconnectRef.current)
      if (wsRef.current) {
        wsRef.current.onclose = null
        wsRef.current.close()
      }
    }
  }, [topic])

  // Auto-scroll to top (newest event is first)
  useEffect(() => {
    if (autoScrollRef.current && feedRef.current) {
      feedRef.current.scrollTop = 0
    }
  }, [events])

  return (
    <div style={styles.wrapper}>
      <div style={styles.header}>
        <h1 style={styles.h1}>Live Event Feed</h1>
        <div style={styles.dot(status)} />
        <span style={styles.statusLabel(status)}>{status}</span>
      </div>

      <div style={styles.controls}>
        {TOPICS.map((t) => (
          <button key={t} style={styles.btn(topic === t)} onClick={() => { setEvents([]); setTopic(t) }}>
            {t.toUpperCase()}
          </button>
        ))}
        <button style={styles.clearBtn} onClick={() => setEvents([])}>Clear</button>
        <span style={{ color: '#475569', fontSize: '0.75rem' }}>{events.length} event{events.length !== 1 ? 's' : ''}</span>
      </div>

      <div style={styles.feed} ref={feedRef}>
        {events.length === 0 ? (
          <div style={styles.empty}>Waiting for events...</div>
        ) : (
          events.map((ev) => (
            <div key={ev.id} style={styles.event(ev.type)}>
              <span style={styles.ts}>{ev.ts}</span>
              <span style={styles.tag(ev.type)}>{ev.type}</span>
              {ev.payload?.event_type && <strong>{ev.payload.event_type} </strong>}
              {ev.payload?.subject_id && <span style={{ color: '#94a3b8' }}>{ev.payload.subject_id} </span>}
              {ev.payload?.actor && <span style={{ color: '#64748b' }}>by {ev.payload.actor}</span>}
              {!ev.payload?.event_type && <span style={{ color: '#94a3b8' }}>{ev.raw.slice(0, 120)}</span>}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
