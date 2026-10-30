import { useState } from 'react'
import { Check, ChevronDown, CornerUpLeft, GitBranch, Pause, Users, X, Minus } from 'lucide-react'
import { Avatar, PhaseTile, Pill, RoleChip } from './ui'
import { useApp } from './ctx'
import { shortDate } from './format'

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

/** The Neo flow chart as a live diagram. mode "project": shows progress. mode "guide": shows every branch. */
export default function FlowMap({ steps, mode, openPhase, highlightRole }) {
  const { def, roles } = useApp()
  const [open, setOpen] = useState({})
  const [all, setAll] = useState(mode === 'guide')
  const phaseSteps = (k) => steps.filter((s) => s.phase === k && !(mode === 'project' && s.state === 'skipped'))
  const isOpen = (k) => all || (open[k] ?? (mode === 'guide' || k === openPhase))

  return (
    <div className={`flow ${mode}`}>
      {mode === 'project' && (
        <div className="flow-tools"><button className="link" onClick={() => setAll(!all)}>{all ? 'Show only current phase' : 'Show every step'}</button></div>
      )}
      {def.phases.map((ph) => {
        const list = phaseSteps(ph.key)
        if (!list.length) return null
        const done = list.filter((s) => s.state === 'done').length
        const complete = mode === 'project' && done === list.length
        const current = list.some((s) => s.state === 'current' || s.state === 'hold')
        return (
          <section key={ph.key} className={`band ${complete ? 'complete' : ''} ${current ? 'here' : ''}`} style={{ '--c': ph.color }}>
            <button className="band-head" onClick={() => setOpen({ ...open, [ph.key]: !isOpen(ph.key) })} aria-expanded={isOpen(ph.key)}>
              <PhaseTile phase={ph.key} color={ph.color} size={38} />
              <b>{ph.name}</b>
              {mode === 'project' && <span className={`band-count ${complete ? 'ok' : ''}`}>{complete ? <Check size={14} strokeWidth={3} /> : `${done}/${list.length}`}</span>}
              <ChevronDown size={18} className={`chev ${isOpen(ph.key) ? '' : 'turn'}`} />
            </button>
            {isOpen(ph.key) && (
              <ol className="nodes">
                {list.map((s) => {
                  const mine = highlightRole && (s.owners.some((o) => o.role === highlightRole) || s.coordinatorRole === highlightRole)
                  const last = s.last
                  return (
                    <li key={s.key} className={`node ${s.state || ''} ${mine ? 'mine' : ''}`}>
                      <span className="rail"><Dot state={s.state} /></span>
                      <div className="node-body">
                        <div className="node-line">
                          <span className="node-name">{s.name}</span>
                          {s.mode === 'decision' && <Pill tone="purple" icon={GitBranch}>Decision</Pill>}
                          {s.all && <Pill tone="amber" icon={Users}>{s.owners.length === 2 ? 'Both sign' : 'All sign'}</Pill>}
                          {s.only === 'development' && <Pill tone="blue">Development</Pill>}
                          {s.only === 'in_licence' && <Pill tone="blue">In-Licence</Pill>}
                          {s.sent_back > 0 && <Pill tone="amber" icon={CornerUpLeft}>Sent back {s.sent_back}×</Pill>}
                        </div>
                        <div className="node-owners">
                          {s.owners.map((o) => <RoleChip key={o.role} owner={o} roles={roles} />)}
                          {s.coordinator && <span className="role-chip ghost">Coordinator: {s.coordinator}</span>}
                        </div>
                        {mode === 'project' && last && s.state === 'done' && (
                          <div className="node-done">
                            <Avatar name={last.user?.name || '?'} size={20} />
                            <span><b>{last.option_label ? last.result : last.result}</b> · {last.user?.name} · {shortDate(last.at)}</span>
                          </div>
                        )}
                        {mode === 'project' && last?.note && ['done', 'current', 'hold'].includes(s.state) && <q>{last.note}</q>}
                        {mode === 'guide' && s.mode === 'decision' && (
                          <div className="branches">
                            {s.options.map((o) => {
                              const B = BRANCH[o.kind]
                              return <span key={o.key} className={`branch ${B.cls}`}><B.icon size={13} strokeWidth={2.6} />{branchText(o)}</span>
                            })}
                          </div>
                        )}
                      </div>
                    </li>
                  )
                })}
              </ol>
            )}
          </section>
        )
      })}
    </div>
  )
}
