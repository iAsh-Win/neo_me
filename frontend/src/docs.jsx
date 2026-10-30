import { useMemo, useRef, useState } from 'react'
import { Check, FilePlus2, Link2, Paperclip, Search } from 'lucide-react'
import { api } from './api'
import { useApp } from './ctx'
import { DocChip, Field, Modal } from './ui'
import { fmtDate } from './format'

/** Send one document (name + file(s) and/or link) to the project. Returns { ids, project }. */
export async function sendDoc(pid, spec, target = {}) {
  if (spec.existing?.length) {
    return api.post(`/api/projects/${pid}/documents/attach`, {
      doc_ids: spec.existing, step_key: target.stepKey || '', doc_type: target.docType || '', task_id: target.taskId || null,
    })
  }
  const form = new FormData()
  for (const f of spec.files || []) form.append('files', f)
  form.append('step_key', target.stepKey || '')
  form.append('doc_type', target.docType || '')
  form.append('title', spec.title || '')
  form.append('url', spec.url || '')
  if (target.taskId) form.append('task_id', target.taskId)
  return api.upload(`/api/projects/${pid}/documents`, form)
}

/**
 * One way to add anything: a name, a file, a link – or pick something that is already in the project.
 * `collect` (optional) hands the choice back without uploading (used while a task is being written).
 */
export function DocDialog({ pid, project, target = {}, label, collect, onDone, onClose }) {
  const { toast } = useApp()
  const input = useRef()
  const [tab, setTab] = useState('new')
  const [title, setTitle] = useState('')
  const [url, setUrl] = useState('')
  const [files, setFiles] = useState([])
  const [picked, setPicked] = useState([])
  const [q, setQ] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const here = (d) => (d.source_id || d.id)
  const taken = new Set((project?.documents || [])
    .filter((d) => (d.step_key || '') === (target.stepKey || '') && (d.doc_type || '') === (target.docType || '') && (d.task_id || null) === (target.taskId || null))
    .map(here))
  const ids = new Set((project?.documents || []).map((d) => d.id))
  const library = useMemo(() => (project?.documents || [])
    .filter((d) => (!d.source_id || !ids.has(d.source_id)) && !taken.has(here(d)))
    .filter((d) => !q || `${d.title} ${d.step_name} ${d.doc_label}`.toLowerCase().includes(q.toLowerCase())), // eslint-disable-line
  [project, q]) // eslint-disable-line

  const go = async () => {
    setError('')
    const spec = tab === 'new' ? { title, url, files } : { existing: picked }
    if (tab === 'new' && !files.length && !url.trim()) return setError('Please choose a file or paste a link.')
    if (tab === 'old' && !picked.length) return setError('Please tick at least one document.')
    if (collect) { collect(spec); onClose(); return }
    setBusy(true)
    try {
      const r = await sendDoc(pid, spec, target)
      toast(tab === 'old' ? 'Document added here' : 'Document added')
      onDone(r)
      onClose()
    } catch (e) {
      setError(e.message)
      setBusy(false)
    }
  }
  const toggle = (id) => setPicked(picked.includes(id) ? picked.filter((x) => x !== id) : [...picked, id])

  return (
    <Modal title={label ? `Add a document – ${label}` : 'Add a document'} onClose={onClose}
      footer={<><button className="btn" onClick={onClose}>Cancel</button><button className="btn primary" disabled={busy} onClick={go}>{tab === 'old' ? 'Use selected' : 'Add'}</button></>}>
      {library.length > 0 || tab === 'old' ? (
        <div className="seg" role="tablist">
          <button role="tab" aria-selected={tab === 'new'} className={tab === 'new' ? 'on' : ''} onClick={() => setTab('new')}><FilePlus2 size={15} /> New</button>
          <button role="tab" aria-selected={tab === 'old'} className={tab === 'old' ? 'on' : ''} onClick={() => setTab('old')}>Already in this project</button>
        </div>
      ) : null}
      {tab === 'new' ? (
        <>
          <Field label="Name"><input value={title} onChange={(e) => setTitle(e.target.value)} placeholder={files[0]?.name || 'e.g. Stability data – June'} autoFocus /></Field>
          <div className="field">
            <span>File</span>
            <button type="button" className="filebox" onClick={() => input.current.click()}>
              <Paperclip size={17} />
              {files.length ? files.map((f) => f.name).join(', ') : 'Choose a file (or several)'}
            </button>
            <input ref={input} type="file" multiple hidden aria-label="Choose files" onChange={(e) => setFiles([...e.target.files])} />
          </div>
          <Field label="Link (SharePoint, Drive, any web address)" hint="Add a file, a link, or both.">
            <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://" />
          </Field>
          {files.length > 1 && <p className="muted small">Each file keeps its own file name.</p>}
        </>
      ) : (
        <>
          <div className="searchbox"><Search size={16} /><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search the project's documents" aria-label="Search documents" /></div>
          <ul className="picklist">
            {library.map((d) => (
              <li key={d.id}>
                <label className={picked.includes(d.id) ? 'on' : ''}>
                  <input type="checkbox" checked={picked.includes(d.id)} onChange={() => toggle(d.id)} />
                  <span className="box"><Check size={13} strokeWidth={3.5} /></span>
                  <span className="pick-main"><b>{d.title}</b><small>{d.doc_label || d.step_name || (d.task_title ? `Task: ${d.task_title}` : 'General')} · {d.user.name} · {fmtDate(d.at)}</small></span>
                </label>
              </li>
            ))}
            {library.length === 0 && <li className="muted center">Nothing else to use yet.</li>}
          </ul>
        </>
      )}
      {error && <p className="form-error" role="alert">{error}</p>}
    </Modal>
  )
}

/** One kind of document a step needs: what is attached, and one button to add more. */
export function DocSlot({ pid, project, slot, stepKey, taskId, onChange, mine = true, compact }) {
  const { toast, user } = useApp()
  const [adding, setAdding] = useState(false)
  const has = slot.items.length > 0
  const remove = async (d) => {
    if (!confirm(`Remove “${d.title}”?`)) return
    try { onChange({ project: await api.del(`/api/documents/${d.id}`) }) } catch (e) { toast(e.message, 'err') }
  }
  return (
    <div className={`slot ${compact ? 'compact' : ''} ${has ? 'ok' : slot.required && mine ? 'need' : ''}`}>
      <div className="slot-head">
        <span className="slot-state">{has ? <Check size={14} strokeWidth={3} /> : slot.required && mine ? '!' : ''}</span>
        <b>{slot.label}</b>
        <small>{slot.role_short ? `${slot.role_short} · ` : ''}{slot.required ? 'required' : 'optional'}</small>
        {mine && <button className="btn small slot-btn" onClick={() => setAdding(true)}><FilePlus2 size={15} /> {has ? 'Add more' : 'Add document'}</button>}
      </div>
      {has && (
        <div className="slot-items">
          {slot.items.map((d) => (
            <DocChip key={d.id} doc={d} onRemove={mine && (user.role === 'admin' || d.user.id === user.id) ? () => remove(d) : null} />
          ))}
        </div>
      )}
      {adding && (
        <DocDialog pid={pid} project={project} target={{ stepKey, docType: slot.key, taskId }} label={slot.label}
          onDone={onChange} onClose={() => setAdding(false)} />
      )}
    </div>
  )
}

export { Link2 }
