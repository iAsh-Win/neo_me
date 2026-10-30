import { useState } from 'react'
import {
  ArrowRight, Ban, BellRing, Check, CheckSquare, Clock, CornerUpLeft, FastForward, FilePlus, FileX, MessageSquare, Pause,
  Play, Plus, Route, X, Pencil, Star, UserRoundCog,
} from 'lucide-react'
import { Avatar, DocChip } from './ui'
import { ago, fmtDate, shortDate } from './format'

const ICON = {
  done: [Check, 'ok'], approve: [Check, 'ok'], signoff: [Check, 'ok'], sendback: [CornerUpLeft, 'warn'], hold: [Pause, 'warn'],
  reject: [X, 'bad'], resume: [Play, 'ok'], cancel: [Ban, 'bad'], moved: [Route, 'info'], fasttrack: [FastForward, 'info'],
  nudge: [BellRing, 'info'], comment: [MessageSquare, 'info'], task_new: [Plus, 'info'], task_done: [CheckSquare, 'ok'],
  task_cancel: [X, 'warn'], ext_ask: [Clock, 'warn'], ext_yes: [Check, 'ok'], ext_no: [X, 'bad'], due: [Pencil, 'info'],
  doc_added: [FilePlus, 'info'], doc_removed: [FileX, 'warn'], doc_key: [Star, 'info'], doc_unkey: [Star, 'info'],
  assign: [UserRoundCog, 'info'],
}

function Line({ e }) {
  const who = <b>{e.user?.name}</b>
  const role = e.user ? <small className="role">({e.user.short})</small> : null
  const step = e.step_name ? <b className="st">{e.step_name}</b> : null
  switch (e.action) {
    case 'done': return <>{who} {role} completed {step}</>
    case 'approve': return <>{who} {role} approved {step}</>
    case 'signoff': return <>{who} {role} signed {step}</>
    case 'sendback': return <>{who} {role} sent {step} back{e.target_name && <> to <b className="st">{e.target_name}</b></>}</>
    case 'hold': return <>{who} {role} put the project on hold{step && <> at {step}</>}</>
    case 'reject': return <>{who} {role} rejected the project at {step}</>
    case 'resume': return <>{who} {role} restarted the project</>
    case 'cancel': return <>{who} {role} cancelled the project</>
    case 'moved': return <>{who} {role} moved the project to <b className="st">{e.target_name}</b></>
    case 'fasttrack': return <>{who} {role} changed Fast track</>
    case 'nudge': return <>{who} {role} sent a reminder{step && <> for {step}</>}</>
    case 'comment': return <>{who} {role} wrote a note</>
    case 'task_new': return <>{who} {role} gave a task</>
    case 'task_done': return <>{who} {role} finished a task</>
    case 'task_cancel': return <>{who} {role} cancelled a task</>
    case 'ext_ask': return <>{who} {role} asked for more time on <b className="st">{e.label}</b></>
    case 'ext_yes': return <>{who} {role} approved more time on <b className="st">{e.label}</b></>
    case 'ext_no': return <>{who} {role} declined more time on <b className="st">{e.label}</b></>
    case 'due': return <>{who} {role} changed the date of {step}</>
    case 'doc_added': return <>{who} {role} {e.reuse ? 'used' : 'added'} a document{e.task ? <> on task <b className="st">{e.task}</b></> : step && <> for {step}</>}</>
    case 'doc_key': return <>{who} {role} marked a key document</>
    case 'doc_unkey': return <>{who} {role} unmarked a key document</>
    case 'assign': return <>{who} {role} changed who has {step}</>
    case 'doc_removed': return <>{who} {role} removed a document</>
    default: return <>{who} {role} {e.action}</>
  }
}

export function HistoryItem({ e }) {
  const [Icon, tone] = ICON[e.action] || [Clock, 'info']
  const isNote = e.kind === 'comment'
  return (
    <li className={`h-item ${tone}`}>
      <span className="h-dot"><Icon size={14} strokeWidth={2.6} /></span>
      <div className="h-body">
        <p className="h-line"><Line e={e} /> <small title={fmtDate(e.at)}>{ago(e.at)}</small></p>
        {e.to && !['comment', 'doc_added', 'doc_removed', 'nudge', 'doc_key', 'doc_unkey'].includes(e.action) && (
          <p className="h-to"><ArrowRight size={13} /> {['ext_ask', 'task_new'].includes(e.action) ? 'Went to' : 'Goes to'} {e.to}</p>
        )}
        {e.old && e.new && <p className="h-to"><Clock size={13} /> {shortDate(e.old)} → <b>{shortDate(e.new)}</b></p>}
        {e.data?.length > 0 && (
          <div className="h-data">{e.data.map((d) => <span key={d.label}>{d.label}: <b>{d.unit === 'A$' ? `A$ ${Number(d.value).toLocaleString('en-AU')}` : `${d.value}${d.unit ? ` ${d.unit}` : ''}`}</b></span>)}</div>
        )}
        {e.checks?.length > 0 && <div className="h-checks"><Check size={13} /> {e.checks.join(' · ')}</div>}
        {e.docs?.length > 0 && (
          <div className="h-docs">{e.docs.map((d) => <DocChip key={d.id} compact doc={d} />)}</div>
        )}
        {e.doc && <div className="h-docs"><DocChip compact doc={e.doc} />{e.doc_label && <small>{e.doc_label}</small>}</div>}
        {e.kind === 'comment' && e.note ? <div className="bubble">{e.note}</div> : e.note && !['doc_added', 'doc_removed', 'task_new', 'doc_key', 'doc_unkey'].includes(e.action) ? <q>{e.note}</q> : null}
        {e.action === 'task_new' && e.note && <q>{e.note}</q>}
      </div>
    </li>
  )
}

const FILTERS = [
  ['key', 'Key moments'], ['all', 'Everything'], ['step', 'Steps'], ['comment', 'Notes'], ['doc', 'Files'], ['task', 'Tasks'], ['request', 'Requests'],
]

export function HistoryList({ events, filterable = true, empty = 'Nothing yet.', start = 'all' }) {
  const [f, setF] = useState(start)
  const list = [...events].reverse().filter((e) => f === 'all' || (f === 'key' ? e.key : e.kind === f || (f === 'step' && e.kind === 'system')))
  return (
    <div className="history-wrap">
      {filterable && (
        <div className="chips">
          {FILTERS.map(([k, label]) => <button key={k} className={`chip ${f === k ? 'on' : ''}`} onClick={() => setF(k)}>{label}</button>)}
        </div>
      )}
      {f === 'key' && <p className="muted small">Approvals, send-backs, holds and date changes. Choose “Everything” for every hand-over, note and file.</p>}
      {list.length === 0 && <p className="muted center">{empty}</p>}
      <ul className="h-list">{list.map((e) => <HistoryItem key={e.id} e={e} />)}</ul>
    </div>
  )
}

export function Mini({ e }) {
  return <HistoryItem e={e} />
}

export { Avatar }
