import React from 'react'
import { Routes, Route, NavLink, Navigate } from 'react-router-dom'
import Teams from './pages/Teams.jsx'
import Models from './pages/Models.jsx'
import Rag from './pages/Rag.jsx'
import Audit from './pages/Audit.jsx'
import Settings from './pages/Settings.jsx'
import Chat from './pages/Chat.jsx'

const NAV = [
  { to: '/teams', label: 'Teams & Budgets', icon: '👥' },
  { to: '/models', label: 'Models', icon: '🧠' },
  { to: '/rag', label: 'RAG Ingestion', icon: '📚' },
  { to: '/chat', label: 'Chat / Voice', icon: '💬' },
  { to: '/audit', label: 'Audit Log', icon: '🛡️' },
  { to: '/settings', label: 'Settings', icon: '⚙️' },
]

export default function App() {
  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">🔐</span>
          <div>
            <h1>FortressStack</h1>
            <p>Admin Console</p>
          </div>
        </div>
        <nav>
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              className={({ isActive }) => 'nav-item' + (isActive ? ' active' : '')}
            >
              <span>{n.icon}</span> {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">v1.0.0 · local-mode</div>
      </aside>
      <main className="content">
        <Routes>
          <Route path="/" element={<Navigate to="/teams" replace />} />
          <Route path="/teams" element={<Teams />} />
          <Route path="/models" element={<Models />} />
          <Route path="/rag" element={<Rag />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/audit" element={<Audit />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
    </div>
  )
}