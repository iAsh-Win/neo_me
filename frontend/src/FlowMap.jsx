import { useState } from 'react'
import { Check, ChevronDown, Clock, CornerUpLeft, FastForward, GitBranch, History, Minus, Pause, Users, X } from 'lucide-react'
import { Avatar, PhaseTile, Pill, RoleChip, DuePill } from './ui'
import { useApp } from './ctx'
import { shortDate } from './format'
import { HistoryItem } from './History'

const BRANCH = {
  approve: { icon: Check, cls: 'b-ok' },
  back: { icon: CornerUpLeft, cls: 'b-back' },
  hold: { icon: Pause, cls: 'b-back' },
  reject: { icon: X, cls: 'b-bad' },
}

function branchText(o) {
  if (o.kind === 'back') return `Back to ${o.to_name}`
  if (o.kind === 'approve') return o.to_name ? `Approve → ${o.to_name}` : 'Approve'
  if (o.kind === 'hold') return 'Hold'
  return 'Reject – project closes'
}

function Dot({ state }) {
  if (state === 'done') return <span className="dot done"><Check size={13} strokeWidth={3.2} /></span>
  if (state === 'current') return <span className="dot now" />
  if (state === 'hold') return <span className="dot hold"><Pause size={11} strokeWidth={3} /></span>
  if (state === 'stopped') return <span className="dot stop"><X size={12} strokeWidth={3.2} /></span>
  if (state === 'skipped') return <span className="dot skip"><Minus size={12} /></span>
  return <span className="dot" />
}

function Node({ s, mode, roles, highlightRole, track }) {
  const [open, setOpen] = useState(false)
  const mine = highlightRole && (s.owners.some((o) => o.role === highlightRole) || s.coordinatorRole === highlightRole)
  const last = s.last
  const canOpen = mode === 'project' && (s.events?.length > 0)
  return (
    <li className={`node ${s.state || ''} ${mine ? 'mine' : ''}`}>
      <span className="rail"><Dot state={s.state} /></span>
      <div className="node-body">
        <div className="node-line">
          <span className="node-name">{s.name}</span>
          {s.mode === 'decision' && <Pill tone="purple" icon={GitBranch}>Decision</Pill>}
          {s.all && <Pill tone="amber" icon={Users}>{s.owners.length === 2 ? 'Both sign' : 'All sign'}</Pill>}
          {s.only === 'development' && <Pill tone="blue">Development</Pill>}
          {s.only === 'in_licence' && <Pill tone="blue">In-Licence</Pill>}
          {s.sent_back > 0 && <Pill tone="amber" icon={CornerUpLeft}>Sent back {s.sent_back}×</Pill>}
          {s.state === 'current' && s.due_days != null && <DuePill days={s.due_days} />}
          {track && <span className="track-tag">{track}</span>}
        </div>
        <div className="node-owners">
          {s.owners.map((o) => <RoleChip key={o.role} owner={o} roles={roles} />)}
          {s.coordinator && <span className="role-chip ghost">Coordinator: {s.coordinator}</span>}
        </div>
        {mode === 'project' && last && s.state === 'done' && (
          <div className="node-done">
            <Avatar name={last.user?.name || '?'} size={20} />
            <span><b>{last.result}</b> · {last.user?.name} · {shortDate(last.at)}</span>
            {last.data?.length > 0 && <span className="node-facts">{last.data.slice(0, 2).map((d) => `${d.label}: ${d.value}${d.unit ? ' ' + d.unit : ''}`).join(' · ')}</span>}
          </div>
        )}
        {canOpen && (
          <button className="link node-more" onClick={() => setOpen(!open)} aria-expanded={open}>
            <History size={14} /> {open ? 'Hide history' : `History (${s.events.length})${s.docs?.length ? ` · ${s.docs.length} file${s.docs.length > 1 ? 's' : ''}` : ''}`}
          </button>
        )}
        {open && <ul className="h-list inline">{s.events.map((e) => <HistoryItem key={e.id} e={e} />)}</ul>}
        {mode === 'guide' && s.mode === 'decision' && (
          <div className="branches">
            {s.options.map((o) => {
              const B = BRANCH[o.kind]
              return <span key={o.key} className={`branch ${B.cls}`}><B.icon size={13} strokeWidth={2.6} />{branchText(o)}</span>
            })}
          </div>
        )}
        {mode === 'guide' && (s.docs?.length > 0 || s.fields?.length > 0 || s.checks?.length > 0) && (
          <div className="needs">
            {s.docs?.map((d) => <span key={d.key} className="need-chip">{d.required ? '★ ' : ''}{d.label}</span>)}
            {s.fields?.filter((f) => f.required).map((f) => <span key={f.key} className="need-chip soft">{f.label}</span>)}
            {s.checks?.length > 0 && <span className="need-chip soft">{s.checks.length} check{s.checks.length > 1 ? 's' : ''}</span>}
          </div>
        )}
      </div>
    </li>
  )
}

function GroupBlock({ g, rows, mode, roles, highlightRole }) {
  const fast = mode === 'guide' ? true : g.mode === 'fast'
  const byKey = Object.fromEntries(rows.map((r) => [r.key, r]))
  const label = mode === 'guide' ? 'Can run side by side' : g.mode === 'fast' ? 'Running side by side' : g.mode === 'seq' ? 'One after another' : 'Can run side by side (Fast track)'
  return (
    <div className={`pgroup ${fast ? 'fast' : 'seq'}`}>
      <div className="pg-head">
        <FastForward size={16} /> <b>{g.name}</b>
        <Pill tone={fast ? 'blue' : 'gray'}>{label}</Pill>
      </div>
      {mode === 'guide' && <p className="muted small">{g.why} The project waits until every track is finished.</p>}
      {fast ? (
        <div className="pg-tracks" style={{ gridTemplateColumns: `repeat(${g.tracks.length}, minmax(0, 1fr))` }}>
          {g.tracks.map((t) => (
            <div className="pg-track" key={t.name}>
              <h4>{t.name}</h4>
              <ol className="nodes">{t.steps.map((k) => byKey[k] && <Node key={k} s={byKey[k]} mode={mode} roles={roles} highlightRole={highlightRole} />)}</ol>
            </div>
          ))}
        </div>
      ) : (
        <ol className="nodes">
          {g.tracks.flatMap((t) => t.steps.map((k) => byKey[k] && <Node key={k} s={byKey[k]} mode={mode} roles={roles} highlightRole={highlightRole} track={t.name} />))}
        </ol>
      )}
    </div>
  )
}

/** The Neo flow chart as a live diagram. mode "project": shows progress. mode "guide": shows every branch. */
export default function FlowMap({ steps, groups, mode, openPhase, highlightRole }) {
  const { def, roles } = useApp()
  const [open, setOpen] = useState({})
  const [all, setAll] = useState(mode === 'guide')
  const phaseSteps = (k) => steps.filter((s) => s.phase === k && !(mode === 'project' && s.state === 'skipped'))
  const isOpen = (k) => all || (open[k] ?? (mode === 'guide' || k === openPhase))

  return (
    <div className={`flow ${mode}`}>
      {mode === 'project' && (
        <div className="flow-tools"><button className="link" onClick={() => setAll(!all)}>{all ? 'Show only current stage' : 'Show every step'}</button></div>
      )}
      {def.phases.map((ph, pi) => {
        const list = phaseSteps(ph.key)
        if (!list.length) return null
        const done = list.filter((s) => s.state === 'done').length
        const complete = mode === 'project' && done === list.length
        const current = list.some((s) => s.state === 'current' || s.state === 'hold')
        const emitted = new Set()
        const items = []
        for (const s of list) {
          if (s.group) {
            if (!emitted.has(s.group)) {
              emitted.add(s.group)
              items.push({ type: 'group', g: groups.find((x) => x.id === s.group), rows: list.filter((r) => r.group === s.group) })
            }
          } else items.push({ type: 'step', s })
        }
        const blocks = []
        let buf = []
        for (const it of items) {
          if (it.type === 'step') buf.push(it.s)
          else {
            if (buf.length) { blocks.push({ type: 'steps', list: buf }); buf = [] }
            blocks.push(it)
          }
        }
        if (buf.length) blocks.push({ type: 'steps', list: buf })
        return (
          <section key={ph.key} className={`band ${complete ? 'complete' : ''} ${current ? 'here' : ''}`} style={{ '--c': ph.color }}>
            <button className="band-head" onClick={() => setOpen({ ...open, [ph.key]: !isOpen(ph.key) })} aria-expanded={isOpen(ph.key)}>
              <PhaseTile phase={ph.key} color={ph.color} size={38} />
              <b>{pi + 1}. {ph.name}</b>
              {mode === 'project' && <span className={`band-count ${complete ? 'ok' : ''}`}>{complete ? <Check size={14} strokeWidth={3} /> : `${done}/${list.length}`}</span>}
              <ChevronDown size={18} className={`chev ${isOpen(ph.key) ? '' : 'turn'}`} />
            </button>
            {isOpen(ph.key) && (
              <div className="band-body">
                {blocks.map((b, i) => b.type === 'steps'
                  ? <ol className="nodes" key={i}>{b.list.map((s) => <Node key={s.key} s={s} mode={mode} roles={roles} highlightRole={highlightRole} />)}</ol>
                  : <GroupBlock key={b.g.id} g={b.g} rows={b.rows} mode={mode} roles={roles} highlightRole={highlightRole} />)}
              </div>
            )}
          </section>
        )
      })}
    </div>
  )
}
