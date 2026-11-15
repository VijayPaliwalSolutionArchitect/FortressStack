import React, { useEffect, useRef, useState } from 'react'
import { get, post } from '../lib/api.js'

export default function Chat() {
  const [teams, setTeams] = useState([])
  const [corpora, setCorpora] = useState([])
  const [teamId, setTeamId] = useState('')
  const [corpusId, setCorpusId] = useState('')
  const [mode, setMode] = useState('text')
  const [recording, setRecording] = useState(false)
  const [message, setMessage] = useState('')
  const [log, setLog] = useState([])
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  const logRef = useRef(null)

  useEffect(() => {
    get('/teams').then(setTeams).catch((e) => setMsg(e.message))
    get('/rag/corpora').then(setCorpora).catch(() => {})
  }, [])

  useEffect(() => { logRef.current?.scrollTo(0, logRef.current.scrollHeight) }, [log])

  const send = async (overrideMsg) => {
    const text = (overrideMsg ?? message).trim()
    if (!text || !teamId) { setMsg('Select a team and type a message'); return }
    setBusy(true); setMsg('')
    setLog((l) => [...l, { role: 'user', content: text }])
    setMessage('')
    try {
      const r = await post('/chat', {
        team_id: teamId, message: text, corpus_id: corpusId || null,
        mode, stream: false,
      })
      setLog((l) => [...l, { role: 'assistant', content: r.reply, citations: r.citations }])
    } catch (e) { setLog((l) => [...l, { role: 'assistant', content: `⚠ ${e.message}` }]) }
    setBusy(false)
  }

  // Minimal voice capture: uses the Web Speech API to transcribe locally.
  const toggleVoice = () => {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
      setMsg('Voice input requires a browser with Web Speech API (Chrome/Edge)')
      return
    }
    setMode('voice')
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    const rec = new SR()
    rec.lang = 'en-US'
    rec.interimResults = false
    rec.onstart = () => setRecording(true)
    rec.onend = () => setRecording(false)
    rec.onresult = (ev) => {
      const transcript = ev.results[0][0].transcript
      setMessage(transcript)
      send(transcript)
    }
    rec.onerror = () => setRecording(false)
    rec.start()
  }

  return (
    <div className="page">
      <h2>Chat / Voice</h2>
      <p className="sub">Text/Voice dual mode — every call is budget-checked and audited.</p>

      <div className="card">
        <div className="form-row">
          <div><label>Team</label>
            <select value={teamId} onChange={(e) => setTeamId(e.target.value)}>
              <option value="">Select team…</option>
              {teams.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </div>
          <div><label>RAG corpus (optional)</label>
            <select value={corpusId} onChange={(e) => setCorpusId(e.target.value)}>
              <option value="">None</option>
              {corpora.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
          <div><label>Mode</label>
            <select value={mode} onChange={(e) => setMode(e.target.value)}>
              <option value="text">Text</option><option value="voice">Voice</option>
            </select>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="chat-window">
          <div className="chat-log" ref={logRef}>
            {log.length === 0 && <div className="muted" style={{ textAlign: 'center', marginTop: 40 }}>Start a conversation…</div>}
            {log.map((m, i) => (
              <div key={i} className={`msg ${m.role}`}>
                {m.content}
                {m.citations?.length > 0 && (
                  <span className="cite">cited {m.citations.length} source{m.citations.length > 1 ? 's' : ''}</span>
                )}
              </div>
            ))}
          </div>
          <div className="chat-input">
            <input
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !busy && send()}
              placeholder="Type a message…"
              disabled={busy}
            />
            <button className="voice-btn" onClick={toggleVoice} disabled={busy}>
              {recording ? '🔴 Listening…' : '🎤 Voice'}
            </button>
            <button onClick={() => send()} disabled={busy || !message.trim()}>{busy ? '…' : 'Send'}</button>
          </div>
        </div>
      </div>

      {msg && <div className="error">{msg}</div>}
    </div>
  )
}