import { useEffect, useRef } from 'react'
import {
  Ban, Building2, Check, Clock, ExternalLink, File as FileIcon, FileSpreadsheet, FileText, FlaskConical, Handshake,
  Inbox, Lightbulb, Link2, Pause, PartyPopper, ShieldCheck, Star, Truck, X, AlertTriangle,
} from 'lucide-react'
import { avatarColor, dueInfo, initials } from './format'
import { fileUrl } from './api'

export const PHASE_ICON = {
  opportunity: Lightbulb, brief: FileText, india: Building2, feasibility: FlaskConical,
  agreement: Handshake, regulatory: ShieldCheck, launch: Truck,
}

export function PhaseTile({ phase, color, size = 44 }) {
  const Icon = PHASE_ICON[phase] || Lightbulb
  return (
    <span className="tile" style={{ width: size, height: size, '--c': color }} aria-hidden="true">
      <Icon size={size * 0.5} strokeWidth={2} />
    </span>
  )
}

export function Avatar({ name, size = 32 }) {
  return (
    <span className="avatar" style={{ width: size, height: size, background: avatarColor(name), fontSize: size * 0.38 }} title={name}>
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

/** "Suresh Iyer · India Director" with a small photo – used everywhere a person is named */
export function Person({ name, role, size = 26, sub }) {
  return (
    <span className="person-inline">
      <Avatar name={name} size={size} />
      <span><b>{name}</b>{(role || sub) && <small>{role}{sub ? ` · ${sub}` : ''}</small>}</span>
    </span>
  )
}

export function Pill({ tone = 'gray', children, icon: Icon }) {
  return <span className={`pill ${tone}`}>{Icon && <Icon size={13} strokeWidth={2.4} />}{children}</span>
}

export function DuePill({ project, days }) {
  const d = dueInfo(days !== undefined ? { due_days: days } : project)
  if (!d) return null
  return <Pill tone={d.tone} icon={Clock}>{d.text}</Pill>
}

const HEALTH = {
  ok: ['green', 'On track', Check], risk: ['amber', 'At risk', AlertTriangle], late: ['red', 'Late', Clock],
  hold: ['amber', 'On hold', Pause], done: ['green', 'Completed', PartyPopper], stopped: ['gray', 'Stopped', Ban],
}

export function HealthPill({ project }) {
  if (project.status === 'rejected') return <Pill tone="red" icon={X}>Rejected</Pill>
  if (project.status === 'cancelled') return <Pill tone="gray" icon={Ban}>Cancelled</Pill>
  const [tone, label, Icon] = HEALTH[project.health] || HEALTH.ok
  return <Pill tone={tone} icon={Icon}>{label}</Pill>
}

export function StatusPill({ project }) {
  if (project.status === 'active' && project.can_act) return <Pill tone="brand" icon={Check}>Your turn</Pill>
  return <HealthPill project={project} />
}

export function Spinner() {
  return (
    <div className="center-note" role="status" aria-label="Loading">
      <span className="spinner" />
    </div>
  )
}

export function Empty({ title, children }) {
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
    ref.current?.querySelector('input:not([type=radio]),textarea,select')?.focus()
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

export function Field({ label, hint, children, unit }) {
  return (
    <label className="field">
      <span>{label}{unit && <em> ({unit})</em>}</span>
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
    <span className={`role-chip ${ORG_CLASS[org] || ''} ${done || owner.signed ? 'done' : ''}`} title={owner.label}>
      {(done || owner.signed) && <Check size={12} strokeWidth={3} />}
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

const fileIcon = (n = '') => (/\.xlsx?$|\.csv$/i.test(n) ? FileSpreadsheet : /\.(pdf|docx?)$/i.test(n) ? FileText : FileIcon)

/** A document with the same look everywhere: its name, and a file, a link, or both */
export function DocChip({ doc, onRemove, compact, onStar }) {
  const hasFile = doc.has_file
  const hasLink = !!doc.url
  const Icon = hasFile ? fileIcon(doc.filename) : Link2
  const main = hasFile ? fileUrl(`/api/documents/${doc.id}`) : doc.url
  return (
    <span className={`docchip ${!hasFile ? 'link' : ''} ${compact ? 'compact' : ''} ${doc.important ? 'key' : ''}`}>
      <a href={main} target={hasFile ? undefined : '_blank'} rel="noreferrer" title={doc.filename && doc.filename !== doc.title ? `${doc.title} (${doc.filename})` : doc.title}>
        <Icon size={16} />
        <span>{doc.title}</span>
        {doc.important && <Star size={12} className="keymark" aria-label="Key document" />}
        {!hasFile && <ExternalLink size={12} />}
      </a>
      {hasFile && hasLink && <a className="also" href={doc.url} target="_blank" rel="noreferrer" aria-label={`Open the link for ${doc.title}`} title="Open the link"><Link2 size={14} /></a>}
      {onStar && <button className={`x star ${doc.pinned ? 'on' : ''}`} onClick={onStar} aria-label={doc.pinned ? `Unmark ${doc.title} as key` : `Mark ${doc.title} as key`} title={doc.pinned ? 'Key document' : 'Mark as key document'}><Star size={14} /></button>}
      {onRemove && <button className="x" onClick={onRemove} aria-label={`Remove ${doc.title}`}><X size={13} /></button>}
    </span>
  )
}

/** A document as a tidy row: name, what it is, and whether it is a file or a link */
export function DocRow({ doc }) {
  const hasFile = doc.has_file
  const Icon = hasFile ? fileIcon(doc.filename) : Link2
  const href = hasFile ? fileUrl(`/api/documents/${doc.id}`) : doc.url
  return (
    <a className="docrow" href={href} target={hasFile ? undefined : '_blank'} rel="noreferrer">
      <span className="dr-ico"><Icon size={17} /></span>
      <span className="dr-main">
        <b>{doc.title}</b>
        <small>{[doc.doc_label, hasFile && doc.url ? 'File and link' : hasFile ? 'File' : 'Link'].filter(Boolean).join(' · ')}</small>
      </span>
      {!hasFile && <ExternalLink size={14} className="dr-go" />}
    </a>
  )
}
