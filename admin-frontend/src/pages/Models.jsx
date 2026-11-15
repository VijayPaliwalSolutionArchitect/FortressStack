import React, { useEffect, useState } from 'react'
import { get, post, patch } from '../lib/api.js'

export default function Models() {
  const [models, setModels] = useState([])
  const [msg, setMsg] = useState('')
  const [form, setForm] = useState({ name: '', provider: 'ollama', context_window: 8192, max_tokens: 4096, cpu_only: true, resource_limit_mb: 4096 })

  const load = () => get('/models').then(setModels).catch((e) => setMsg(e.message))
  useEffect(() => { load() }, [])

  const create = async () => {
    setMsg('')
    try {
      await post('/models', { ...form, context_window: Number(form.context_window), max_tokens: Number(form.max_tokens), resource_limit_mb: Number(form.resource_limit_mb) })
      setForm({ ...form, name: '' })
      load()
    } catch (e) { setMsg(e.message) }
  }

  const toggle = async (m) => {
    try { await patch(`/models/${m.id}`, { enabled: !m.enabled }); load() }
    catch (e) { setMsg(e.message) }
  }

  return (
    <div className="page">
      <h2>Model Catalogue</h2>
      <p className="sub">Approved local models with per-model resource limits.</p>

      <div className="card">
        <h3>Register Model</h3>
        <div className="form-row">
          <div><label>Name</label><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="llama3.1:8b" /></div>
          <div><label>Provider</label><select value={form.provider} onChange={(e) => setForm({ ...form, provider: e.target.value })}><option value="ollama">ollama</option></select></div>
          <div><label>Context window</label><input type="number" value={form.context_window} onChange={(e) => setForm({ ...form, context_window: e.target.value })} /></div>
          <div><label>Max tokens</label><input type="number" value={form.max_tokens} onChange={(e) => setForm({ ...form, max_tokens: e.target.value })} /></div>
        </div>
        <div className="form-row">
          <div><label>Resource limit (MB)</label><input type="number" value={form.resource_limit_mb} onChange={(e) => setForm({ ...form, resource_limit_mb: e.target.value })} /></div>
          <div><label>CPU only</label><select value={form.cpu_only} onChange={(e) => setForm({ ...form, cpu_only: e.target.value === 'true' })}><option value="true">Yes</option><option value="false">No (GPU)</option></select></div>
        </div>
        <div style={{ marginTop: 12 }}><button onClick={create}>Register Model</button></div>
      </div>

      <div className="card">
        <h3>Models</h3>
        <table>
          <thead><tr><th>Name</th><th>Provider</th><th>Context</th><th>Max Tokens</th><th>CPU</th><th>Status</th><th></th></tr></thead>
          <tbody>
            {models.map((m) => (
              <tr key={m.id}>
                <td>{m.name}</td>
                <td className="muted">{m.provider}</td>
                <td>{m.context_window}</td>
                <td>{m.max_tokens}</td>
                <td>{m.cpu_only ? 'Yes' : 'GPU'}</td>
                <td>{m.enabled ? <span className="badge green">enabled</span> : <span className="badge red">disabled</span>}</td>
                <td><button className="secondary" onClick={() => toggle(m)}>{m.enabled ? 'Disable' : 'Enable'}</button></td>
              </tr>
            ))}
            {models.length === 0 && <tr><td colSpan={7} className="muted">No models registered</td></tr>}
          </tbody>
        </table>
      </div>

      {msg && <div className="error">{msg}</div>}
    </div>
  )
}