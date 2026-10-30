import { ArrowRight } from 'lucide-react'
import { shortName } from './format'
import { Avatar } from './ui'

function NextLine({ nx }) {
  if (!nx) return null
  if (nx.end) return <p className="goes"><span>Then</span> the project is finished.</p>
  if (nx.wait) return <p className="goes"><span>Then</span> it waits until the other tracks are finished.</p>
  return null
}

const todayISO = () => new Date().toISOString().slice(0, 10)

export function HandoverPicker({ nx, value, onChange, joint }) {
  if (!nx || nx.end || nx.wait || !nx.steps?.length) return <NextLine nx={nx} />
  const val = (s) => value[s.key] || { assignee_id: '', due: s.default_due }
  const set = (s, patch) => onChange({ ...value, [s.key]: { ...val(s), ...patch } })
  return (
    <section className="handover">
      <h4><ArrowRight size={15} /> Next: hand over</h4>
      {nx.steps.map((s) => {
        const v = val(s)
        return (
          <div className="ho-card" key={s.key}>
            <b className="ho-step">{s.name}</b>
            <div className="ho-grid">
              <label className="field">
                <span>Send to</span>
                {s.pick ? (
                  <select value={v.assignee_id} onChange={(e) => set(s, { assignee_id: e.target.value })} aria-label={`Who gets ${s.name}`}>
                    <option value="">Anyone in the team</option>
                    {s.people.map((x) => <option key={x.id} value={x.id}>{x.name} ({x.short})</option>)}
                  </select>
                ) : (
                  <span className="ho-people">
                    {s.people.map((x) => <span key={x.id} className="ho-person"><Avatar name={x.name} size={22} />{shortName(x.name)} <small>{x.short}</small></span>)}
                  </span>
                )}
              </label>
              <label className="field">
                <span>Due date</span>
                <input type="date" value={v.due} min={todayISO()} onChange={(e) => set(s, { due: e.target.value })} aria-label={`Due date for ${s.name}`} />
              </label>
            </div>
          </div>
        )
      })}
      {joint && <small className="muted">Goes on once every team has signed.</small>}
    </section>
  )
}

export const nextsBody = (nx, value) => Object.fromEntries((nx?.steps || []).map((s) => {
  const v = value[s.key] || {}
  return [s.key, { assignee_id: v.assignee_id ? Number(v.assignee_id) : null, due: v.due || s.default_due }]
}))

