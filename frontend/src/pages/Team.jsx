import { useEffect, useMemo, useState } from 'react'
import { Plus } from 'lucide-react'
import { api } from '../api'
import { useApp } from '../ctx'
import { Avatar, ErrorNote, Field, Modal, Pill, RoleChip, Spinner } from '../ui'

function PersonForm({ person, people, onClose, onSaved }) {
  const { def, toast } = useApp()
  const [f, setF] = useState(person
    ? { name: person.name, email: person.email, role: person.role, title: person.title, password: '', active: person.active, manager_id: person.manager_id || '' }
    : { name: '', email: '', role: 'initiator', title: '', password: '', active: true, manager_id: '' })
  const [error, setError] = useState('')
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const save = async () => {
    try {
      const body = { ...f, manager_id: f.manager_id ? Number(f.manager_id) : null }
      person ? await api.put(`/api/users/${person.id}`, body) : await api.post('/api/users', body)
      toast(person ? 'Saved' : 'Person added')
      onSaved()
    } catch (e) {
      setError(e.message)
    }
  }
  return (
    <Modal title={person ? 'Edit person' : 'Add a person'} onClose={onClose}
      footer={<><button className="btn" onClick={onClose}>Cancel</button><button className="btn primary" onClick={save}>Save</button></>}>
      <Field label="Full name"><input value={f.name} onChange={set('name')} /></Field>
      <Field label="Email (used to sign in)"><input type="email" value={f.email} onChange={set('email')} /></Field>
      <div className="two">
        <Field label="Role in the flow">
          <select value={f.role} onChange={set('role')}>{def.roles.map((r) => <option key={r.key} value={r.key}>{r.label}</option>)}</select>
        </Field>
        <Field label="Reports to">
          <select value={f.manager_id} onChange={set('manager_id')}>
            <option value="">Nobody</option>
            {people.filter((x) => x.active && x.id !== person?.id && x.role !== 'admin').map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
          </select>
        </Field>
      </div>
      <Field label="Job title"><input value={f.title} onChange={set('title')} /></Field>
      <Field label={person ? 'New password (leave empty to keep)' : 'Password'}><input type="text" value={f.password} onChange={set('password')} autoComplete="off" /></Field>
      {person && <label className="check"><input type="checkbox" checked={f.active} onChange={(e) => setF({ ...f, active: e.target.checked })} /> Can sign in</label>}
      {error && <p className="form-error" role="alert">{error}</p>}
    </Modal>
  )
}

function Branch({ u, kids, admin, onEdit, roles }) {
  const children = kids[u.id] || []
  return (
    <li>
      <button className={`person ${u.active ? '' : 'off'}`} disabled={!admin} onClick={() => onEdit(u)}>
        <Avatar name={u.name} size={40} />
        <span className="grow">
          <b>{u.name}</b>
          <small>{u.title || roles[u.role].label}</small>
        </span>
        <RoleChip owner={{ role: u.role, short: roles[u.role].short, label: roles[u.role].label }} roles={roles} />
        {!u.active && <Pill tone="gray">Off</Pill>}
      </button>
      {children.length > 0 && (
        <ul>{children.map((c) => <Branch key={c.id} u={c} kids={kids} admin={admin} onEdit={onEdit} roles={roles} />)}</ul>
      )}
    </li>
  )
}

export default function Team() {
  const { user, roles } = useApp()
  const [list, setList] = useState(null)
  const [err, setErr] = useState('')
  const [edit, setEdit] = useState(null)
  const load = () => api.get('/api/users').then(setList).catch((e) => setErr(e.message))
  useEffect(() => { load() }, [])
  const { roots, kids, office } = useMemo(() => {
    const kids = {}
    const roots = []
    for (const u of list || []) {
      if (u.role === 'admin') continue
      if (u.manager_id) (kids[u.manager_id] ||= []).push(u)
      else roots.push(u)
    }
    return { roots, kids, office: (list || []).filter((u) => u.role === 'admin') }
  }, [list])
  if (err) return <ErrorNote error={err} retry={load} />
  if (!list) return <Spinner />
  const admin = user.role === 'admin'

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Team</h1>
          <p className="muted">Who reports to whom. Overdue work is escalated up this line.</p>
        </div>
        {admin && <button className="btn primary" onClick={() => setEdit('new')}><Plus size={19} /> Add person</button>}
      </div>
      <div className="orgs">
        {roots.map((r) => (
          <section className="card org" key={r.id}>
            <ul className="tree"><Branch u={r} kids={kids} admin={admin} onEdit={setEdit} roles={roles} /></ul>
          </section>
        ))}
      </div>
      {office.length > 0 && (
        <section className="card org">
          <small className="muted">Office</small>
          <ul className="tree flat">{office.map((u) => <Branch key={u.id} u={u} kids={{}} admin={admin} onEdit={setEdit} roles={roles} />)}</ul>
        </section>
      )}
      {edit && <PersonForm person={edit === 'new' ? null : edit} people={list} onClose={() => setEdit(null)} onSaved={() => { setEdit(null); load() }} />}
    </div>
  )
}
