import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, ArrowRight, CheckCheck, ChevronRight, Plus } from 'lucide-react'
import { api } from '../api'
import { useApp } from '../ctx'
import { AvatarStack, DuePill, ErrorNote, JourneyDots, PhaseTile, Pill, Spinner, StatusPill } from '../ui'
import { plural } from '../format'
import { NewProject } from '../modals'

const greet = () => {
  const h = new Date().getHours()
  return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening'
}

export function TaskCard({ p, onOpen }) {
  const { phases } = useApp()
  const color = phases[p.phase]?.color
  return (
    <button className={`task ${p.overdue ? 'late' : ''}`} onClick={onOpen}>
      <PhaseTile phase={p.phase} color={color} size={48} />
      <span className="task-main">
        <b>{p.title}</b>
        <span className="task-step">{p.step_name}</span>
      </span>
      <DuePill project={p} />
      <span className="btn primary go">{p.mode === 'decision' ? 'Decide' : 'Open'} <ArrowRight size={16} /></span>
    </button>
  )
}

function ProjectRow({ p, onOpen }) {
  const { def } = useApp()
  return (
    <button className="prow" onClick={onOpen}>
      <span className="task-main">
        <b>{p.title}</b>
        <span className="task-step">{p.step_name}</span>
      </span>
      <JourneyDots phases={def.phases} current={p.phase} status={p.status} />
      {p.waiting.length > 0 && <AvatarStack names={p.waiting.flatMap((w) => w.people)} size={26} />}
      <StatusPill project={p} />
      <ChevronRight size={18} className="chev" />
    </button>
  )
}

export default function Home() {
  const { user, roles, canAdd } = useApp()
  const nav = useNavigate()
  const [d, setD] = useState(null)
  const [err, setErr] = useState('')
  const [adding, setAdding] = useState(false)
  const load = () => api.get('/api/dashboard').then(setD).catch((e) => setErr(e.message))
  useEffect(() => { load() }, [])

  if (err) return <ErrorNote error={err} retry={() => { setErr(''); load() }} />
  if (!d) return <Spinner />
  const c = d.counts
  const oversight = d.view !== 'staff'

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>{greet()}, {user.name.split(' ')[0]}</h1>
          <p className="muted">{roles[user.role]?.label}</p>
        </div>
        {canAdd && <button className="btn primary" onClick={() => setAdding(true)}><Plus size={19} /> New project</button>}
      </div>

      <section className={`hero ${c.waiting_me ? 'busy' : 'calm'}`}>
        <div className="hero-main">
          {c.waiting_me ? (
            <>
              <b className="hero-num">{c.waiting_me}</b>
              <span>{c.waiting_me === 1 ? 'task needs' : 'tasks need'} you</span>
            </>
          ) : (
            <>
              <CheckCheck size={40} strokeWidth={1.7} />
              <span>You are all caught up</span>
            </>
          )}
        </div>
        <div className="hero-stats">
          <button onClick={() => nav('/projects?show=active')}><b>{c.active}</b><span>In progress</span></button>
          <button onClick={() => nav('/projects?show=on_hold')}><b>{c.on_hold}</b><span>On hold</span></button>
          <button onClick={() => nav('/projects?show=done')}><b>{c.completed}</b><span>Completed</span></button>
          {oversight && <button className={c.overdue ? 'warn' : ''} onClick={() => nav('/projects?show=late')}><b>{c.overdue}</b><span>Overdue</span></button>}
        </div>
      </section>

      {d.mine.length > 0 && (
        <section>
          <h2 className="sec">Needs you now</h2>
          <div className="tasks">{d.mine.map((p) => <TaskCard key={p.id} p={p} onOpen={() => nav(`/projects/${p.id}`)} />)}</div>
        </section>
      )}

      {oversight && d.overdue?.filter((p) => !p.can_act).length > 0 && (
        <section>
          <h2 className="sec warn"><AlertTriangle size={18} /> Running late</h2>
          <div className="list">{d.overdue.filter((p) => !p.can_act).map((p) => <ProjectRow key={p.id} p={p} onOpen={() => nav(`/projects/${p.id}`)} />)}</div>
        </section>
      )}

      {oversight && d.pipeline && (
        <section>
          <h2 className="sec">Where projects are</h2>
          <div className="stages">
            {d.pipeline.map((s, i) => (
              <button key={s.key} className={s.count ? '' : 'zero'} style={{ '--c': s.color }} onClick={() => nav(`/projects?phase=${s.key}`)}>
                <PhaseTile phase={s.key} color={s.color} size={38} />
                <b>{s.count}</b>
                <span>{s.name}</span>
              </button>
            ))}
          </div>
        </section>
      )}

      {d.following.length > 0 && (
        <section>
          <h2 className="sec">{oversight ? 'All active projects' : 'My other projects'} <Pill tone="gray">{d.following.length}</Pill></h2>
          <div className="list">{d.following.slice(0, oversight ? 6 : 12).map((p) => <ProjectRow key={p.id} p={p} onOpen={() => nav(`/projects/${p.id}`)} />)}</div>
          {d.following.length > (oversight ? 6 : 12) && <button className="link more" onClick={() => nav('/projects')}>See all {plural(d.following.length, 'project')} <ArrowRight size={15} /></button>}
        </section>
      )}

      {!oversight && d.mine.length === 0 && d.following.length === 0 && (
        <p className="muted center">Projects appear here when it is your turn to work on them.</p>
      )}
      {adding && <NewProject onClose={() => setAdding(false)} />}
    </div>
  )
}
