import { useEffect, useState } from 'react'
import { api, appMode } from '../../lib/api'

type Reminder = { id: string; title: string; body: string; reminder_type: string; scheduled_at: string; status: string; acknowledged_at?: string | null }
const personas = ['mother-like', 'father-like', 'best-friend', 'sibling', 'girlfriend', 'boyfriend'] as const

export function CareCompanionPanel() {
  const [persona, setPersona] = useState<string>('best-friend')
  const [sessionId, setSessionId] = useState('')
  const [sessionDemo, setSessionDemo] = useState(appMode === 'demo')
  const [text, setText] = useState('')
  const [answer, setAnswer] = useState('')
  const [title, setTitle] = useState('')
  const [when, setWhen] = useState('')
  const [consent, setConsent] = useState(false)
  const [sessionConsent, setSessionConsent] = useState(false)
  const [reminderType, setReminderType] = useState<'deadline' | 'call_prompt'>('deadline')
  const [incomingPrompt, setIncomingPrompt] = useState<Reminder | null>(null)
  const [reminders, setReminders] = useState<Reminder[]>([])
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  async function refresh() {
    try {
      const r = await api<{ items: Reminder[] }>('/features/care-companion/reminders')
      setReminders(r.items)
      const incoming = r.items.find(x => x.reminder_type === 'call_prompt' && x.status === 'fired' && !x.acknowledged_at)
      if (incoming && document.visibilityState === 'visible') setIncomingPrompt(incoming)
    } catch { /* Keep the current view usable if a poll briefly fails. */ }
  }
  useEffect(() => { const initial = window.setTimeout(() => void refresh(), 0); const timer = window.setInterval(() => void refresh(), 15000); return () => { window.clearTimeout(initial); window.clearInterval(timer) } }, [])
  async function start(promptId?: string) {
    setError('');
    if (!promptId && !sessionConsent) { setError('Please consent before starting an AI companion session.'); return }
    try { const r = await api<{ session_id: string; demo: boolean }>('/features/care-companion/sessions', { method: 'POST', body: JSON.stringify({ persona, locale: 'en', consent: true }) }); setSessionId(r.session_id); setSessionDemo(r.demo); setAnswer('Conversation started. This is an AI companion, not a real person.'); if (promptId) await acknowledge(promptId) }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not start session.') }
    if (promptId) await acknowledge(promptId)
  }
  async function send() {
    if (!sessionId || !text.trim()) return
    try { const r = await api<{ answer: string; demo: boolean }>(`/features/care-companion/sessions/${sessionId}/turns`, { method: 'POST', body: JSON.stringify({ text }) }); setAnswer(r.answer); setSessionDemo(r.demo); setText('') }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not send message.') }
  }
  async function schedule(e: React.FormEvent) {
    e.preventDefault(); setError('');
    if (!consent) { setError('Please give consent before scheduling reminders.'); return }
    try {
      const key = crypto.randomUUID()
      await api('/features/care-companion/reminders', { method: 'POST', headers: { 'Idempotency-Key': key }, body: JSON.stringify({ title, body: '', reminder_type: reminderType, scheduled_at: new Date(when).toISOString(), timezone_name: Intl.DateTimeFormat().resolvedOptions().timeZone, quiet_start: '22:00', quiet_end: '08:00', consent }) })
      setTitle(''); setWhen(''); setNotice(reminderType === 'deadline' ? 'Deadline reminder saved.' : 'In-app check-in saved.'); await refresh()
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not save reminder.') }
  }
  async function acknowledge(id: string) { await api(`/features/care-companion/reminders/${id}/acknowledge`, { method: 'POST' }); setIncomingPrompt(current => current?.id === id ? null : current); setNotice('Check-in acknowledged.'); await refresh() }
  return <section aria-label="AI Care Companion" className="omniva-care-companion">
    <header><h1>AI Care Companion</h1><p>{sessionId ? sessionDemo ? 'DEMO COMPANION' : 'GEMINI COMPANION · TEXT' : appMode === 'demo' ? 'Integrated demo companion' : 'Gemini conversational service'} · deadlines are stored in the configured database.</p></header>
    <p>Every persona is an AI companion, not a real person. Stay connected with people you trust.</p>
    <label>Choose a companion <select value={persona} onChange={e => setPersona(e.target.value)}>{personas.map(p => <option key={p}>{p}</option>)}</select></label>
    <label><input type="checkbox" checked={sessionConsent} onChange={e => setSessionConsent(e.target.checked)} /> I consent to an AI companion conversation.</label><button type="button" onClick={() => void start()} disabled={!sessionConsent}>Start in-app conversation</button>
    {sessionId && <><label htmlFor="care-message">Message the companion</label><input id="care-message" value={text} onChange={e => setText(e.target.value)} /><button type="button" onClick={() => void send()}>Send</button></>}
    {answer && <p role="status">{answer}</p>}
    <h2>Deadline reminders and check-ins</h2><p>Consent is required. Quiet hours are 10 pm–8 am in your current timezone.</p>
    <form onSubmit={e => void schedule(e)}><label htmlFor="reminder-type">Reminder type</label><select id="reminder-type" value={reminderType} onChange={e => setReminderType(e.target.value as 'deadline' | 'call_prompt')}><option value="deadline">Deadline reminder</option><option value="call_prompt">In-app check-in prompt</option></select><label htmlFor="deadline-title">What should we remind you about?</label><input id="deadline-title" required value={title} onChange={e => setTitle(e.target.value)} /><label htmlFor="deadline-when">When</label><input id="deadline-when" required type="datetime-local" value={when} onChange={e => setWhen(e.target.value)} /><label><input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} /> I consent to storing this reminder and showing a check-in while Omniva is open.</label><button type="submit">Save reminder</button></form>
    {incomingPrompt && <div role="alert"><p>Incoming AI companion check-in: {incomingPrompt.title}</p><button type="button" onClick={() => void start(incomingPrompt.id)}>Start check-in</button><button type="button" onClick={() => void acknowledge(incomingPrompt.id)}>Dismiss</button></div>}
    {notice && <p role="status">{notice}</p>}{error && <p role="alert">{error}</p>}
    <ul aria-label="Saved deadlines">{reminders.map(r => <li key={r.id}><strong>{r.title}</strong> · {new Date(r.scheduled_at).toLocaleString()} · {r.status}{r.status === 'fired' && !r.acknowledged_at && <button onClick={() => void acknowledge(r.id)}>Acknowledge check-in</button>}</li>)}</ul>
    <p>While this page is open, it checks for incoming prompts. Closed-browser notifications are unavailable until push delivery is configured; a closed browser cannot receive a live in-app call.</p>
  </section>
}
