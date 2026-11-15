import React, { useEffect, useState } from 'react'
import { get, put } from '../lib/api.js'

export default function Settings() {
  const [settings, setSettings] = useState([])
  const [msg, setMsg] = useState('')

  const load = () => get('/settings').then(setSettings).catch((e) => setMsg(e.message))
  useEffect(() => { load() }, [])

  const save = async (s) => {
    setMsg('')
    try {
      await put(`/settings/${encodeURIComponent(s.key)}`, { value: s.editValue, description: s.description })
      load()
    } catch (e) { setMsg(e.message) }
  }

  const update = (key, val) => setSettings((arr) => arr.map((s) => s.key === key ? { ...s, editValue: val } : s))

  return (
    <div className="page">
      <h2>Settings</h2>
      <p className="sub">Runtime policy — change behaviour without redeploying. Every change is audited.</p>

      <div className="card">
        <table>
          <thead><tr><th>Key</th><th>Value</th><th>Description</th><th></th></tr></thead>
          <tbody>
            {settings.map((s) => (
              <tr key={s.key}>
                <td><code>{s.key}</code></td>
                <td>
                  <input
                    value={s.editValue ?? s.value}
                    onChange={(e) => update(s.key, e.target.value)}
                    style={{ width: 120 }}
                  />
                </td>
                <td className="muted">{s.description}</td>
                <td><button className="secondary" onClick={() => save({ ...s, editValue: s.editValue ?? s.value })}>Save</button></td>
              </tr>
            ))}
            {settings.length === 0 && <tr><td colSpan={4} className="muted">No settings yet</td></tr>}
          </tbody>
        </table>
      </div>

      {msg && <div className="error">{msg}</div>}
    </div>
  )
}