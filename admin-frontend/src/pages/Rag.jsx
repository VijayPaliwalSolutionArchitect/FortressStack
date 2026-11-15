import React, { useEffect, useState } from 'react'
import { get, post, uploadDocument } from '../lib/api.js'

export default function Rag() {
  const [corpora, setCorpora] = useState([])
  const [teams, setTeams] = useState([])
  const [selected, setSelected] = useState(null)
  const [docs, setDocs] = useState([])
  const [msg, setMsg] = useState('')
  const [form, setForm] = useState({ team_id: '', name: '', description: '' })
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])

  const loadAll = () => {
    get('/rag/corpora').then(setCorpora).catch((e) => setMsg(e.message))
    get('/teams').then(setTeams).catch(() => {})
  }
  useEffect(() => { loadAll() }, [])

  const select = async (c) => {
    setSelected(c)
    setResults([])
    try { setDocs(await get(`/rag/corpora/${c.id}/documents`)) }
    catch (e) { setMsg(e.message) }
  }

  const createCorpus = async () => {
    setMsg('')
    try {
      await post('/rag/corpora', form)
      setForm({ ...form, name: '', description: '' })
      loadAll()
    } catch (e) { setMsg(e.message) }
  }

  const upload = async (e) => {
    setMsg('')
    const file = e.target.files[0]
    if (!file || !selected) return
    try {
      const r = await uploadDocument(selected.id, file)
      setMsg(`Ingested "${file.name}" → ${r.chunks} chunks (${r.status})`)
      select(selected)
    } catch (err) { setMsg(err.message) }
  }

  const search = async () => {
    setMsg('')
    try {
      const r = await post('/rag/retrieve', { corpus_id: selected.id, query })
      setResults(r.results)
    } catch (e) { setMsg(e.message) }
  }

  return (
    <div className="page">
      <h2>RAG Ingestion</h2>
      <p className="sub">Upload documents, chunk &amp; embed them, and query corpora with cited answers.</p>

      <div className="card">
        <h3>Create Corpus</h3>
        <div className="form-row">
          <div><label>Team</label>
            <select value={form.team_id} onChange={(e) => setForm({ ...form, team_id: e.target.value })}>
              <option value="">Select team…</option>
              {teams.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </div>
          <div><label>Name</label><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
          <div><label>Description</label><input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></div>
        </div>
        <div style={{ marginTop: 12 }}><button onClick={createCorpus}>Create Corpus</button></div>
      </div>

      <div className="card">
        <h3>Corpora</h3>
        <table>
          <thead><tr><th>Name</th><th>Team</th><th>Docs</th><th>Created</th><th></th></tr></thead>
          <tbody>
            {corpora.map((c) => (
              <tr key={c.id} onClick={() => select(c)} style={{ cursor: 'pointer' }}>
                <td>{c.name}</td><td className="muted">{c.team_name}</td>
                <td>{c.document_count}</td><td className="muted">{new Date(c.created_at).toLocaleDateString()}</td>
                <td>{selected?.id === c.id ? <span className="badge blue">selected</span> : <span className="muted">select</span>}</td>
              </tr>
            ))}
            {corpora.length === 0 && <tr><td colSpan={5} className="muted">No corpora yet</td></tr>}
          </tbody>
        </table>
      </div>

      {selected && (
        <>
          <div className="card">
            <h3>Upload to "{selected.name}"</h3>
            <input type="file" onChange={upload} />
            <p className="muted" style={{ marginTop: 8, fontSize: 12 }}>PDF, DOCX, TXT, MD, CSV · max 50MB</p>
          </div>

          <div className="card">
            <h3>Documents</h3>
            <table>
              <thead><tr><th>File</th><th>Type</th><th>Size</th><th>Chunks</th><th>Status</th></tr></thead>
              <tbody>
                {docs.map((d) => (
                  <tr key={d.id}>
                    <td>{d.filename}</td><td className="muted">{d.mime_type}</td>
                    <td>{(d.size_bytes / 1024).toFixed(1)} KB</td><td>{d.chunk_count}</td>
                    <td>
                      {d.status === 'ready' ? <span className="badge green">ready</span>
                        : d.status === 'failed' ? <span className="badge red">failed</span>
                        : <span className="badge amber">{d.status}</span>}
                    </td>
                  </tr>
                ))}
                {docs.length === 0 && <tr><td colSpan={5} className="muted">No documents</td></tr>}
              </tbody>
            </table>
          </div>

          <div className="card">
            <h3>Query Corpus</h3>
            <div className="chat-input">
              <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Ask your documents…" onKeyDown={(e) => e.key === 'Enter' && search()} />
              <button onClick={search}>Search</button>
            </div>
            {results.length > 0 && (
              <div style={{ marginTop: 14 }}>
                {results.map((r, i) => (
                  <div key={r.chunk_id} className="msg assistant" style={{ marginBottom: 8 }}>
                    <strong>[{i + 1}]</strong> {r.content}
                    <span className="cite">score {r.score}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}

      {msg && <div className={msg.includes('Error') || msg.includes('failed') ? 'error' : 'success'}>{msg}</div>}
    </div>
  )
}