import { useEffect, useRef } from 'react'
import {
  BadgeIndianRupee, Building2, Check, FileText, FlaskConical, Handshake, Inbox, Lightbulb, Palette, Printer,
  ShieldCheck, Truck, X, Clock, Pause, Ban, PartyPopper,
} from 'lucide-react'
import { avatarColor, dueInfo, initials, STATUS } from './format'

export const PHASE_ICON = {
  idea: Lightbulb, brief: FileText, india: Building2, feasibility: FlaskConical, commercial: BadgeIndianRupee,
  agreement: Handshake, regulatory: ShieldCheck, concept: Palette, print: Printer, launch: Truck,
}

export function PhaseTile({ phase, color, size = 44 }) {
  const Icon = PHASE_ICON[phase] || Lightbulb
  return (
    <span className="tile" style={{ width: size, height: size, '--c': color }} aria-hidden="true">
      <Icon size={size * 0.5} strokeWidth={2} />
    </span>
  )
}

export function Avatar({ name, size = 32, ring }) {
  return (
    <span className={`avatar ${ring ? 'ring' : ''}`} style={{ width: size, height: size, background: avatarColor(name), fontSize: size * 0.38 }} title={name}>
      {initials(name)}
    </span>
  )
}

export function AvatarStack({ names, size = 28, max = 3 }) {
  const shown = names.slice(0, max)
  return (
    <span className="avs" title={names.join(', ')}>
      {shown.map((n) => <Avatar key={n} name={n} size={size} />)}
      {names.length > max && <span className="avatar more" style={{ width: size, height: size, fontSize: size * 0.38 }}>+{names.length - max}</span>}
    </span>
  )
}

export function Pill({ tone = 'gray', children, icon: Icon }) {
  return <span className={`pill ${tone}`}>{Icon && <Icon size={13} strokeWidth={2.4} />}{children}</span>
}

export function DuePill({ project }) {
  const d = dueInfo(project)
  if (!d) return null
  return <Pill tone={d.tone} icon={Clock}>{d.text}</Pill>
}

export function StatusPill({ project }) {
  if (project.status === 'active' && project.can_act) return <Pill tone="brand" icon={Check}>Your turn</Pill>
  if (project.status === 'active') return <Pill tone="blue" icon={Clock}>Waiting</Pill>
  const s = STATUS[project.status]
  const Icon = { on_hold: Pause, rejected: X, cancelled: Ban, completed: PartyPopper }[project.status]
  return <Pill tone={s.tone} icon={Icon}>{s.label}</Pill>
}

export function Spinner() {
  return (
    <div className="center-note" role="status" aria-label="Loading">
      <span className="spinner" />
    </div>
  )
}

export function Empty({ title, children, art = 'inbox' }) {
  return (
    <div className="empty">
      <span className="empty-art"><Inbox size={34} strokeWidth={1.5} /></span>
      <strong>{title}</strong>
      {children && <p>{children}</p>}
    </div>
  )
}

export function ErrorNote({ error, retry }) {
  return (
    <div className="empty">
      <strong>We could not open this</strong>
      <p>{error}</p>
      {retry && <button className="btn" onClick={retry}>Try again</button>}
    </div>
  )
}

export function Modal({ title, onClose, children, footer, size }) {
  const ref = useRef()
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    ref.current?.querySelector('input,textarea,select')?.focus()
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])
  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`modal ${size || ''}`} role="dialog" aria-modal="true" aria-label={title} ref={ref}>
        <header>
          <h2>{title}</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Close"><X size={20} /></button>
        </header>
        <div className="modal-body">{children}</div>
        {footer && <footer>{footer}</footer>}
      </div>
    </div>
  )
}

export function Field({ label, hint, children }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  )
}

export const ORG_CLASS = { 'Neo Health (OTC)': 'o-otc', 'Neo India Lifeline': 'o-india', Manufacturer: 'o-cmo', Office: 'o-office' }

/** Small coloured label for a team: "Reg. Head", "Legal" … */
export function RoleChip({ owner, roles, done }) {
  const org = roles?.[owner.role]?.org
  return (
    <span className={`role-chip ${ORG_CLASS[org] || ''} ${done ? 'done' : ''}`} title={owner.label}>
      {done && <Check size={12} strokeWidth={3} />}
      {owner.short}
    </span>
  )
}

export function JourneyDots({ phases, current, status }) {
  const idx = phases.findIndex((p) => p.key === current)
  return (
    <span className="dots" aria-hidden="true">
      {phases.map((p, i) => (
        <i key={p.key} className={status === 'completed' || i < idx ? 'done' : i === idx ? 'cur' : ''} style={{ '--c': p.color }} />
      ))}
    </span>
  )
}
