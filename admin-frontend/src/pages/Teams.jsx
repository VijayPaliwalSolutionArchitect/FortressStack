import React, { useEffect, useState } from 'react'
import { get, post, patch } from '../lib/api.js'

export default function Teams() {
  const [teams, setTeams] = useState([])
  const [form, setForm] = useState({ name: '', budget_usd: 50, rate_limit_rpm: 60, models: 'llama3.1:8b' })
  const [msg, setMsg] = useState('')

  const load = () => get('/teams').then(setTeams).catch((e) => setMsg(e.message))
  useEffect(() => { load() }, [])

  const create = async () => {
    setMsg('')
    try {
      await post('/teams', {
        name: form.name, budget_usd: Number(form.budget_usd),
        rate_limit_rpm: Number(form.rate_limit_rpm),
        models: form.models.split(',').map((s) => s.trim()).filter(Boolean),
      })
      setForm({ ...form, name: '' })
      load()
    } catch (e) { setMsg(e.message) }
  }

  const checkBudget = async (team) => {
    try {
      const r = await post('/teams/budget-check', { team_id: team.id, estimated_cost_usd: 0.01 })
      setMsg(`${team.name}: spent $${r.spent_usd} / budget $${r.budget_usd} → ${r.allowed ? 'allowed' : 'BLOCKED'}`)
    } catch (e) { setMsg(e.message) }
  }

  return (
    <div className="page">
      <h2>Teams &amp; Budgets</h2>
      <p className="sub">Per-team LLM budgets, rate limits and allowed models.</p>

      <div className="card">
        <h3>Create Team</h3>
        <div className="form-row">
          <div><label>Name</label><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. Legal" /></div>
          <div><label>Budget (USD)</label><input type="number" value={form.budget_usd} onChange={(e) => setForm({ ...form, budget_usd: e.target.value })} /></div>
          <div><label>Rate limit (RPM)</label><input type="number" value={form.rate_limit_rpm} onChange={(e) => setForm({ ...form, rate_limit_rpm: e.target.value })} /></div>
        </div>
        <div><label>Allowed models (comma-separated)</label><input value={form.models} onChange={(e) => setForm({ ...form, models: e.target.value })} /></div>
        <div style={{ marginTop: 12 }}><button onClick={create}>Create Team</button></div>
      </div>

      <div className="card">
        <h3>Teams</h3>
        <table>
          <thead><tr><th>Name</th><th>Budget</th><th>RPM</th><th>Models</th><th>Actions</th></tr></thead>
          <tbody>
            {teams.map((t) => (
              <tr key={t.id}>
                <td>{t.name}</td>
                <td>${Number(t.budget_usd).toFixed(2)}</td>
                <td>{t.rate_limit_rpm}</td>
                <td className="muted">{(t.models || []).join(', ') || '—'}</td>
                <td><button className="secondary" onClick={() => checkBudget(t)}>Budget check</button></td>
              </tr>
            ))}
            {teams.length === 0 && <tr><td colSpan={5} className="muted">No teams yet</td></tr>}
          </tbody>
        </table>
      </div>

      {msg && <div className={msg.includes('BLOCKED') || msg.includes('Error') ? 'error' : 'success'}>{msg}</div>}
    </div>
  )
}