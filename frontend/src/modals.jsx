import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Download, FileSpreadsheet, Hammer, Handshake } from 'lucide-react'
import { api, fileUrl } from './api'
import { useApp } from './ctx'
import { Field, Modal } from './ui'

function useInitiators(enabled) {
  const [list, setList] = useState([])
  useEffect(() => {
    if (enabled) api.get('/api/users').then((u) => setList(u.filter((x) => x.role === 'initiator' && x.active))).catch(() => {})
  }, [enabled])
  return list
}

export function NewProject({ onClose }) {
  const { user, toast } = useApp()
  const nav = useNavigate()
  const [f, setF] = useState({ title: '', ptype: '', market: 'Australia', est_value: '', description: '', initiator_id: '' })
  const initiators = useInitiators(user.role === 'admin')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })

  const submit = async () => {
    setError('')
    if (!f.title.trim()) return setError('Please give the project a name.')
    if (!f.ptype) return setError('Please choose Development or In-Licence.')
    setBusy(true)
    try {
      const p = await api.post('/api/projects', {
        ...f,
        est_value: f.est_value === '' ? null : Number(f.est_value),
        initiator_id: f.initiator_id ? Number(f.initiator_id) : null,
      })
      toast('Project added')
      onClose()
      nav(`/projects/${p.id}`)
    } catch (e) {
      setError(e.message)
      setBusy(false)
    }
  }

  return (
    <Modal
      title="New project"
      onClose={onClose}
      footer={
        <>
          <button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn primary" onClick={submit} disabled={busy}>{busy ? 'Adding…' : 'Add project'}</button>
        </>
      }
    >
      <Field label="Project name">
        <input value={f.title} onChange={set('title')} placeholder="e.g. Vitamin C Effervescent 1000mg" autoFocus />
      </Field>
      <div className="field">
        <span>Type</span>
        <div className="choice">
          <button type="button" className={f.ptype === 'development' ? 'on' : ''} onClick={() => setF({ ...f, ptype: 'development' })}>
            <Hammer size={22} />
            <b>Development</b>
            <small>We develop it with a manufacturer</small>
          </button>
          <button type="button" className={f.ptype === 'in_licence' ? 'on' : ''} onClick={() => setF({ ...f, ptype: 'in_licence' })}>
            <Handshake size={22} />
            <b>In-Licence</b>
            <small>We take a ready product from a partner</small>
          </button>
        </div>
      </div>
      <div className="two">
        <Field label="Market"><input value={f.market} onChange={set('market')} /></Field>
        <Field label="Est. yearly sales (A$)"><input type="number" min="0" value={f.est_value} onChange={set('est_value')} placeholder="optional" /></Field>
      </div>
      {user.role === 'admin' && (
        <Field label="Project Initiator">
          <select value={f.initiator_id} onChange={set('initiator_id')}>
            <option value="">Choose…</option>
            {initiators.map((i) => <option key={i.id} value={i.id}>{i.name}</option>)}
          </select>
        </Field>
      )}
      <Field label="Short description">
        <textarea rows={3} value={f.description} onChange={set('description')} placeholder="What is the product?" />
      </Field>
      {error && <p className="form-error" role="alert">{error}</p>}
    </Modal>
  )
}

export function ImportExcel({ onClose, onDone }) {
  const { user, toast } = useApp()
  const [file, setFile] = useState(null)
  const initiators = useInitiators(user.role === 'admin')
  const [ini, setIni] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const input = useRef()

  const go = async () => {
    if (!file) return setError('Please choose the Excel file first.')
    setBusy(true)
    setError('')
    const form = new FormData()
    form.append('file', file)
    if (ini) form.append('initiator_id', ini)
    try {
      const r = await api.upload('/api/projects/import', form)
      toast(`${r.created} project${r.created === 1 ? '' : 's'} added`)
      onDone()
    } catch (e) {
      setError(e.message)
      setBusy(false)
    }
  }
  return (
    <Modal
      title="Add projects from Excel"
      onClose={onClose}
      footer={
        <>
          <button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn primary" onClick={go} disabled={busy}>{busy ? 'Adding…' : 'Add projects'}</button>
        </>
      }
    >
      <a className="btn block" href={fileUrl('/api/projects/import-template.xlsx')}><Download size={17} /> 1 · Download the Excel template</a>
      {user.role === 'admin' && (
        <Field label="Project Initiator for these projects">
          <select value={ini} onChange={(e) => setIni(e.target.value)}>
            <option value="">Choose…</option>
            {initiators.map((i) => <option key={i.id} value={i.id}>{i.name}</option>)}
          </select>
        </Field>
      )}
      <button className="dropzone" onClick={() => input.current.click()}>
        <FileSpreadsheet size={28} strokeWidth={1.5} />
        <b>{file ? file.name : '2 · Choose your filled Excel file'}</b>
      </button>
      <input ref={input} type="file" accept=".xlsx" hidden onChange={(e) => setFile(e.target.files[0] || null)} />
      {error && <p className="form-error" role="alert">{error}</p>}
    </Modal>
  )
}

export function ChangePassword({ onClose }) {
  const { toast } = useApp()
  const [f, setF] = useState({ old_password: '', new_password: '', again: '' })
  const [error, setError] = useState('')
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const save = async () => {
    if (f.new_password !== f.again) return setError('The two new passwords are not the same.')
    try {
      await api.post('/api/auth/password', { old_password: f.old_password, new_password: f.new_password })
      toast('Password changed')
      onClose()
    } catch (e) {
      setError(e.message)
    }
  }
  return (
    <Modal title="Change password" onClose={onClose}
      footer={<><button className="btn" onClick={onClose}>Cancel</button><button className="btn primary" onClick={save}>Save</button></>}>
      <Field label="Current password"><input type="password" value={f.old_password} onChange={set('old_password')} autoComplete="current-password" /></Field>
      <Field label="New password" hint="At least 6 characters"><input type="password" value={f.new_password} onChange={set('new_password')} autoComplete="new-password" /></Field>
      <Field label="New password again"><input type="password" value={f.again} onChange={set('again')} autoComplete="new-password" /></Field>
      {error && <p className="form-error" role="alert">{error}</p>}
    </Modal>
  )
}
