import React, { useEffect, useState } from 'react'
import { get } from '../lib/api.js'

export default function Audit() {
  const [entries, setEntries] = useState([])
  const [filter, setFilter] = useState('')
  const [msg, setMsg] = useState('')

  const load = (action = '') => {
    get(`/audit?limit=100${action ? `&action=${encodeURIComponent(action)}` : ''}`)
      .then(setEntries).catch((e) => setMsg(e.message))
  }
  useEffect(() => { load() }, [])

  return (
    <div className="page">
      <h2>Audit Log</h2>
      <p className="sub">Immutable, append-only record of every governed action — your compliance proof.</p>

      <div className="card">
        <div className="toolbar">
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter by action (e.g. budget.blocked)…"
            style={{ maxWidth: 320 }}
          />
          <button className="secondary" onClick={() => load(filter)}>Filter</button>
          <button className="secondary" onClick={() => { setFilter(''); load() }}>Clear</button>
        </div>
        <table>
          <thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Resource</th><th>Detail</th></tr></thead>
          <tbody>
            {entries.map((e) => (
              <tr key={e.id}>
                <td className="muted">{new Date(e.created_at).toLocaleString()}</td>
                <td>{e.actor}</td>
                <td><span className="badge blue">{e.action}</span></td>
                <td className="muted">{e.resource_type}:{e.resource_id ? e.resource_id.slice(0, 8) : '—'}</td>
                <td className="muted">{JSON.stringify(e.detail)}</td>
              </tr>
            ))}
            {entries.length === 0 && <tr><td colSpan={5} className="muted">No audit entries</td></tr>}
          </tbody>
        </table>
      </div>

      {msg && <div className="error">{msg}</div>}
    </div>
  )
}