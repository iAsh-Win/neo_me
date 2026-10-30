const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export function fmtDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`
}

export function shortDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getDate()} ${MONTHS[d.getMonth()]}`
}

export function ago(iso) {
  if (!iso) return ''
  const mins = Math.max(0, Math.round((Date.now() - new Date(iso)) / 60000))
  if (mins < 2) return 'Just now'
  if (mins < 60) return `${mins} min ago`
  const hrs = Math.round(mins / 60)
  if (hrs < 24) return `${hrs} hr ago`
  const days = Math.round(hrs / 24)
  if (days < 30) return days === 1 ? 'Yesterday' : `${days} days ago`
  return fmtDate(iso)
}

export const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`

/** "2 days late" / "Due today" / "3 days left" – null when the project is not waiting on anyone */
export function dueInfo(p) {
  if (p.due_days == null) return null
  if (p.due_days < 0) return { tone: 'red', text: `${plural(-p.due_days, 'day')} late` }
  if (p.due_days === 0) return { tone: 'amber', text: 'Due today' }
  return { tone: 'gray', text: `${plural(p.due_days, 'day')} left` }
}

export function money(v) {
  if (v == null || v === '') return '—'
  return 'A$' + Number(v).toLocaleString('en-AU', { maximumFractionDigits: 0 })
}

export function fileSize(n) {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${Math.round(n / 1024)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

export const initials = (name = '') =>
  name
    .replace(/^Dr\.?\s+/i, '')
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0])
    .join('')
    .toUpperCase()

const AVATARS = ['#6D4AFF', '#2563EB', '#0E9AA7', '#16A34A', '#D97706', '#DB2777', '#7C3AED', '#4F46E5']
export function avatarColor(name = '') {
  let h = 0
  for (const c of name) h = (h * 31 + c.charCodeAt(0)) >>> 0
  return AVATARS[h % AVATARS.length]
}

export const STATUS = {
  active: { label: 'In progress', tone: 'blue' },
  on_hold: { label: 'On hold', tone: 'amber' },
  rejected: { label: 'Rejected', tone: 'red' },
  cancelled: { label: 'Cancelled', tone: 'gray' },
  completed: { label: 'Completed', tone: 'green' },
}

export const shortName = (n = '') => { const p = n.replace(/^Dr\.?\s+/i, '').split(/\s+/); return p.length > 1 ? `${p[0]} ${p[1][0]}.` : n }

export const ORG_TONE = { 'Neo Health (OTC)': 'brand', 'Neo India Lifeline': 'teal', Manufacturer: 'orange', Office: 'gray' }
