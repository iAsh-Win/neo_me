import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  ArrowLeft, BellRing, Check, CheckCircle2, CornerUpLeft, Download, File as FileIcon, FileSpreadsheet, FileText,
  Info, MoreHorizontal, Paperclip, Pause, Pencil, Play, Send, Trash2, X, Ban, PartyPopper, Clock, Hand,
} from 'lucide-react'
import { api, fileUrl } from '../api'
import { useApp } from '../ctx'
import { Avatar, AvatarStack, DuePill, ErrorNote, Field, Modal, PHASE_ICON, PhaseTile, Pill, RoleChip, Spinner, StatusPill } from '../ui'
import { ago, fileSize, fmtDate, money, plural } from '../format'
import FlowMap from '../FlowMap'

/* ---------- journey rail ---------- */
function Journey({ p }) {
  const { def } = useApp()
  const idx = def.phases.findIndex((x) => x.key === p.phase)
  return (
    <ol className="journey" aria-label="Project journey">
      {def.phases.map((ph, i) => {
        const Icon = PHASE_ICON[ph.key]
        const state = p.status === 'completed' || i < idx ? 'done' : i === idx ? 'now' : 'later'
        const stopped = state === 'now' && ['rejected', 'cancelled'].includes(p.status)
        return (
          <li key={ph.key} className={`${state} ${stopped ? 'stopped' : ''}`} style={{ '--c': ph.color }}>
            <span className="j-node">
              {state === 'done' ? <Check size={18} strokeWidth={3} /> : <Icon size={18} strokeWidth={2.2} />}
            </span>
            <span className="j-label">{ph.name}</span>
          </li>
        )
      })}
    </ol>
  )
}

/* ---------- dialogs used by the big buttons ---------- */
function ChoiceDialog({ title, options, onPick, onClose }) {
  return (
    <Modal title={title} onClose={onClose}>
      <div className="big-choices">
        {options.map((o) => (
          <button key={o.key} className="big-choice" onClick={() => onPick(o.key)}>
            <CheckCircle2 size={24} /> {o.short || o.label}
          </button>
        ))}
      </div>
    </Modal>
  )
}

function WhyDialog({ options, onPick, onClose, error, busy }) {
  const [note, setNote] = useState('')
  const hasBack = options.some((o) => o.kind === 'back')
  return (
    <Modal title={hasBack ? 'Send back' : options.length > 1 ? 'Hold or reject' : 'Reject'} onClose={onClose}
      footer={
        <>
          <button className="btn" onClick={onClose}>Cancel</button>
          {options.map((o) => (
            <button key={o.key} disabled={busy} className={`btn ${o.kind === 'hold' ? 'amber' : 'danger'}`} onClick={() => onPick(o.key, note)}>
              {o.kind === 'back' ? <CornerUpLeft size={17} /> : o.kind === 'hold' ? <Pause size={17} /> : <X size={17} />}
              {o.kind === 'back' ? 'Send back' : o.kind === 'hold' ? 'Hold for now' : 'Reject'}
            </button>
          ))}
        </>
      }>
      {hasBack && <p className="muted">It goes back to <b>{options.find((o) => o.kind === 'back').to_name}</b>.</p>}
      <Field label="Why?">
        <textarea rows={3} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Write one or two lines" autoFocus />
      </Field>
      {error && <p className="form-error" role="alert">{error}</p>}
    </Modal>
  )
}

/* ---------- the big "what's next" card ---------- */
function Who({ a }) {
  return (
    <div className="who-row">
      {a.owners.map((o) => {
        const signed = a.all && a.signed.includes(o.role)
        return (
          <span key={o.role} className={`who ${signed ? 'signed' : ''}`}>
            {o.people.length > 0 && <AvatarStack names={o.people} size={34} max={2} />}
            <span className="who-text">
              <b>{o.people.length > 2 ? `${o.people.length} people` : o.people.join(', ') || o.label}</b>
              <small>{o.short}{a.all ? (signed ? ' · signed' : ' · waiting') : ''}</small>
            </span>
            {a.all && (signed ? <Check size={18} className="ok" strokeWidth={3} /> : <Clock size={17} className="wait" />)}
          </span>
        )
      })}
      {a.coordinator && <span className="who"><span className="who-text"><small>Coordinator</small><b>{a.coordinator}</b></span></span>}
    </div>
  )
}

function NowCard({ p, onChange }) {
  const { toast, phases } = useApp()
  const a = p.action
  const [note, setNote] = useState('')
  const [text, setText] = useState('')
  const [showNote, setShowNote] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [dlg, setDlg] = useState(null)
  const fileRef = useRef()
  useEffect(() => { setNote(''); setText(''); setError(''); setShowNote(false); setDlg(null) }, [p.current_step, p.status])

  const run = async (option, why) => {
    setBusy(true)
    setError('')
    try {
      const r = await api.post(`/api/projects/${p.id}/act`, { option, note: why ?? note, text: text || null })
      setDlg(null)
      toast(r.message)
      onChange(r.project)
    } catch (e) {
      setError(e.message)
    }
    setBusy(false)
  }
  const upload = async (file) => {
    if (!file) return
    const form = new FormData()
    form.append('file', file)
    form.append('step_key', a.key)
    try {
      onChange(await api.upload(`/api/projects/${p.id}/documents`, form))
      toast('File attached')
    } catch (e) {
      setError(e.message)
    }
  }
  const nudge = async () => {
    try {
      const r = await api.post(`/api/projects/${p.id}/nudge`)
      toast(r.message)
      onChange(r.project)
    } catch (e) {
      toast(e.message, 'err')
    }
  }

  if (p.status === 'completed')
    return <div className="nowcard end ok"><PartyPopper size={30} /><div><h2>Project completed</h2><p>Dispatched and closed.</p></div></div>
  if (p.status === 'rejected' || p.status === 'cancelled')
    return <div className="nowcard end bad"><Ban size={30} /><div><h2>Project {p.status}</h2><p>{p.status_note || 'No reason recorded.'}</p></div></div>
  if (p.status === 'on_hold')
    return <div className="nowcard end warn"><Pause size={30} /><div><h2>On hold</h2><p>{p.status_note}</p><small>at: {a.name}</small></div></div>

  const approves = a.options.filter((o) => o.kind === 'approve')
  const negatives = a.options.filter((o) => o.kind !== 'approve')
  const negLabel = negatives.some((o) => o.kind === 'back') ? 'Send back' : negatives.length > 1 ? 'Hold / Reject' : 'Reject'
  const mine = a.can_act

  return (
    <section className={`nowcard ${mine ? 'mine' : ''}`} aria-live="polite">
      <div className="now-top">
        <PhaseTile phase={p.phase} color={phases[p.phase]?.color} size={46} />
        <div className="grow">
          <span className="now-tag">{mine ? 'Your turn' : 'Waiting for'}</span>
          <h2>{a.name}</h2>
        </div>
        <DuePill project={p} />
      </div>

      <Who a={a} />

      {a.consult && <p className="muted small">Consult: {a.consult}</p>}
      {p.clarification_pending && <p className="callout">Neo India asked for clarification. Update, then submit again.</p>}

      {mine ? (
        <div className="act">
          {a.needs_text && <Field label={a.needs_text}><input value={text} onChange={(e) => setText(e.target.value)} /></Field>}
          {a.needs_file && (
            <div className={`need-file ${a.has_file ? 'ok' : ''}`}>
              <Paperclip size={19} />
              <span>{a.has_file ? <><b>{a.needs_file}</b> attached</> : <>Attach: <b>{a.needs_file}</b></>}</span>
              <button className="btn small" onClick={() => fileRef.current.click()}>{a.has_file ? 'Add another' : 'Choose file'}</button>
              <input ref={fileRef} type="file" hidden onChange={(e) => { upload(e.target.files[0]); e.target.value = '' }} />
            </div>
          )}
          {a.needs_note && <Field label={a.needs_note}><textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} /></Field>}
          {!a.needs_note && (showNote
            ? <Field label="Note"><textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} autoFocus /></Field>
            : <button className="link" onClick={() => setShowNote(true)}>+ Add a note</button>)}
          {error && !dlg && <p className="form-error" role="alert">{error}</p>}
          <div className="act-buttons">
            {a.mode === 'decision' ? (
              <>
                <button className="btn ok big" disabled={busy} onClick={() => (approves.length === 1 ? run(approves[0].key) : setDlg('choice'))}>
                  <Check size={22} strokeWidth={3} /> Approve
                </button>
                {negatives.length > 0 && (
                  <button className="btn bad big" disabled={busy} onClick={() => setDlg('why')}>
                    {negatives.some((o) => o.kind === 'back') ? <CornerUpLeft size={20} /> : <X size={22} strokeWidth={3} />} {negLabel}
                  </button>
                )}
              </>
            ) : (
              <button className="btn ok big" disabled={busy} onClick={() => run(null)}><Check size={22} strokeWidth={3} /> {a.button}</button>
            )}
          </div>
        </div>
      ) : (
        <div className="act">
          <div className="waiting-line"><Hand size={18} /> Not your turn. You will be told when it moves.</div>
          {p.permissions.nudge && <button className="btn small" onClick={nudge}><BellRing size={16} /> Send reminder</button>}
        </div>
      )}
      {dlg === 'choice' && <ChoiceDialog title="Is the information complete?" options={approves} onClose={() => setDlg(null)} onPick={(k) => run(k)} />}
      {dlg === 'why' && <WhyDialog options={negatives} busy={busy} error={error} onClose={() => setDlg(null)} onPick={(k, why) => run(k, why)} />}
    </section>
  )
}

/* ---------- tabs ---------- */
const fileIcon = (n) => (/\.xlsx?$/i.test(n) ? <FileSpreadsheet size={26} /> : /\.(pdf|docx?)$/i.test(n) ? <FileText size={26} /> : <FileIcon size={26} />)

function FilesTab({ p, onChange }) {
  const { toast, user } = useApp()
  const ref = useRef()
  const [busy, setBusy] = useState(false)
  const up = async (f) => {
    if (!f) return
    setBusy(true)
    const form = new FormData()
    form.append('file', f)
    form.append('step_key', p.current_step)
    try {
      onChange(await api.upload(`/api/projects/${p.id}/documents`, form))
      toast('File added')
    } catch (e) {
      toast(e.message, 'err')
    }
    setBusy(false)
  }
  const del = async (d) => {
    if (!confirm(`Remove “${d.filename}”?`)) return
    try { onChange(await api.del(`/api/documents/${d.id}`)) } catch (e) { toast(e.message, 'err') }
  }
  return (
    <div className="tabpane">
      <div className="files">
        {p.documents.map((d) => (
          <div key={d.id} className="file">
            <a href={fileUrl(`/api/documents/${d.id}`)} className="file-main">
              <span className="file-ico">{fileIcon(d.filename)}</span>
              <b>{d.filename}</b>
              <small>{d.step_name || 'General'}</small>
              <small>{d.user.name} · {fmtDate(d.at)} · {fileSize(d.size)}</small>
            </a>
            {(user.role === 'admin' || d.user.id === user.id) && (
              <button className="icon-btn del" onClick={() => del(d)} aria-label={`Remove ${d.filename}`}><Trash2 size={17} /></button>
            )}
          </div>
        ))}
        <button className="file add" disabled={busy} onClick={() => ref.current.click()}>
          <Paperclip size={26} strokeWidth={1.6} /><b>Add file</b>
        </button>
        <input ref={ref} type="file" hidden onChange={(e) => { up(e.target.files[0]); e.target.value = '' }} />
      </div>
    </div>
  )
}

const SYSTEM = { hold: 'put the project on hold', resume: 'restarted the project', cancel: 'cancelled the project', moved: 'moved the project', nudge: 'sent a reminder' }

function NotesTab({ p, onChange }) {
  const { toast } = useApp()
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [hist, setHist] = useState(false)
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
  const notes = p.events.filter((e) => e.kind === 'comment').reverse()
  const history = [...p.events].reverse()
  return (
    <div className="tabpane">
      <div className="composer">
        <textarea rows={2} value={text} onChange={(e) => setText(e.target.value)} placeholder="Write a note…" aria-label="Write a note" />
        <button className="btn primary" onClick={send} disabled={busy || !text.trim()}><Send size={16} /> Post</button>
      </div>
      <ul className="bubbles">
        {notes.map((e) => (
          <li key={e.id}>
            <Avatar name={e.user?.name || '?'} size={34} />
            <div><p><b>{e.user?.name}</b> <small>{e.user?.short} · {ago(e.at)}</small></p><div className="bubble">{e.note}</div></div>
          </li>
        ))}
      </ul>
      {notes.length === 0 && <p className="muted center">No notes yet.</p>}
      <button className="link" onClick={() => setHist(!hist)}>{hist ? 'Hide history' : 'Show full history'}</button>
      {hist && (
        <ul className="history">
          {history.filter((e) => e.kind !== 'comment').map((e) => (
            <li key={e.id}>
              <small>{ago(e.at)}</small>
              <span><b>{e.user?.name}</b> {e.kind === 'system' ? SYSTEM[e.action] : <>{e.option_label ? e.result.toLowerCase() : e.result.toLowerCase()} · {e.step_name}</>}{e.note && <q>{e.note}</q>}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

/* ---------- dialogs ---------- */
function DetailsDialog({ p, onClose, onEdit }) {
  const rows = [
    ['Type', p.ptype_label], ['Market', p.market || '—'], ['Initiator', p.initiator.name],
    ['Est. yearly sales', money(p.est_value)], ['Target date', p.target_date ? fmtDate(p.target_date) : '—'],
    ...(p.ptype === 'development' ? [['CDMO / Manufacturer', p.manufacturer || 'Not confirmed yet']] : []),
    ['Added', fmtDate(p.created_at)], ['Step due in', `${plural(p.action.sla, 'day')} each`],
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

function Reason({ title, cta, tone, needNote = true, stepOptions, onClose, onSubmit }) {
  const [note, setNote] = useState('')
  const [step, setStep] = useState(stepOptions?.[0]?.key || '')
  const [error, setError] = useState('')
  const go = async () => {
    if (needNote && !note.trim()) return setError('Please write a short reason.')
    try { await onSubmit({ note, step_key: step }); onClose() } catch (e) { setError(e.message) }
  }
  return (
    <Modal title={title} onClose={onClose}
      footer={<><button className="btn" onClick={onClose}>Not now</button><button className={`btn ${tone || 'primary'}`} onClick={go}>{cta}</button></>}>
      {stepOptions && (
        <Field label="Move the project to">
          <select value={step} onChange={(e) => setStep(e.target.value)}>{stepOptions.map((s) => <option key={s.key} value={s.key}>{s.name}</option>)}</select>
        </Field>
      )}
      <Field label={needNote ? 'Why?' : 'Note (optional)'}><textarea rows={3} value={note} onChange={(e) => setNote(e.target.value)} /></Field>
      {error && <p className="form-error" role="alert">{error}</p>}
    </Modal>
  )
}

/* ---------- page ---------- */
export default function ProjectPage() {
  const { id } = useParams()
  const { toast } = useApp()
  const [p, setP] = useState(null)
  const [err, setErr] = useState('')
  const [dlg, setDlg] = useState(null)
  const [menu, setMenu] = useState(false)
  const [tab, setTab] = useState('flow')
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
    const r = await api.post(`/api/projects/${p.id}/${path}`, body)
    setP(r)
    toast('Done')
  }
  const notesCount = p.events.filter((e) => e.kind === 'comment').length

  return (
    <div className="page project">
      <Link to="/projects" className="back"><ArrowLeft size={17} /> Projects</Link>
      <header className="p-head">
        <div>
          <div className="p-badges">
            {p.code && <span className="code">{p.code}</span>}
            <Pill tone="gray">{p.ptype_label}</Pill>
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
                <a className="menu-item" href={fileUrl(`/api/projects/${p.id}/brief.xlsx`)}><Download size={17} /> Download Excel</a>
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
      <NowCard p={p} onChange={setP} />

      <div className="tabs wide" role="tablist">
        <button role="tab" aria-selected={tab === 'flow'} className={tab === 'flow' ? 'on' : ''} onClick={() => setTab('flow')}>Flow</button>
        <button role="tab" aria-selected={tab === 'files'} className={tab === 'files' ? 'on' : ''} onClick={() => setTab('files')}>Files<span>{p.documents.length}</span></button>
        <button role="tab" aria-selected={tab === 'notes'} className={tab === 'notes' ? 'on' : ''} onClick={() => setTab('notes')}>Notes<span>{notesCount}</span></button>
      </div>
      {tab === 'flow' && <FlowMap steps={p.steps} mode="project" openPhase={p.phase} />}
      {tab === 'files' && <FilesTab p={p} onChange={setP} />}
      {tab === 'notes' && <NotesTab p={p} onChange={setP} />}

      {dlg === 'details' && <DetailsDialog p={p} onClose={() => setDlg(null)} onEdit={() => setDlg('edit')} />}
      {dlg === 'edit' && <EditDetails p={p} onClose={() => setDlg(null)} onChange={setP} />}
      {dlg === 'hold' && <Reason title="Put on hold" cta="Put on hold" tone="amber" onClose={() => setDlg(null)} onSubmit={post('hold')} />}
      {dlg === 'resume' && <Reason title="Restart project" cta="Restart" needNote={false} onClose={() => setDlg(null)} onSubmit={post('resume')} />}
      {dlg === 'cancel' && <Reason title="Cancel project" cta="Cancel project" tone="danger" onClose={() => setDlg(null)} onSubmit={post('cancel')} />}
      {dlg === 'move' && <Reason title="Correct the step" cta="Move" stepOptions={p.step_options} onClose={() => setDlg(null)} onSubmit={post('move')} />}
    </div>
  )
}
