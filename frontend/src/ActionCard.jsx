import { useEffect, useState } from 'react'
import { BellRing, Check, CornerUpLeft, FilePlus2, Hand, ListChecks, MoreHorizontal, Pause, X, Clock, Pencil, UserRoundCog } from 'lucide-react'
import { api } from './api'
import { useApp } from './ctx'
import { DocDialog, DocSlot } from './docs'
import { AskTimeDialog, AssignDialog, ChoiceDialog, RequestBox, SendBackDialog, SetDueDialog, TaskDialog, WhyDialog } from './dialogs'
import { Avatar, AvatarStack, DocChip, DocRow, DuePill, Field, PhaseTile } from './ui'
import { ago, shortName } from './format'
import { HandoverPicker, nextsBody } from './handover'

function FieldInput({ f, value, onChange }) {
  const common = { value, onChange: (e) => onChange(e.target.value), 'aria-label': f.label }
  if (f.type === 'textarea') return <textarea rows={3} {...common} />
  if (f.type === 'select') {
    return (
      <select {...common}>
        <option value="">Choose…</option>
        {f.options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    )
  }
  return <input type={f.type === 'number' ? 'number' : f.type === 'date' ? 'date' : 'text'} step="any" {...common} />
}

function OwnerBadge({ o, size = 32, extra = '' }) {
  const names = o.people.length ? o.people : [o.label]
  return (
    <span className="person-inline">
      <AvatarStack names={names} size={size} max={2} />
      <span><b>{names.length > 2 ? `${shortName(names[0])} +${names.length - 1}` : names.map(shortName).join(', ')}</b><small>{o.short}{extra}</small></span>
    </span>
  )
}

/** What the person before me sent along – shown in full, not hidden behind a menu. */
export function Received({ a, user }) {
  const h = a.handover
  if (!h && !(a.from && (a.rework || a.from.id !== user.id))) return null
  const by = h?.by || a.from.name
  const role = h?.role || a.from.short
  const kind = h?.kind || (a.rework ? 'sendback' : 'done')
  if (!h?.has_content && a.from?.id === user.id && !a.rework) return null
  const label = { sendback: 'Sent back to you', fixed: 'Fixed and returned to you', done: 'Handed over to you' }[kind]
  const note = h?.note || a.from?.note
  const where = h?.step_name ? `${kind === 'sendback' ? 'from' : 'after'} “${h.step_name}”` : ''
  const hasFacts = h?.data?.length > 0 || h?.checks?.length > 0
  return (
    <section className={`received ${kind === 'sendback' ? 'bad' : ''}`}>
      <header className="rec-head">
        <Avatar name={by} size={36} />
        <div>
          <b>{by} <span className="rec-role">{role}</span></b>
          <small>{label}{where && ` ${where}`} · {ago(a.from?.at || h?.at)}</small>
        </div>
      </header>
      {note && <p className="rec-note">{note}</p>}
      {h?.data?.length > 0 && (
        <dl className="rec-facts">{h.data.map((d) => <div key={d.label}><dt>{d.label}</dt><dd>{d.unit === 'A$' ? `A$ ${Number(d.value).toLocaleString('en-AU')}` : `${d.value}${d.unit ? ` ${d.unit}` : ''}`}</dd></div>)}</dl>
      )}
      {h?.checks?.length > 0 && (
        <ul className="rec-checks">{h.checks.map((c) => <li key={c}><Check size={14} strokeWidth={3} />{c}</li>)}</ul>
      )}
      {h?.docs?.length > 0 && <div className="rec-docs">{h.docs.map((d) => <DocRow key={d.id} doc={d} />)}</div>}
      {!note && !hasFacts && !(h?.docs?.length > 0) && <p className="rec-empty">Nothing else was attached.</p>}
      {a.rework && a.return_to_name && (
        <footer className="rec-return"><CornerUpLeft size={14} /> When you finish, it returns to <b>{a.return_to_user?.name || by}</b> for “{a.return_to_name}”.</footer>
      )}
    </section>
  )
}

/** A step waiting for me: everything I need to finish it, in one card. */
export function MyCard({ p, a, onChange }) {
  const { toast, phases, user } = useApp()
  const init = () => Object.fromEntries(a.fields.map((f) => [f.key, f.value || '']))
  const [data, setData] = useState(init)
  const [checks, setChecks] = useState([])
  const [note, setNote] = useState('')
  const [showNote, setShowNote] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [dlg, setDlg] = useState(null)
  const [menu, setMenu] = useState(false)
  const [nexts, setNexts] = useState({})
  const [more, setMore] = useState(false)
  useEffect(() => { setData(init()); setChecks([]); setNote(''); setError(''); setNexts({}) }, [a.run_id]) // eslint-disable-line

  const approves = a.options.filter((o) => o.kind === 'approve')
  const backs = a.options.filter((o) => o.kind === 'back')
  const stops = a.options.filter((o) => o.kind === 'hold' || o.kind === 'reject')
  const canSendBack = a.targets.length > 0
  const base = `/api/projects/${p.id}/runs/${a.run_id}`
  const nextFor = a.mode === 'decision' ? a.next[approves[0]?.key] : a.next.done

  const run = async (option, nx = nextFor) => {
    setBusy(true)
    setError('')
    try {
      const r = await api.post(`${base}/act`, { option, note, data, checks, nexts: nextsBody(nx, nexts) })
      setDlg(null)
      toast(r.message)
      onChange(r.project)
    } catch (e) {
      setDlg(null)
      setError(e.message)
    }
    setBusy(false)
  }
  const toggle = (k) => setChecks(checks.includes(k) ? checks.filter((x) => x !== k) : [...checks, k])
  const needs = a.docs.length > 0 || a.fields.length > 0 || a.checks.length > 0

  return (
    <section className={`nowcard mine ${a.rework ? 'rework' : ''}`} aria-live="polite">
      <div className="now-top">
        <PhaseTile phase={wfPhase(p, a)} color={phases[wfPhase(p, a)]?.color} size={46} />
        <div className="grow">
          <span className="now-tag">{a.rework ? 'Sent back to you' : 'Your turn'}</span>
          <h2>{a.name}</h2>
        </div>
        <DuePill days={a.due_days} />
        <div className="menu">
          <button className="icon-btn" onClick={() => setMenu(!menu)} aria-label="More" aria-expanded={menu}><MoreHorizontal size={20} /></button>
          {menu && (
            <div className="popover small" onClick={() => setMenu(false)}>
              <button onClick={() => setDlg('time')}><Clock size={17} /> Ask for more time</button>
              {a.can_set_due && <button onClick={() => setDlg('due')}><Pencil size={17} /> Change the date</button>}
              {p.permissions.add_task && <button onClick={() => setDlg('task')}><ListChecks size={17} /> Give a task</button>}
            </div>
          )}
        </div>
      </div>

      <Received a={a} user={user} />
      {a.pending_request && <RequestBox p={p} req={a.pending_request} label={a.name} onChange={onChange} />}
      {a.all && (
        <div className="who-row">
          {a.owners.map((o) => (
            <span key={o.role} className={`who ${o.signed ? 'signed' : ''}`}>
              <OwnerBadge o={o} size={28} extra={o.signed ? ' · signed' : ' · waiting'} />
              {o.signed ? <Check size={17} className="ok" strokeWidth={3} /> : <Clock size={16} className="wait" />}
            </span>
          ))}
        </div>
      )}
      {a.consult && <p className="muted small">Consult: {a.consult}</p>}
      {p.clarification_pending && a.key === 'internal_review' && <p className="callout">Neo India asked a question. Update the brief, then submit again.</p>}
      {a.blockers.length > 0 && <p className="callout">Waiting for a task: {a.blockers.join(', ')}</p>}

      {needs && <div className="needs-box">
        <h4 className="box-title">To finish this step</h4>
        {a.docs.map((s) => <DocSlot key={s.key} pid={p.id} project={p} slot={s} stepKey={a.key} mine={s.editable} onChange={(r) => onChange(r.project)} />)}
        {a.fields.length > 0 && (
          <div className="fields">
            {a.fields.map((f) => (
              <Field key={f.key} label={f.label + (f.required ? '' : ' (optional)')} unit={f.unit}>
                <FieldInput f={f} value={data[f.key] ?? ''} onChange={(v) => setData({ ...data, [f.key]: v })} />
              </Field>
            ))}
          </div>
        )}
        {a.checks.length > 0 && (
          <div className="checks">
            {a.checks.map((c) => (
              <label key={c.key} className={`tick ${checks.includes(c.key) ? 'on' : ''}`}>
                <input type="checkbox" checked={checks.includes(c.key)} onChange={() => toggle(c.key)} />
                <span className="box"><Check size={14} strokeWidth={3.5} /></span>{c.label}
              </label>
            ))}
          </div>
        )}
      </div>}
      <div className="extra-docs">
        {a.other_docs.map((d) => <DocChip key={d.id} doc={d} />)}
        <button className="link" onClick={() => setMore(true)}><FilePlus2 size={15} /> {a.docs.length || a.other_docs.length ? 'Add another document' : 'Add a document (optional)'}</button>
      </div>

      {showNote
        ? <Field label="Message for the next person (optional)"><textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} autoFocus /></Field>
        : <button className="link" onClick={() => setShowNote(true)}>+ Add a message for the next person</button>}

      {approves.length <= 1 && <HandoverPicker nx={nextFor} value={nexts} onChange={setNexts} joint={a.all} />}
      {error && <p className="form-error" role="alert">{error}</p>}

      <div className="act-buttons">
        {a.mode === 'decision' ? (
          <>
            <button className="btn ok big" disabled={busy} onClick={() => (approves.length > 1 ? setDlg('choice') : run(approves[0].key))}>
              <Check size={22} strokeWidth={3} /> Approve
            </button>
            {(canSendBack || backs.length > 0) && <button className="btn bad big" disabled={busy} onClick={() => setDlg('back')}><CornerUpLeft size={20} /> Send back</button>}
            {stops.length > 0 && <button className="btn ghost big" disabled={busy} onClick={() => setDlg('why')}>{stops.some((o) => o.kind === 'hold') ? <Pause size={19} /> : <X size={19} />} {stops.length > 1 ? 'Hold / Reject' : 'Reject'}</button>}
          </>
        ) : (
          <>
            <button className="btn ok big" disabled={busy} onClick={() => run(null)}><Check size={22} strokeWidth={3} /> {a.button}</button>
            {canSendBack && <button className="btn bad big" disabled={busy} onClick={() => setDlg('back')}><CornerUpLeft size={20} /> Send back</button>}
          </>
        )}
      </div>

      {dlg === 'choice' && <ChoiceDialog a={a} options={approves} nexts={nexts} setNexts={setNexts} busy={busy} onClose={() => setDlg(null)} onPick={(k) => run(k, a.next[k])} />}
      {more && <DocDialog pid={p.id} project={p} target={{ stepKey: a.key }} label={a.name} onDone={(r) => onChange(r.project)} onClose={() => setMore(false)} />}
      {dlg === 'task' && <TaskDialog p={p} onClose={() => setDlg(null)} onDone={(pr) => { setDlg(null); onChange(pr) }} />}
      {dlg === 'back' && <SendBackDialog p={p} a={a} onClose={() => setDlg(null)} onDone={(pr) => { setDlg(null); onChange(pr) }} />}
      {dlg === 'why' && <WhyDialog p={p} a={a} options={stops} onClose={() => setDlg(null)} onDone={(pr) => { setDlg(null); onChange(pr) }} />}
      {dlg === 'time' && <AskTimeDialog p={p} kind="step" runId={a.run_id} due={a.due_at} to={a.request_to} label={a.name} onClose={() => setDlg(null)} onDone={(pr) => { setDlg(null); onChange(pr) }} />}
      {dlg === 'due' && <SetDueDialog p={p} a={a} onClose={() => setDlg(null)} onDone={(pr) => { setDlg(null); onChange(pr) }} />}
    </section>
  )
}

function wfPhase(p, a) {
  return p.steps.find((s) => s.key === a.key)?.phase
}

/** A step waiting for someone else: who, since when, and what I can do about it. */
export function WaitCard({ p, a, onChange }) {
  const { toast, phases } = useApp()
  const [dlg, setDlg] = useState(null)
  const phase = wfPhase(p, a)
  const nudge = async () => {
    try {
      const r = await api.post(`/api/projects/${p.id}/runs/${a.run_id}/nudge`)
      toast(r.message)
      onChange(r.project)
    } catch (e) {
      toast(e.message, 'err')
    }
  }
  const names = a.owners.flatMap((o) => o.people.map((n) => ({ n, short: o.short, signed: o.signed })))
  const canAssign = a.can_assign && a.assign_options.length > 1
  return (
    <section className="waitcard">
      <div className="now-top">
        <PhaseTile phase={phase} color={phases[phase]?.color} size={40} />
        <div className="grow">
          <span className="now-tag">{a.rework ? 'Sent back – waiting for' : 'Waiting for'}</span>
          <h3>{a.name}</h3>
        </div>
        <DuePill days={a.due_days} />
      </div>
      <div className="who-row">
        {a.owners.map((o) => (
          <span key={o.role} className={`who ${o.signed ? 'signed' : ''}`}>
            <OwnerBadge o={o} size={30} extra={a.all ? (o.signed ? ' · signed' : ' · waiting') : ''} />
            {a.all && (o.signed ? <Check size={17} className="ok" strokeWidth={3} /> : <Clock size={16} className="wait" />)}
          </span>
        ))}
      </div>
      {a.from && a.rework && (
        <p className="muted small"><Hand size={14} /> Sent back by {a.from.name}: “{a.from.note}”</p>
      )}
      {a.pending_request && <RequestBox p={p} req={a.pending_request} label={a.name} onChange={onChange} />}
      {(a.can_nudge || a.can_set_due || canAssign) && (
        <div className="wait-actions">
          {a.can_nudge && <button className="btn small" onClick={nudge}><BellRing size={15} /> Send reminder to {names.length === 1 ? shortName(names[0].n) : 'them'}</button>}
          {a.can_set_due && <button className="btn small" onClick={() => setDlg('due')}><Pencil size={15} /> Change the date</button>}
          {canAssign && <button className="btn small" onClick={() => setDlg('assign')}><UserRoundCog size={15} /> Change who</button>}
        </div>
      )}
      {dlg === 'due' && <SetDueDialog p={p} a={a} onClose={() => setDlg(null)} onDone={(pr) => { setDlg(null); onChange(pr) }} />}
      {dlg === 'assign' && <AssignDialog p={p} a={a} onClose={() => setDlg(null)} onDone={(pr) => { setDlg(null); onChange(pr) }} />}
    </section>
  )
}

export { Avatar }
