import { useEffect, useState } from 'react'
import { CornerUpLeft, FastForward, FilePlus2, Pause, X, Check } from 'lucide-react'
import { api } from './api'
import { useApp } from './ctx'
import { DocDialog, DocSlot, sendDoc } from './docs'
import { HandoverPicker, nextsBody } from './handover'
import { Avatar, DocChip, Field, Modal, Person } from './ui'
import { fmtDate, shortName } from './format'

const tomorrowISO = (extra = 1) => new Date(Date.now() + extra * 86400000).toISOString().slice(0, 10)

/* ---------- send back: choose WHO gets it, say why, attach what helps ---------- */
export function SendBackDialog({ p, a, onClose, onDone }) {
  const { toast } = useApp()
  const chart = a.options.find((o) => o.kind === 'back')
  const targets = a.targets.map((t) => ({ ...t, chart: chart && t.key === chart.to }))
  const [target, setTarget] = useState((targets.find((t) => t.chart) || targets[0])?.key || '')
  const [note, setNote] = useState('')
  const [docs, setDocs] = useState([])
  const [proj, setProj] = useState(p)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [who, setWho] = useState('')
  const [due, setDue] = useState('')
  const cur = targets.find((t) => t.key === target)
  const isChart = cur?.chart
  useEffect(() => { setWho(''); setDue(cur?.default_due || '') }, [target]) // eslint-disable-line
  const go = async () => {
    setBusy(true)
    setError('')
    try {
      const url = `/api/projects/${p.id}/runs/${a.run_id}`
      const pick = { assignee_id: who ? Number(who) : null, due: due || null }
      const r = isChart
        ? await api.post(`${url}/act`, { option: chart.key, note, nexts: { [chart.to]: pick } })
        : await api.post(`${url}/sendback`, { target, note, doc_ids: docs, ...pick })
      toast(r.message)
      onDone(r.project)
    } catch (e) {
      setError(e.message)
      setBusy(false)
    }
  }
  const slot = { key: '', label: 'Documents that help (optional)', required: false, items: proj.documents.filter((d) => docs.includes(d.id)) }
  return (
    <Modal title="Send back" onClose={onClose} size="wide"
      footer={
        <>
          <button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn danger" disabled={busy || !target} onClick={go}><CornerUpLeft size={17} /> Send back</button>
        </>
      }>
      <div className="field"><span>Send it back to</span></div>
      <div className="targets">
        {targets.map((t) => (
          <label key={t.key} className={`target ${target === t.key ? 'on' : ''}`}>
            <input type="radio" name="target" checked={target === t.key} onChange={() => setTarget(t.key)} />
            <span className="target-main">
              <b>{t.name}</b>
              {t.chart && <i className="flag">As in the flow chart</i>}
              <span className="target-people">
                {t.people.slice(0, 3).map((x) => <Person key={x.name} name={x.name} role={x.short} size={22} />)}
              </span>
            </span>
          </label>
        ))}
      </div>
      {cur && (
        <p className="goes">
          <span>This goes to</span> {cur.people.map((x) => `${x.name} (${x.short})`).join(' and ')}
          <small>{isChart ? 'After they fix it, it follows the flow chart.' : 'When they finish, it comes straight back to you.'}</small>
        </p>
      )}
      <Field label="Why?"><textarea rows={3} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Tell them what to fix" /></Field>
      {cur && (
        <div className="two">
          <Field label="Send it to">
            {cur.pick ? (
              <select value={who} onChange={(e) => setWho(e.target.value)}>
                <option value="">Anyone in the team ({cur.people.map((x) => shortName(x.name)).join(', ')})</option>
                {cur.people.map((x) => <option key={x.id} value={x.id}>{x.name} ({x.short})</option>)}
              </select>
            ) : <input readOnly value={cur.people.map((x) => `${shortName(x.name)} (${x.short})`).join(', ')} />}
          </Field>
          <Field label="Fix it by"><input type="date" value={due} min={new Date().toISOString().slice(0, 10)} onChange={(e) => setDue(e.target.value)} /></Field>
        </div>
      )}
      {!isChart && (
        <DocSlot pid={p.id} project={proj} slot={slot} stepKey={a.key}
          onChange={(r) => { setDocs([...docs, ...(r.ids || [])]); if (r.project) setProj(r.project) }} />
      )}
      {error && <p className="form-error" role="alert">{error}</p>}
    </Modal>
  )
}

/* ---------- hold / reject (the chart's Hold/Reject box without a loop) ---------- */
export function WhyDialog({ p, a, options, onClose, onDone }) {
  const { toast } = useApp()
  const [note, setNote] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const go = async (key) => {
    setBusy(true)
    try {
      const r = await api.post(`/api/projects/${p.id}/runs/${a.run_id}/act`, { option: key, note })
      toast(r.message)
      onDone(r.project)
    } catch (e) {
      setError(e.message)
      setBusy(false)
    }
  }
  return (
    <Modal title={options.length > 1 ? 'Hold or reject' : 'Reject'} onClose={onClose}
      footer={
        <>
          <button className="btn" onClick={onClose}>Cancel</button>
          {options.map((o) => (
            <button key={o.key} disabled={busy} className={`btn ${o.kind === 'hold' ? 'amber' : 'danger'}`} onClick={() => go(o.key)}>
              {o.kind === 'hold' ? <Pause size={17} /> : <X size={17} />} {o.kind === 'hold' ? 'Hold for now' : 'Reject'}
            </button>
          ))}
        </>
      }>
      <p className="muted">The initiator and both Directors are told.</p>
      <Field label="Why?"><textarea rows={3} value={note} onChange={(e) => setNote(e.target.value)} autoFocus /></Field>
      {error && <p className="form-error" role="alert">{error}</p>}
    </Modal>
  )
}

/* ---------- approve with a question (India review): choose, then say who gets it and by when ---------- */
export function ChoiceDialog({ a, options, nexts, setNexts, busy, onPick, onClose }) {
  const [sel, setSel] = useState(null)
  const nx = sel ? a.next[sel] : null
  return (
    <Modal title="Is the information complete?" onClose={onClose} size="wide"
      footer={<><button className="btn" onClick={onClose}>Cancel</button><button className="btn ok" disabled={!sel || busy} onClick={() => onPick(sel)}><Check size={17} strokeWidth={3} /> Confirm</button></>}>
      <div className="big-choices">
        {options.map((o) => {
          const n = a.next[o.key]
          return (
            <button key={o.key} className={`big-choice ${sel === o.key ? 'on' : ''}`} onClick={() => setSel(o.key)}>
              <Check size={24} />
              <span>{o.short || o.label}{n?.steps?.length > 0 && <small>goes to {n.steps[0].name} · {n.steps[0].people.map((x) => shortName(x.name)).join(', ')}</small>}</span>
            </button>
          )
        })}
      </div>
      {nx && <HandoverPicker nx={nx} value={nexts} onChange={setNexts} />}
    </Modal>
  )
}

/* ---------- ask for more time (goes to whoever gave the date) ---------- */
export function AskTimeDialog({ p, kind, runId, taskId, due, to, label, onClose, onDone }) {
  const { toast } = useApp()
  const [date, setDate] = useState(tomorrowISO(Math.max(2, Math.ceil((new Date(due) - Date.now()) / 86400000) + 2)))
  const [reason, setReason] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const go = async () => {
    setBusy(true)
    try {
      const url = kind === 'task' ? `/api/projects/${p.id}/tasks/${taskId}/extend` : `/api/projects/${p.id}/runs/${runId}/extend`
      const r = await api.post(url, { new_due: date, reason })
      toast(r.message)
      onDone(r.project)
    } catch (e) {
      setError(e.message)
      setBusy(false)
    }
  }
  return (
    <Modal title="Ask for more time" onClose={onClose}
      footer={<><button className="btn" onClick={onClose}>Cancel</button><button className="btn primary" disabled={busy} onClick={go}>Send request</button></>}>
      <p className="muted">{label}. Now due <b>{fmtDate(due)}</b>.</p>
      <Field label="New date"><input type="date" value={date} min={tomorrowISO(1)} onChange={(e) => setDate(e.target.value)} /></Field>
      <Field label="Why do you need more time?"><textarea rows={3} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="One or two lines" /></Field>
      {to && <p className="goes"><span>This request goes to</span><Person name={to.name} role={to.short} size={24} /><small>They gave you this date and will say yes or no.</small></p>}
      {error && <p className="form-error" role="alert">{error}</p>}
    </Modal>
  )
}

export function SetDueDialog({ p, a, onClose, onDone }) {
  const { toast } = useApp()
  const [date, setDate] = useState(a.due_at.slice(0, 10))
  const [error, setError] = useState('')
  const go = async () => {
    try {
      onDone(await api.post(`/api/projects/${p.id}/runs/${a.run_id}/due`, { due: date }))
      toast('Date changed')
    } catch (e) {
      setError(e.message)
    }
  }
  return (
    <Modal title="Change the date" onClose={onClose}
      footer={<><button className="btn" onClick={onClose}>Cancel</button><button className="btn primary" onClick={go}>Save</button></>}>
      <Field label={`New date for “${a.name}”`}><input type="date" value={date} onChange={(e) => setDate(e.target.value)} /></Field>
      <p className="muted small">The people it is waiting for are told.</p>
      {error && <p className="form-error" role="alert">{error}</p>}
    </Modal>
  )
}

export function AssignDialog({ p, a, onClose, onDone }) {
  const { toast } = useApp()
  const [who, setWho] = useState(a.assignee?.id || '')
  const [error, setError] = useState('')
  const go = async () => {
    try {
      onDone(await api.post(`/api/projects/${p.id}/runs/${a.run_id}/assign`, { assignee_id: who ? Number(who) : null }))
      toast('Saved')
    } catch (e) {
      setError(e.message)
    }
  }
  return (
    <Modal title="Change who has it" onClose={onClose}
      footer={<><button className="btn" onClick={onClose}>Cancel</button><button className="btn primary" onClick={go}>Save</button></>}>
      <Field label={`Who should do “${a.name}”?`}>
        <select value={who} onChange={(e) => setWho(e.target.value)}>
          <option value="">Anyone in the team</option>
          {a.assign_options.map((x) => <option key={x.id} value={x.id}>{x.name} ({x.short})</option>)}
        </select>
      </Field>
      <p className="muted small">The person is told. The date stays the same.</p>
      {error && <p className="form-error" role="alert">{error}</p>}
    </Modal>
  )
}

/* ---------- give a task ---------- */
export function TaskDialog({ p, onClose, onDone }) {
  const { toast } = useApp()
  const [people, setPeople] = useState([])
  const [f, setF] = useState({ title: '', assignee_id: '', due: tomorrowISO(3), details: '', step_key: '', blocking: false })
  const [error, setError] = useState('')
  const [pending, setPending] = useState([])
  const [adding, setAdding] = useState(false)
  useEffect(() => { api.get('/api/people').then(setPeople).catch(() => {}) }, [])
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const who = people.find((x) => String(x.id) === String(f.assignee_id))
  const go = async () => {
    try {
      let r = await api.post(`/api/projects/${p.id}/tasks`, { ...f, assignee_id: Number(f.assignee_id) || 0 })
      const id = r.new_task_id
      for (const spec of pending) r = { ...r, ...(await sendDoc(p.id, spec, { taskId: id })) , new_task_id: id }
      onDone(r.project || r)
      toast('Task given')
    } catch (e) {
      setError(e.message)
    }
  }
  return (
    <Modal title="Give a task" onClose={onClose}
      footer={<><button className="btn" onClick={onClose}>Cancel</button><button className="btn primary" onClick={go}>Give task</button></>}>
      <Field label="What needs to be done?"><input value={f.title} onChange={set('title')} placeholder="e.g. Get the GMP clearance letter" autoFocus /></Field>
      <div className="two">
        <Field label="Give it to">
          <select value={f.assignee_id} onChange={set('assignee_id')}>
            <option value="">Choose a person…</option>
            {people.map((x) => <option key={x.id} value={x.id}>{x.name} · {x.short}</option>)}
          </select>
        </Field>
        <Field label="Due date"><input type="date" value={f.due} min={tomorrowISO(0)} onChange={set('due')} /></Field>
      </div>
      <Field label="Details (optional)"><textarea rows={2} value={f.details} onChange={set('details')} /></Field>
      <Field label="Linked to step (optional)">
        <select value={f.step_key} onChange={set('step_key')}>
          <option value="">Not linked</option>
          {p.steps.filter((s) => ['current', 'upcoming'].includes(s.state)).slice(0, 14).map((s) => <option key={s.key} value={s.key}>{s.name}</option>)}
        </select>
      </Field>
      {f.step_key && (
        <label className="check"><input type="checkbox" checked={f.blocking} onChange={(e) => setF({ ...f, blocking: e.target.checked })} /> That step cannot be finished until this task is done</label>
      )}
      <div className="task-docs">
        {pending.map((d, i) => (
          <span key={i} className="docchip"><a><FilePlus2 size={15} /><span>{d.existing ? `${d.existing.length} existing document${d.existing.length > 1 ? 's' : ''}` : d.title || d.files?.[0]?.name || d.url}</span></a>
            <button className="x" aria-label="Remove" onClick={() => setPending(pending.filter((_, j) => j !== i))}><X size={13} /></button></span>
        ))}
        <button className="link" onClick={() => setAdding(true)}><FilePlus2 size={15} /> Add a document (optional)</button>
      </div>
      {adding && <DocDialog pid={p.id} project={p} label="Task" collect={(spec) => setPending([...pending, spec])} onClose={() => setAdding(false)} />}
      {who && <p className="goes"><span>This goes to</span><Person name={who.name} role={who.short} size={24} /><small>They will see this project and get a notification.</small></p>}
      {error && <p className="form-error" role="alert">{error}</p>}
    </Modal>
  )
}

/* ---------- fast track ---------- */
export function FastTrackDialog({ p, onClose, onDone }) {
  const { toast } = useApp()
  const on = p.fast_track
  const go = async () => {
    onDone(await api.post(`/api/projects/${p.id}/fasttrack`, { on: !on }))
    toast(on ? 'Fast track is off' : 'Fast track is on')
  }
  return (
    <Modal title="Fast track" onClose={onClose}
      footer={<><button className="btn" onClick={onClose}>Close</button><button className="btn primary" onClick={go}><FastForward size={17} /> {on ? 'Turn off' : 'Turn on'}</button></>}>
      <p>The flow chart runs these parts one after the other. They do not depend on each other, so with <b>Fast track</b> they run side by side and the project waits until all of them are finished.</p>
      {p.groups.map((g) => (
        <div key={g.id} className="ft-group">
          <b>{g.name}</b>
          <small>{g.why}</small>
          <span className="ft-tracks">{g.tracks.map((t) => <i key={t.name}>{t.name}</i>)}</span>
          {g.mode && <small>Already started: {g.mode === 'fast' ? 'side by side' : 'one after another'}</small>}
        </div>
      ))}
      <p className="muted small">It applies to parts that have not started yet.</p>
    </Modal>
  )
}

/* ---------- answer a request for more time ---------- */
export function RequestBox({ p, req, label, onChange }) {
  const { toast } = useApp()
  const [declining, setDeclining] = useState(false)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const decide = async (approve) => {
    setBusy(true)
    try {
      onChange(await api.post(`/api/projects/${p.id}/requests/${req.id}/decide`, { approve, note }))
      toast(approve ? 'Approved' : 'Declined')
    } catch (e) {
      toast(e.message, 'err')
      setBusy(false)
    }
  }
  return (
    <div className="reqbox">
      <div className="req-top">
        <Avatar name={req.requested_by.name} size={30} />
        <span><b>{req.requested_by.name}</b> asks for more time{label ? ` on “${label}”` : ''}<small>{fmtDate(req.old_due)} → <b>{fmtDate(req.new_due)}</b></small></span>
      </div>
      <q>{req.reason}</q>
      {req.can_decide ? (
        declining ? (
          <div className="req-actions">
            <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Why not?" aria-label="Reason for declining" autoFocus />
            <button className="btn small danger" disabled={busy} onClick={() => decide(false)}>Decline</button>
            <button className="btn small" onClick={() => setDeclining(false)}>Back</button>
          </div>
        ) : (
          <div className="req-actions">
            <button className="btn small ok" disabled={busy} onClick={() => decide(true)}><Check size={15} /> Approve</button>
            <button className="btn small bad" onClick={() => setDeclining(true)}>Decline</button>
          </div>
        )
      ) : (
        <small className="muted">Waiting for {req.approver.name} ({req.approver.short}) to answer.</small>
      )}
    </div>
  )
}
