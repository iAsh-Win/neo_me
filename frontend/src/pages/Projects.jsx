import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Plus, Search } from 'lucide-react'
import { api } from '../api'
import { useApp } from '../ctx'
import { AvatarStack, DuePill, Empty, ErrorNote, JourneyDots, PhaseTile, Spinner, StatusPill } from '../ui'
import { NewProject } from '../modals'

const TABS = [
  ['active', 'In progress'],
  ['mine', 'Needs me'],
  ['on_hold', 'On hold'],
  ['done', 'Finished'],
  ['all', 'All'],
]

const matches = (p, show) =>
  show === 'all' ? true
  : show === 'mine' ? p.can_act
  : show === 'late' ? p.overdue
  : show === 'active' ? p.status === 'active'
  : show === 'done' ? ['completed', 'rejected', 'cancelled'].includes(p.status)
  : p.status === show

export default function Projects() {
  const { def, phases, canAdd } = useApp()
  const nav = useNavigate()
  const [params, setParams] = useSearchParams()
  const show = params.get('show') || 'active'
  const phase = params.get('phase') || ''
  const [q, setQ] = useState('')
  const [list, setList] = useState(null)
  const [err, setErr] = useState('')
  const [adding, setAdding] = useState(false)
  const load = () => api.get('/api/projects').then(setList).catch((e) => setErr(e.message))
  useEffect(() => { load() }, [])
  const setParam = (k, v) => {
    const n = new URLSearchParams(params)
    v ? n.set(k, v) : n.delete(k)
    setParams(n, { replace: true })
  }

  const rows = useMemo(() => {
    if (!list) return []
    const text = q.trim().toLowerCase()
    return list.filter((p) => matches(p, show) && (!phase || p.phase === phase) &&
      (!text || `${p.title} ${p.code || ''} ${p.market} ${p.step_name}`.toLowerCase().includes(text)))
  }, [list, q, show, phase])

  if (err) return <ErrorNote error={err} retry={() => { setErr(''); load() }} />
  if (!list) return <Spinner />
  const count = (k) => list.filter((p) => matches(p, k)).length

  return (
    <div className="page">
      <div className="page-head">
        <h1>Projects</h1>
        <div className="head-actions">
          {canAdd && <button className="btn primary" onClick={() => setAdding(true)}><Plus size={19} /> New project</button>}
        </div>
      </div>

      <div className="toolbar">
        <div className="tabs" role="tablist">
          {TABS.map(([k, label]) => (
            <button key={k} role="tab" aria-selected={show === k} className={show === k ? 'on' : ''} onClick={() => setParam('show', k === 'active' ? '' : k)}>
              {label}<span>{count(k)}</span>
            </button>
          ))}
        </div>
        <div className="search">
          <Search size={18} />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search" aria-label="Search projects" />
        </div>
      </div>
      {(phase || show === 'late') && (
        <div className="filters">
          {phase && <button className="chip on" onClick={() => setParam('phase', '')}>{phases[phase]?.name} ✕</button>}
          {show === 'late' && <button className="chip on" onClick={() => setParam('show', '')}>Overdue ✕</button>}
        </div>
      )}

      {rows.length === 0 && <Empty title="Nothing here">{canAdd && show === 'active' ? 'Press “New project” to add the first one.' : 'No projects match.'}</Empty>}

      <div className="cards">
        {rows.map((p) => (
          <button key={p.id} className={`pcard ${p.can_act ? 'mine' : ''}`} onClick={() => nav(`/projects/${p.id}`)}>
            <div className="pcard-top">
              <PhaseTile phase={p.phase} color={phases[p.phase]?.color} size={44} />
              <span className="task-main">
                <b>{p.title}</b>
                <small>{p.code || 'No code yet'} · {p.ptype_label}</small>
              </span>
            </div>
            <JourneyDots phases={def.phases} current={p.phase} status={p.status} />
            <div className="pcard-step">{p.active.length > 1 ? `${p.active.length} steps side by side` : p.step_name}</div>
            <div className="pcard-foot">
              {p.waiting.length > 0 ? <AvatarStack names={p.waiting.flatMap((w) => w.people)} size={26} /> : <span />}
              <span className="pcard-pills"><DuePill project={p} /><StatusPill project={p} /></span>
            </div>
          </button>
        ))}
      </div>
      {adding && <NewProject onClose={() => setAdding(false)} />}
    </div>
  )
}
