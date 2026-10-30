import { useEffect, useRef, useState } from 'react'
import { NavLink, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import {
  AlertTriangle, ArrowRight, Bell, BellRing, Check, CornerUpLeft, FolderKanban, Home as HomeIcon, KeyRound, LogOut,
  MessageSquare, Network, Pause, Route as RouteIcon, X,
} from 'lucide-react'
import { useApp } from './ctx'
import { api } from './api'
import { Avatar, Spinner } from './ui'
import { ago } from './format'
import { ChangePassword } from './modals'
import Login from './pages/Login'
import Home from './pages/Home'
import Projects from './pages/Projects'
import ProjectPage from './pages/ProjectPage'
import ProcessMap from './pages/ProcessMap'
import Team from './pages/Team'

const KIND = {
  turn: { icon: ArrowRight, cls: 'k-turn' },
  back: { icon: CornerUpLeft, cls: 'k-warn' },
  hold: { icon: Pause, cls: 'k-warn' },
  reject: { icon: X, cls: 'k-bad' },
  done: { icon: Check, cls: 'k-ok' },
  remind: { icon: BellRing, cls: 'k-warn' },
  escalate: { icon: AlertTriangle, cls: 'k-bad' },
  note: { icon: MessageSquare, cls: 'k-info' },
  info: { icon: Bell, cls: 'k-info' },
}

function Bells() {
  const { toast } = useApp()
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState([])
  const seen = useRef(null)
  const nav = useNavigate()
  const loc = useLocation()
  const box = useRef()

  const load = () =>
    api.get('/api/notifications').then((rows) => {
      const top = rows.reduce((m, n) => Math.max(m, n.id), 0)
      if (seen.current != null) {
        const fresh = rows.filter((n) => n.id > seen.current && !n.read)
        if (fresh.length) toast(fresh.length === 1 ? fresh[0].text : `${fresh.length} new notifications`, 'info')
      }
      seen.current = top
      setItems(rows)
    }).catch(() => {})

  useEffect(() => { load() }, [loc.pathname]) // eslint-disable-line
  useEffect(() => {
    const t = setInterval(load, 15000)
    const close = (e) => box.current && !box.current.contains(e.target) && setOpen(false)
    document.addEventListener('mousedown', close)
    return () => {
      clearInterval(t)
      document.removeEventListener('mousedown', close)
    }
  }, []) // eslint-disable-line
  const unread = items.filter((n) => !n.read).length
  useEffect(() => {
    document.title = unread ? `(${unread}) Neo Project Flow` : 'Neo Project Flow'
  }, [unread])

  const readAll = () => api.post('/api/notifications/read').then(load)
  return (
    <div className="bell" ref={box}>
      <button className="icon-btn" onClick={() => setOpen(!open)} aria-label={`Notifications${unread ? `, ${unread} new` : ''}`} aria-expanded={open}>
        <Bell size={21} />
        {unread > 0 && <b>{unread > 9 ? '9+' : unread}</b>}
      </button>
      {open && (
        <div className="popover notif">
          <div className="pop-head">
            <h3>Notifications</h3>
            {unread > 0 && <button className="link" onClick={readAll}>Mark all read</button>}
          </div>
          {items.length === 0 && <p className="muted pad">Nothing yet.</p>}
          <div className="pop-list">
            {items.map((n) => {
              const K = KIND[n.kind] || KIND.info
              return (
                <button key={n.id} className={`note ${n.read ? '' : 'new'}`}
                  onClick={() => { setOpen(false); nav(`/projects/${n.project_id}`); if (!n.read) readAll() }}>
                  <span className={`k ${K.cls}`}><K.icon size={16} strokeWidth={2.4} /></span>
                  <span className="grow"><span>{n.text}</span><small>{ago(n.at)}</small></span>
                </button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

function UserMenu({ onPassword, compact }) {
  const { user, logout, roles } = useApp()
  const [open, setOpen] = useState(false)
  const box = useRef()
  useEffect(() => {
    const close = (e) => box.current && !box.current.contains(e.target) && setOpen(false)
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])
  return (
    <div className={`me ${compact ? 'compact mobile-only' : ''}`} ref={box}>
      <button className="me-btn" onClick={() => setOpen(!open)} aria-expanded={open} aria-label="My account">
        <Avatar name={user.name} size={compact ? 34 : 36} />
        {!compact && <span className="grow"><strong>{user.name}</strong><small>{roles[user.role]?.short}</small></span>}
      </button>
      {open && (
        <div className={`popover small ${compact ? '' : 'up'}`} onClick={() => setOpen(false)}>
          {compact && <div className="pop-who"><b>{user.name}</b><small>{roles[user.role]?.label}</small></div>}
          <button onClick={onPassword}><KeyRound size={17} /> Change password</button>
          <button onClick={logout}><LogOut size={17} /> Sign out</button>
        </div>
      )}
    </div>
  )
}

function Layout({ children }) {
  const { oversight } = useApp()
  const [pw, setPw] = useState(false)
  const nav = [
    { to: '/', label: 'Home', icon: HomeIcon, end: true },
    { to: '/projects', label: 'Projects', icon: FolderKanban },
    { to: '/process', label: 'Process map', short: 'Process', icon: RouteIcon },
    ...(oversight ? [{ to: '/team', label: 'Team', icon: Network }] : []),
  ]
  return (
    <div className="shell">
      <aside className="side">
        <div className="brand"><img src="/neo-logo.png" alt="Neo India Lifeline" /></div>
        <nav>
          {nav.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end} className="nav-item">
              <n.icon size={20} /><span>{n.label}</span>
            </NavLink>
          ))}
        </nav>
        <UserMenu onPassword={() => setPw(true)} />
      </aside>
      <div className="main">
        <header className="topbar">
          <img className="mobile-logo" src="/neo-logo.png" alt="Neo" />
          <Bells />
          <UserMenu compact onPassword={() => setPw(true)} />
        </header>
        <main>{children}</main>
      </div>
      <nav className="tabbar" aria-label="Main">
        {nav.map((n) => (
          <NavLink key={n.to} to={n.to} end={n.end} className="tab"><n.icon size={22} /><span>{n.short || n.label}</span></NavLink>
        ))}
      </nav>
      {pw && <ChangePassword onClose={() => setPw(false)} />}
    </div>
  )
}

export default function App() {
  const { user, ready, oversight } = useApp()
  const loc = useLocation()
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [loc.pathname])
  if (!ready) return <Spinner />
  if (!user) return <Login />
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/projects" element={<Projects />} />
        <Route path="/projects/:id" element={<ProjectPage />} />
        <Route path="/process" element={<ProcessMap />} />
        {oversight && <Route path="/team" element={<Team />} />}
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </Layout>
  )
}
