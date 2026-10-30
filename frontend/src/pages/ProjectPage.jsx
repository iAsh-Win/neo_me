import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  AlertTriangle, ArrowLeft, Ban, Check, CornerUpLeft, FastForward, FilePlus2, Info, MoreHorizontal, PartyPopper, Pause, Pencil,
  Play, Plus, Search, Send, X, Clock, ListChecks, Eye,
} from 'lucide-react'
import { api } from '../api'
import { useApp } from '../ctx'
import { DocDialog } from '../docs'
import { FastTrackDialog, RequestBox, TaskDialog, AskTimeDialog } from '../dialogs'
import { MyCard, WaitCard } from '../ActionCard'
import FlowMap from '../FlowMap'
import { HistoryItem, HistoryList } from '../History'
import { AvatarStack, DocChip, DuePill, ErrorNote, Field, HealthPill, Modal, PHASE_ICON, PhaseTile, Person, Pill, Spinner, StatusPill } from '../ui'
import { ago, fmtDate, money, plural } from '../format'

/* ---------- journey line (7 stages) ---------- */
function Journey({ p }) {
  const { def } = useApp()
  const idx = def.phases.findIndex((x) => x.key === p.phase)
  return (
    <ol className="journey" aria-label="Project stages">
      {def.phases.map((ph, i) => {
        const Icon = PHASE_ICON[ph.key]
        const state = p.status === 'completed' || i < idx ? 'done' : i === idx ? 'now' : 'later'
        const stopped = state === 'now' && ['rejected', 'cancelled'].includes(p.status)
        return (
          <li key={ph.key} className={`${state} ${stopped ? 'stopped' : ''}`} style={{ '--c': ph.color }}>
            <span className="j-node">{state === 'done' ? <Check size={17} strokeWidth={3} /> : <Icon size={17} strokeWidth={2.2} />}</span>
            <span className="j-label">{ph.name}</span>
          </li>
        )
      })}
    </ol>
  )
}

/* ---------- status strip: where it stands, with whom, latest note ---------- */
function Strip({ p, onNotes }) {
  const people = p.waiting.flatMap((w) => w.people)
  return (
    <div className="strip">
      <div className="strip-cell">
        <small>Status</small>
        <span className="strip-val"><HealthPill project={p} /></span>
        {p.status_note && <small className="note-line">{p.status_note}</small>}
      </div>
      <div className="strip-cell">
        <small>Progress</small>
        <span className="strip-val"><span className="bar"><i style={{ width: `${p.progress}%` }} /></span><b>{p.progress}%</b></span>
        <small>{p.steps_done} of {p.steps_total} steps</small>
      </div>
      <div className="strip-cell">
        <small>With</small>
        <span className="strip-val">{people.length ? <AvatarStack names={people} size={26} max={4} /> : '—'}</span>
        <small>{p.active.length > 1 ? `${p.active.length} steps side by side` : p.step_name}</small>
      </div>
      <div className="strip-cell">
        <small>Next date</small>
        <span className="strip-val">{p.due_days != null ? <DuePill days={p.due_days} /> : '—'}</span>
        {(p.tasks_open > 0 || p.requests_pending > 0) && (
          <small>{p.tasks_open > 0 && plural(p.tasks_open, 'open task')}{p.tasks_open > 0 && p.requests_pending > 0 && ' · '}{p.requests_pending > 0 && plural(p.requests_pending, 'time request')}</small>
        )}
      </div>
      {p.latest_note && (
        <button className="strip-cell note" onClick={onNotes}>
          <small>Latest note</small>
          <q>{p.latest_note.text}</q>
          <small>{p.latest_note.user.name} · {ago(p.latest_note.at)}</small>
        </button>
      )}
    </div>
  )
}

/* ---------- small generic dialog ---------- */
function Reason({ title, cta, tone, needNote = true, label, onClose, onSubmit }) {
  const [note, setNote] = useState('')
  const [error, setError] = useState('')
  const go = async () => {
    if (needNote && !note.trim()) return setError('Please write a short reason.')
    try { await onSubmit({ note }); onClose() } catch (e) { setError(e.message) }
  }
  return (
    <Modal title={title} onClose={onClose}
      footer={<><button className="btn" onClick={onClose}>Not now</button><button className={`btn ${tone || 'primary'}`} onClick={go}>{cta}</button></>}>
      <Field label={label || (needNote ? 'Why?' : 'Note (optional)')}><textarea rows={3} value={note} onChange={(e) => setNote(e.target.value)} autoFocus /></Field>
      {error && <p className="form-error" role="alert">{error}</p>}
    </Modal>
  )
}

/* ---------- tabs ---------- */
function TaskRow({ p, t, onChange }) {
  const { toast } = useApp()
  const [dlg, setDlg] = useState(null)
  const post = async (path, body = {}) => {
    try {
      onChange(await api.post(`/api/projects/${p.id}/tasks/${t.id}/${path}`, body))
      toast('Done')
    } catch (e) {
      toast(e.message, 'err')
    }
  }
  const closed = t.status !== 'open'
  const [adding, setAdding] = useState(false)
  return (
    <li className={`trow ${closed ? 'closed' : ''} ${t.overdue ? 'late' : ''}`}>
      <div className="trow-main">
        <b>{t.title}</b>
        {t.details && <small>{t.details}</small>}
        <div className="trow-meta">
          <Person name={t.assignee.name} role={t.assignee.short} size={24} />
          <small>from {t.creator.name}</small>
          {!closed && <DuePill days={t.due_days} />}
          {t.blocking && !closed && <Pill tone="amber">Blocks: {t.step_name}</Pill>}
          {t.step_name && !t.blocking && <Pill tone="gray">{t.step_name}</Pill>}
          {t.status === 'done' && <Pill tone="green" icon={Check}>Done {ago(t.completed_at)}</Pill>}
          {t.status === 'cancelled' && <Pill tone="gray" icon={Ban}>Cancelled</Pill>}
        </div>
        {t.done_note && <q>{t.done_note}</q>}
        {(t.docs.length > 0 || !closed) && (
          <div className="task-docs">
            {t.docs.map((d) => <DocChip key={d.id} doc={d} compact />)}
            {!closed && <button className="link" onClick={() => setAdding(true)}><FilePlus2 size={15} /> Add document</button>}
          </div>
        )}
        {t.pending_request && <RequestBox p={p} req={t.pending_request} label={t.title} onChange={onChange} />}
      </div>
      {!closed && (
        <div className="trow-actions">
          {t.can_complete && <button className="btn small ok" onClick={() => setDlg('done')}><Check size={15} /> Done</button>}
          {t.can_request && <button className="btn small" onClick={() => setDlg('time')}><Clock size={15} /> More time</button>}
          {t.can_cancel && <button className="btn small ghost" onClick={() => post('cancel')}>Cancel</button>}
        </div>
      )}
      {adding && <DocDialog pid={p.id} project={p} target={{ taskId: t.id }} label={t.title} onDone={(r) => onChange(r.project)} onClose={() => setAdding(false)} />}
      {dlg === 'done' && <Reason title="Finish task" cta="Done" needNote={false} label="Note (optional)" onClose={() => setDlg(null)} onSubmit={(b) => post('done', b)} />}
      {dlg === 'time' && <AskTimeDialog p={p} kind="task" taskId={t.id} due={t.due_at} to={t.request_to} label={t.title} onClose={() => setDlg(null)} onDone={(pr) => { setDlg(null); onChange(pr) }} />}
    </li>
  )
}

function TasksTab({ p, onChange }) {
  const [adding, setAdding] = useState(false)
  const open = p.tasks.filter((t) => t.status === 'open')
  const closed = p.tasks.filter((t) => t.status !== 'open')
  return (
    <div className="tabpane">
      <div className="row-between">
        <p className="muted">Small jobs given to people. They can block a step until done.</p>
        {p.permissions.add_task && <button className="btn primary" onClick={() => setAdding(true)}><Plus size={18} /> Give a task</button>}
      </div>
      {open.length === 0 && <p className="muted center">No open tasks.</p>}
      <ul className="tlist">{open.map((t) => <TaskRow key={t.id} p={p} t={t} onChange={onChange} />)}</ul>
      {closed.length > 0 && <><h4 className="sub">Finished</h4><ul className="tlist">{closed.map((t) => <TaskRow key={t.id} p={p} t={t} onChange={onChange} />)}</ul></>}
      {adding && <TaskDialog p={p} onClose={() => setAdding(false)} onDone={(pr) => { setAdding(false); onChange(pr) }} />}
    </div>
  )
}

function FilesTab({ p, onChange }) {
  const { user, toast } = useApp()
  const [q, setQ] = useState('')
  const [adding, setAdding] = useState(false)
  const ids = new Set(p.documents.map((d) => d.id))
  const match = (d) => !q || `${d.title} ${d.step_name} ${d.doc_label} ${d.user.name} ${d.task_title}`.toLowerCase().includes(q.toLowerCase())
  const lib = p.documents.filter((d) => (!d.source_id || !ids.has(d.source_id)) && match(d))
  const keyDocs = lib.filter((d) => d.important)
  const groups = []
  const general = lib.filter((d) => !d.step_key && !d.task_id)
  if (general.length) groups.push({ name: 'General', docs: general })
  for (const s of p.steps) {
    const docs = lib.filter((d) => d.step_key === s.key && !d.task_id)
    if (docs.length) groups.push({ name: s.name, docs })
  }
  for (const t of p.tasks) {
    const docs = lib.filter((d) => d.task_id === t.id)
    if (docs.length) groups.push({ name: `Task: ${t.title}`, docs })
  }
  const star = async (d) => {
    try { onChange(await api.post(`/api/documents/${d.original_id}/important`, { on: !d.pinned })) } catch (e) { toast(e.message, 'err') }
  }
  const remove = async (d) => {
    if (!confirm(`Remove “${d.title}”?`)) return
    try { onChange(await api.del(`/api/documents/${d.id}`)) } catch (e) { toast(e.message, 'err') }
  }
  const Row = ({ d }) => (
    <div className="fitem">
      <DocChip doc={d} onStar={p.permissions.mark_key || d.user.id === user.id ? () => star(d) : null}
        onRemove={user.role === 'admin' || d.user.id === user.id ? () => remove(d) : null} />
      <small>{d.doc_label || (d.step_name ? 'Other' : '')}{d.doc_label || d.step_name ? ' · ' : ''}{d.user.name} · {fmtDate(d.at)}{d.used_in.length > 0 && ` · also used in ${d.used_in.join(', ')}`}</small>
    </div>
  )
  return (
    <div className="tabpane">
      <div className="files-bar">
        <div className="searchbox"><Search size={16} /><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search documents" aria-label="Search documents" /></div>
        <button className="btn primary" onClick={() => setAdding(true)}><FilePlus2 size={17} /> Add document</button>
      </div>
      {keyDocs.length > 0 && (
        <section className="fgroup keys">
          <h4>Key documents</h4>
          <div className="flist">{keyDocs.map((d) => <Row key={d.id} d={d} />)}</div>
        </section>
      )}
      {groups.map((g) => (
        <section key={g.name} className="fgroup">
          <h4>{g.name}</h4>
          <div className="flist">{g.docs.map((d) => <Row key={d.id} d={d} />)}</div>
        </section>
      ))}
      {lib.length === 0 && <p className="muted center">{p.documents.length ? 'No document matches.' : 'No documents yet. Add them on each step, or here.'}</p>}
      {p.scope === 'focus' && <p className="muted small center"><Eye size={14} /> Shows the documents of your own steps and tasks.</p>}
      {adding && <DocDialog pid={p.id} project={p} label="" onDone={(r) => onChange(r.project)} onClose={() => setAdding(false)} />}
    </div>
  )
}

/* ---------- the short version, for someone who just wants to know where it stands ---------- */
function SummaryTab({ p, goto }) {
  const b = p.brief
  const keyEvents = p.events.filter((e) => e.key).slice(-4).reverse()
  const stateText = (s) => {
    if (s.state === 'done') return `Finished ${shortDay(s.finished)} · ${plural(s.days ?? 0, 'day')}${s.last ? ` · last step by ${s.last.name}` : ''}`
    if (s.state === 'now') return s.now.length ? s.now.map((n) => `${n.name} – ${n.people.join(', ') || '—'}`).join(' · ') : 'In progress'
    return 'Not started'
  }
  return (
    <div className="tabpane summary">
      {b.attention.length > 0 ? (
        <section className="attn">
          <h4><AlertTriangle size={16} /> Needs attention</h4>
          <ul>{b.attention.map((x, i) => <li key={i} className={x.tone}>{x.text}</li>)}</ul>
        </section>
      ) : (
        p.status === 'active' && <p className="calm"><Check size={16} strokeWidth={3} /> Nothing needs attention.</p>
      )}
      <section>
        <h4 className="sub">The project, stage by stage</h4>
        <ol className="stages">
          {b.stages.map((s, i) => (
            <li key={s.key} className={`stage ${s.state}`} style={{ '--c': s.color }}>
              <PhaseTile phase={s.key} color={s.color} size={36} />
              <div className="st-main">
                <b>{i + 1}. {s.name}</b>
                <small>{stateText(s)}</small>
              </div>
              <div className="st-side">
                {s.sendbacks > 0 && <Pill tone="amber" icon={CornerUpLeft}>Sent back {s.sendbacks}×</Pill>}
                <span className="st-count">{s.state === 'done' ? <Check size={15} strokeWidth={3} /> : `${s.steps_done}/${s.steps_total}`}</span>
              </div>
            </li>
          ))}
        </ol>
      </section>
      <div className="nums">
        <div><b>{b.counts.days}</b><small>days running</small></div>
        <div><b>{b.counts.sendbacks}</b><small>send-backs</small></div>
        <div><b>{b.counts.extensions}</b><small>time extensions</small></div>
        <div><b>{b.counts.holds}</b><small>holds</small></div>
      </div>
      {b.key_docs.length > 0 && (
        <section>
          <div className="row-between"><h4 className="sub">Key documents</h4><button className="link" onClick={() => goto('files')}>All documents</button></div>
          <div className="slot-items">{b.key_docs.map((d) => <DocChip key={d.id} doc={d} />)}</div>
        </section>
      )}
      {keyEvents.length > 0 && (
        <section>
          <div className="row-between"><h4 className="sub">Latest key moments</h4><button className="link" onClick={() => goto('history')}>Full history</button></div>
          <ul className="h-list">{keyEvents.map((e) => <HistoryItem key={e.id} e={e} />)}</ul>
        </section>
      )}
    </div>
  )
}

const shortDay = (iso) => fmtDate(iso)

function HistoryTab({ p, onChange }) {
  const { toast } = useApp()
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const send = async () => {
    if (!text.trim()) return
    setBusy(true)
    try {
      onChange(await api.post(`/api/projects/${p.id}/comments`, { note: text }))
      setText('')
    } catch (e) {
      toast(e.message, 'err')
    }
    setBusy(false)
  }
  return (
    <div className="tabpane">
      <div className="composer">
        <textarea rows={2} value={text} onChange={(e) => setText(e.target.value)} placeholder="Write a note for the team…" aria-label="Write a note" />
        <button className="btn primary" onClick={send} disabled={busy || !text.trim()}><Send size={16} /> Post</button>
      </div>
      <HistoryList events={p.events} start={p.scope === 'full' ? 'key' : 'all'} />
    </div>
  )
}

/* ---------- dialogs ---------- */
function DetailsDialog({ p, onClose, onEdit }) {
  const rows = [
    ['Type', p.ptype_label], ['Market', p.market || '—'], ['Initiator', p.initiator.name],
    ['Est. yearly sales', money(p.est_value)], ['Target date', p.target_date ? fmtDate(p.target_date) : '—'],
    ...(p.ptype === 'development' ? [['CDMO / Manufacturer', p.manufacturer || 'Not confirmed yet']] : []),
    ['Added', fmtDate(p.created_at)],
  ]
  return (
    <Modal title="Project details" onClose={onClose}
      footer={p.permissions.edit ? <button className="btn" onClick={onEdit}><Pencil size={16} /> Edit</button> : null}>
      <dl className="facts">{rows.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
      {p.description && <p className="desc">{p.description}</p>}
    </Modal>
  )
}

function EditDetails({ p, onClose, onChange }) {
  const { user, toast } = useApp()
  const [f, setF] = useState({
    title: p.title, market: p.market, est_value: p.est_value ?? '', target_date: p.target_date || '',
    description: p.description, manufacturer: p.manufacturer, initiator_id: p.initiator.id,
  })
  const [inis, setInis] = useState([])
  const [error, setError] = useState('')
  useEffect(() => {
    if (user.role === 'admin') api.get('/api/users').then((u) => setInis(u.filter((x) => x.role === 'initiator' && x.active)))
  }, [user.role])
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const save = async () => {
    try {
      const body = { ...f, est_value: f.est_value === '' ? null : Number(f.est_value) }
      if (user.role !== 'admin') delete body.initiator_id
      onChange(await api.patch(`/api/projects/${p.id}`, body))
      toast('Saved')
      onClose()
    } catch (e) {
      setError(e.message)
    }
  }
  return (
    <Modal title="Edit details" onClose={onClose}
      footer={<><button className="btn" onClick={onClose}>Cancel</button><button className="btn primary" onClick={save}>Save</button></>}>
      <Field label="Project name"><input value={f.title} onChange={set('title')} /></Field>
      <div className="two">
        <Field label="Market"><input value={f.market} onChange={set('market')} /></Field>
        <Field label="Est. yearly sales (A$)"><input type="number" min="0" value={f.est_value} onChange={set('est_value')} /></Field>
      </div>
      <div className="two">
        <Field label="Target date"><input type="date" value={f.target_date} onChange={set('target_date')} /></Field>
        <Field label="CDMO / Manufacturer"><input value={f.manufacturer} onChange={set('manufacturer')} /></Field>
      </div>
      {user.role === 'admin' && (
        <Field label="Project Initiator">
          <select value={f.initiator_id} onChange={set('initiator_id')}>{inis.map((i) => <option key={i.id} value={i.id}>{i.name}</option>)}</select>
        </Field>
      )}
      <Field label="Description"><textarea rows={3} value={f.description} onChange={set('description')} /></Field>
      {error && <p className="form-error" role="alert">{error}</p>}
    </Modal>
  )
}

function MoveDialog({ p, onClose, onSubmit }) {
  const [step, setStep] = useState(p.step_options[0].key)
  const [note, setNote] = useState('')
  const [error, setError] = useState('')
  const go = async () => {
    if (!note.trim()) return setError('Please write a short reason.')
    try { await onSubmit({ note, step_key: step }); onClose() } catch (e) { setError(e.message) }
  }
  return (
    <Modal title="Correct the step" onClose={onClose}
      footer={<><button className="btn" onClick={onClose}>Not now</button><button className="btn primary" onClick={go}>Move</button></>}>
      <Field label="Move the project to"><select value={step} onChange={(e) => setStep(e.target.value)}>{p.step_options.map((s) => <option key={s.key} value={s.key}>{s.name}</option>)}</select></Field>
      <Field label="Why?"><textarea rows={3} value={note} onChange={(e) => setNote(e.target.value)} /></Field>
      {error && <p className="form-error" role="alert">{error}</p>}
    </Modal>
  )
}

/* ---------- end states ---------- */
function EndCard({ p }) {
  if (p.status === 'completed') return <div className="nowcard end ok"><PartyPopper size={30} /><div><h2>Project completed</h2><p>Dispatched and closed.</p></div></div>
  if (p.status === 'rejected' || p.status === 'cancelled') return <div className="nowcard end bad"><Ban size={30} /><div><h2>Project {p.status}</h2><p>{p.status_note || 'No reason recorded.'}</p></div></div>
  return <div className="nowcard end warn"><Pause size={30} /><div><h2>On hold</h2><p>{p.status_note}</p><small>{p.permissions.resume ? 'Use “Restart” in the ⋯ menu when ready.' : 'A Director will restart it.'}</small></div></div>
}

/* ---------- page ---------- */
export default function ProjectPage() {
  const { id } = useParams()
  const { toast } = useApp()
  const [p, setP] = useState(null)
  const [err, setErr] = useState('')
  const [dlg, setDlg] = useState(null)
  const [menu, setMenu] = useState(false)
  const [tabSel, setTab] = useState(null)
  const menuRef = useRef()
  const load = () => api.get(`/api/projects/${id}`).then(setP).catch((e) => setErr(e.message))
  useEffect(() => { setP(null); setErr(''); load() }, [id]) // eslint-disable-line
  useEffect(() => {
    const close = (e) => menuRef.current && !menuRef.current.contains(e.target) && setMenu(false)
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])

  if (err) return <ErrorNote error={err} retry={() => { setErr(''); load() }} />
  if (!p) return <Spinner />
  const perm = p.permissions
  const post = (path) => async (body) => {
    setP(await api.post(`/api/projects/${p.id}/${path}`, body))
    toast('Done')
  }
  const mine = p.actions.filter((a) => a.can_act)
  const others = p.actions.filter((a) => !a.can_act)
  const openTasks = p.tasks.filter((t) => t.status === 'open').length
  const full = p.scope === 'full'
  const tab = tabSel ?? (full ? 'summary' : 'flow')
  const tabs = [...(full ? [['summary', 'Summary']] : []), ['flow', full ? 'Flow' : 'My part'], ['tasks', 'Tasks', openTasks],
    ['files', 'Files', p.documents.filter((d) => !d.source_id).length], ['history', 'History', p.events.length]]

  return (
    <div className="page project">
      <Link to="/projects" className="back"><ArrowLeft size={17} /> Projects</Link>
      <header className="p-head">
        <div>
          <div className="p-badges">
            {p.code && <span className="code">{p.code}</span>}
            <Pill tone="gray">{p.ptype_label}</Pill>
            {p.fast_track && <Pill tone="blue" icon={FastForward}>Fast track</Pill>}
            <StatusPill project={p} />
          </div>
          <h1>{p.title}</h1>
        </div>
        <div className="head-actions">
          <button className="btn" onClick={() => setDlg('details')}><Info size={18} /> <span>Details</span></button>
          <div className="menu" ref={menuRef}>
            <button className="btn icon" onClick={() => setMenu(!menu)} aria-label="More actions" aria-expanded={menu}><MoreHorizontal size={20} /></button>
            {menu && (
              <div className="popover small" onClick={() => setMenu(false)}>
                {perm.add_task && <button onClick={() => setDlg('task')}><ListChecks size={17} /> Give a task</button>}
                {perm.fast_track && <button onClick={() => setDlg('fast')}><FastForward size={17} /> Fast track…</button>}
                {perm.hold && <button onClick={() => setDlg('hold')}><Pause size={17} /> Put on hold</button>}
                {perm.resume && <button onClick={() => setDlg('resume')}><Play size={17} /> Restart</button>}
                {perm.move && <button onClick={() => setDlg('move')}><CornerUpLeft size={17} /> Correct the step</button>}
                {perm.cancel && <button className="danger" onClick={() => setDlg('cancel')}><X size={17} /> Cancel project</button>}
              </div>
            )}
          </div>
        </div>
      </header>

      <Journey p={p} />
      <Strip p={p} onNotes={() => setTab('history')} />

      {p.status !== 'active' && <EndCard p={p} />}
      {p.status === 'active' && (
        <>
          {mine.map((a) => <MyCard key={a.run_id} p={p} a={a} onChange={setP} />)}
          {others.length > 0 && (
            <div className="others">
              {mine.length > 0 && <h4 className="sub">With others</h4>}
              {others.map((a) => <WaitCard key={a.run_id} p={p} a={a} onChange={setP} />)}
            </div>
          )}
        </>
      )}

      {!full && p.status === 'active' && <p className="scope-note"><Eye size={14} /> You see the parts of this project that you work on. The owner and the Directors see everything.</p>}
      <div className="tabs wide" role="tablist">
        {tabs.map(([k, label, n]) => (
          <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>
            {label}{n !== undefined && <span>{n}</span>}
          </button>
        ))}
      </div>
      {tab === 'summary' && full && <SummaryTab p={p} goto={setTab} />}
      {tab === 'flow' && <FlowMap steps={p.steps} groups={p.groups} mode="project" openPhase={p.phase} />}
      {tab === 'tasks' && <TasksTab p={p} onChange={setP} />}
      {tab === 'files' && <FilesTab p={p} onChange={setP} />}
      {tab === 'history' && <HistoryTab p={p} onChange={setP} />}

      {dlg === 'details' && <DetailsDialog p={p} onClose={() => setDlg(null)} onEdit={() => setDlg('edit')} />}
      {dlg === 'edit' && <EditDetails p={p} onClose={() => setDlg(null)} onChange={setP} />}
      {dlg === 'task' && <TaskDialog p={p} onClose={() => setDlg(null)} onDone={(pr) => { setDlg(null); setP(pr); setTab('tasks') }} />}
      {dlg === 'fast' && <FastTrackDialog p={p} onClose={() => setDlg(null)} onDone={(pr) => { setDlg(null); setP(pr) }} />}
      {dlg === 'hold' && <Reason title="Put on hold" cta="Put on hold" tone="amber" onClose={() => setDlg(null)} onSubmit={post('hold')} />}
      {dlg === 'resume' && <Reason title="Restart project" cta="Restart" needNote={false} onClose={() => setDlg(null)} onSubmit={post('resume')} />}
      {dlg === 'cancel' && <Reason title="Cancel project" cta="Cancel project" tone="danger" onClose={() => setDlg(null)} onSubmit={post('cancel')} />}
      {dlg === 'move' && <MoveDialog p={p} onClose={() => setDlg(null)} onSubmit={post('move')} />}
    </div>
  )
}
