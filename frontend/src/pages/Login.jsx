import { useEffect, useState } from 'react'
import { Eye, EyeOff, ShieldCheck, Workflow, BellRing } from 'lucide-react'
import { api } from '../api'
import { useApp } from '../ctx'
import { Avatar } from '../ui'

export default function Login() {
  const { login } = useApp()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [show, setShow] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [demo, setDemo] = useState([])

  useEffect(() => {
    api.get('/api/auth/demo-users').then(setDemo).catch(() => {})
  }, [])

  const go = async (e, p) => {
    setBusy(true)
    setError('')
    try {
      await login(e, p)
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }
  const orgs = [...new Set(demo.map((d) => d.org))]

  return (
    <div className="login">
      <section className="login-hero">
        <img src="/neo-logo.png" alt="Neo India Lifeline" />
        <h1>Every project.<br />One clear path.</h1>
        <ul>
          <li><span><Workflow size={20} /></span><div><b>Follow the flow</b><small>From idea to dispatch, step by step</small></div></li>
          <li><span><ShieldCheck size={20} /></span><div><b>See only your work</b><small>Tasks that need you, nothing else</small></div></li>
          <li><span><BellRing size={20} /></span><div><b>Nothing gets missed</b><small>Alerts, reminders and escalation</small></div></li>
        </ul>
        <svg className="hero-art" viewBox="0 0 420 120" aria-hidden="true">
          <g fill="none" stroke="#5a2d86" strokeWidth="3" strokeLinecap="round">
            <path d="M30 60 H390" opacity=".25" />
            <path d="M30 60 H250" />
          </g>
          {[30, 110, 190, 250].map((x) => <circle key={x} cx={x} cy="60" r="13" fill="#18a07f" />)}
          <circle cx="250" cy="60" r="19" fill="#5a2d86" /><circle cx="250" cy="60" r="8" fill="#fff" />
          {[330, 390].map((x) => <circle key={x} cx={x} cy="60" r="13" fill="#fff" stroke="#cdbfe0" strokeWidth="3" />)}
          <path d="M26 60 l5 5 l9 -10" transform="translate(-1 0)" stroke="#fff" strokeWidth="3" fill="none" strokeLinecap="round" />
        </svg>
      </section>

      <section className="login-panel">
        <form className="login-card" onSubmit={(e) => { e.preventDefault(); go(email, password) }}>
          <h2>Welcome back</h2>
          <p className="muted">Sign in to see what needs you today.</p>
          <label className="field">
            <span>Email</span>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" required />
          </label>
          <label className="field">
            <span>Password</span>
            <div className="pw">
              <input type={show ? 'text' : 'password'} value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
              <button type="button" className="icon-btn" onClick={() => setShow(!show)} aria-label={show ? 'Hide password' : 'Show password'}>{show ? <EyeOff size={18} /> : <Eye size={18} />}</button>
            </div>
          </label>
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="btn primary big block" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
        </form>

        {demo.length > 0 && (
          <div className="demo">
            <h3>Demo accounts <small>password for all: neo@123</small></h3>
            {orgs.map((org) => (
              <div key={org} className="demo-org">
                <small>{org}</small>
                <div className="demo-grid">
                  {demo.filter((d) => d.org === org).map((u) => (
                    <button key={u.email} className="demo-user" disabled={busy} onClick={() => go(u.email, 'neo@123')}>
                      <Avatar name={u.name} size={28} />
                      <span><strong>{u.name}</strong><small>{u.role_label}</small></span>
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
