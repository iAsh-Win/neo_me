import { useMemo, useState } from 'react'
import { useApp } from '../ctx'
import FlowMap from '../FlowMap'

export default function ProcessMap() {
  const { def, user } = useApp()
  const [type, setType] = useState('development')
  const [mine, setMine] = useState(user.role !== 'admin')
  const byKey = useMemo(() => Object.fromEntries(def.steps.map((s) => [s.key, s])), [def])
  const roleBy = useMemo(() => Object.fromEntries(def.roles.map((r) => [r.key, r])), [def])

  const steps = useMemo(() => def.steps
    .filter((s) => !s.only || s.only === type)
    .map((s) => ({
      ...s,
      state: 'upcoming',
      owners: s.roles.map((r) => ({ role: r, short: roleBy[r].short, label: roleBy[r].label })),
      coordinator: s.coordinator ? roleBy[s.coordinator].short : null,
      coordinatorRole: s.coordinator,
      options: s.options.map((o) => ({ ...o, to_name: o.to ? byKey[o.to].name : o.key === 'approve' && s.key === 'agreement_decision' ? (type === 'development' ? byKey.cdmo.name : byKey.reg_review.name) : null })),
    })), [def, type, byKey, roleBy])

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Process map</h1>
          <p className="muted">The company flow chart, step by step.</p>
        </div>
        <div className="head-actions">
          <div className="seg" role="tablist">
            <button role="tab" aria-selected={type === 'development'} className={type === 'development' ? 'on' : ''} onClick={() => setType('development')}>Development</button>
            <button role="tab" aria-selected={type === 'in_licence'} className={type === 'in_licence' ? 'on' : ''} onClick={() => setType('in_licence')}>In-Licence</button>
          </div>
        </div>
      </div>
      {user.role !== 'admin' && (
        <label className="switch">
          <input type="checkbox" checked={mine} onChange={(e) => setMine(e.target.checked)} />
          <span />Highlight my steps
        </label>
      )}
      <FlowMap steps={steps} mode="guide" highlightRole={mine ? user.role : null} />
    </div>
  )
}
