import { useEffect, useState } from 'react'
import { api, appMode } from '../../lib/api'

type EmailRow = { id: string; sender: string; subject: string; category: string; summary: string; unread: boolean }
type Draft = { draft_id: string; body: string; subject: string; }
export function EmailAgentPanel() {
  const [rows, setRows] = useState<EmailRow[]>([])
  const [draft, setDraft] = useState<Draft | null>(null)
  const [approval, setApproval] = useState('')
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  async function load() { try { const r = await api<{items: EmailRow[]}>('/features/email-agent/inbox'); setRows(r.items) } catch (e) { setError(e instanceof Error ? e.message : 'Inbox could not load.') } }
  useEffect(() => { const timer = window.setTimeout(() => void load(), 0); return () => window.clearTimeout(timer) }, [])
  async function makeDraft(id: string) {
    setError(''); setNotice('');
    try { const r = await api<Draft>('/features/email-agent/drafts', { method: 'POST', body: JSON.stringify({ email_id: id, tone: 'professional' }) }); setDraft(r); setApproval('') }
    catch (e) { setError(e instanceof Error ? e.message : 'Draft could not be created.') }
  }
  async function approve() {
    if (!draft) return
    try { const r = await api<{approval: string}>('/features/email-agent/approvals', { method: 'POST', body: JSON.stringify({ draft_id: draft.draft_id }) }); setApproval(r.approval); setNotice('Review the draft and explicitly approve sending below.') }
    catch (e) { setError(e instanceof Error ? e.message : 'Approval request failed.') }
  }
  async function send() {
    if (!approval) return
    try { const r = await api<{sent: boolean; status: string}>('/features/email-agent/send', { method: 'POST', headers: { 'Idempotency-Key': crypto.randomUUID() }, body: JSON.stringify({ approval }) }); setNotice(r.sent ? 'Message sent.' : 'Demo send simulated. No email was sent.'); setApproval('') }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not send.') }
  }
  return <section aria-label="Email Agent" className="omniva-email-agent">
    <header><h1>Email Agent</h1><p>{appMode === 'demo' ? 'Fictional demo inbox · nothing is sent to an external email account.' : 'Connected inbox'}</p></header>
    <button type="button" onClick={() => void load()}>Refresh inbox</button>
    <ul>{rows.map(row => <li key={row.id}><strong>{row.subject}</strong><span>{row.sender} · {row.category}</span><p>{row.summary}</p><button type="button" onClick={() => void makeDraft(row.id)}>Review and draft</button></li>)}</ul>
    {draft && <section aria-label="Draft review"><h2>Review draft</h2><p><strong>{draft.subject}</strong></p><pre>{draft.body}</pre><button onClick={() => void approve()}>Request send approval</button>{approval && <button onClick={() => void send()}>Approve simulated send</button>}</section>}
    {notice && <p role="status">{notice}</p>}{error && <p role="alert">{error}</p>}
    <p>Each send requires explicit approval. Demo mode never sends email.</p>
  </section>
}
