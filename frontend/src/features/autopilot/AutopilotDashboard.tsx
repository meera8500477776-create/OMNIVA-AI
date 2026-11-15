import { useEffect, useState } from 'react'

type Risk = 'low' | 'medium' | 'high'
type Step = { id: string; description: string; tool: string; expected_output: string; dependencies: string[]; risk: Risk; approval_required: boolean; status?: string; result?: Record<string, unknown>; approval_id?: string | null }
type Plan = { id: string; user_id: string; request: string; demo: boolean; steps: Step[] }
type Approval = { id: string; user_id: string; workflow_id: string; step_id: string; plan_hash: string; action_hash: string; action_text: string; status: string; expires_at: string }
type Workflow = { workflow_id: string; plan: Plan; plan_hash: string; status: string; steps: Step[]; events: Array<{ sequence: number; type: string; step_id?: string; message: string; data?: Record<string, unknown> }>; demo: boolean }
export type AutopilotApi = {
  plan(request: string): Promise<Plan>
  get(id: string): Promise<Workflow>
  createWorkflow(planId: string): Promise<Workflow>
  start(id: string): Promise<Workflow>
  pause(id: string): Promise<Workflow>
  resume(id: string): Promise<Workflow>
  cancel(id: string): Promise<Workflow>
  history(): Promise<Workflow[]>
  approvals(): Promise<Approval[]>
  consentMemory(consented: boolean): Promise<void>
  addMemory(content: string, provenance: string): Promise<void>
  decideApproval(approval: Approval, confirmed: boolean): Promise<Workflow>
  emergencyStop(): Promise<void>
  memories(query?: string): Promise<Array<{ id: string; content: string; provenance: string; expires_at: string }>>
  deleteMemory(id: string): Promise<void>
  browserEvidence?(workflowId: string): Promise<Array<{ title: string; text: string; evidence_id: string; demo: boolean }>>
}
const EXAMPLE = 'Find three example AI internships, compare them, draft an application email and schedule a reminder.'
const panes = ['Overview', 'New task', 'Approvals', 'Browser activity', 'History', 'Memory', 'Settings'] as const
export function AutopilotDashboard({ api, mode = 'demo' }: { api: AutopilotApi; mode?: 'demo' | 'live' }) {
  const [pane, setPane] = useState<(typeof panes)[number]>('Overview')
  const [request, setRequest] = useState(EXAMPLE)
  const [plan, setPlan] = useState<Plan | null>(null)
  const [workflow, setWorkflow] = useState<Workflow | null>(null)
  const [approvals, setApprovals] = useState<Approval[]>([])
  const [history, setHistory] = useState<Workflow[]>([])
  const [memories, setMemories] = useState<Array<{ id: string; content: string; provenance: string; expires_at: string }>>([])
  const [evidence, setEvidence] = useState<Array<{ title: string; text: string; evidence_id: string; demo: boolean }>>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [memoryConsent, setMemoryConsent] = useState(false)
  const [memoryText, setMemoryText] = useState('')
  const activeWorkflowId = workflow?.workflow_id
  const activeWorkflowStatus = workflow?.status
  useEffect(() => {
    if (!activeWorkflowId || !["running", "waiting_approval"].includes(activeWorkflowStatus ?? "")) return
    const timer = window.setInterval(() => {
      void api.get(activeWorkflowId).then(setWorkflow).catch(() => undefined)
    }, 2000)
    return () => window.clearInterval(timer)
  }, [api, activeWorkflowId, activeWorkflowStatus])
  const act = async (fn: () => Promise<void>) => { setLoading(true); setError(''); setMessage(''); try { await fn() } catch (e) { setError(e instanceof Error ? e.message : 'Request failed') } finally { setLoading(false) } }
  const refreshApprovals = () => act(async () => setApprovals(await api.approvals()))
  const makePlan = () => act(async () => { const next = await api.plan(request); setPlan(next); setWorkflow(null); setPane('New task') })
  const create = () => act(async () => { if (!plan) return; const run = await api.createWorkflow(plan.id); setWorkflow(run); setMessage('Plan saved. Review approvals before any consequential action starts.') })
  const run = (method: (id: string) => Promise<Workflow>) => act(async () => { if (!workflow) return; setWorkflow(await method(workflow.workflow_id)) })
  const loadHistory = () => act(async () => { setHistory(await api.history()); setPane('History') })
  const loadMemories = () => act(async () => { setMemories(await api.memories()); setPane('Memory') })
  const loadEvidence = () => act(async () => { if (workflow && api.browserEvidence) setEvidence(await api.browserEvidence(workflow.workflow_id)); setPane('Browser activity') })
  const decide = (item: Approval, confirmed: boolean) => act(async () => { setWorkflow(await api.decideApproval(item, confirmed)); setApprovals(await api.approvals()); setMessage(confirmed ? 'Approval recorded for this exact action.' : 'Action denied; it will not be executed.') })
  return <section className="autopilot-page">
    <header className="autopilot-header"><div><p className="eyebrow">OMNIVA AI · FEATURE 8</p><h1>Autopilot</h1><p>Turn a request into a reviewable workflow with you in control.</p></div><span className={`badge badge-${mode === 'demo' ? 'amber' : 'blue'}`}>{mode === 'demo' ? 'DEMO' : 'LIVE'}</span></header>
    <nav className="autopilot-tabs" aria-label="Autopilot sections">{panes.map(item => <button key={item} type="button" aria-current={pane === item ? 'page' : undefined} onClick={() => { setPane(item); if (item === 'Approvals') void refreshApprovals(); if (item === 'History') void loadHistory(); if (item === 'Memory') void loadMemories(); if (item === 'Browser activity') void loadEvidence() }}>{item}</button>)}</nav>
    {error && <div className="error-state" role="alert">{error}</div>}{message && <div className="autopilot-notice" role="status">{message}</div>}
    {pane === 'Overview' && <section className="autopilot-grid"><article className="card"><p className="eyebrow">YOUR AUTOMATION SPACE</p><h2>Plan first. Approve each consequential step.</h2><p>Autopilot uses allowlisted tools. It does not execute generated code or grant approvals on its own.</p><button className="button button-primary" type="button" onClick={() => setPane('New task')}>Create a task</button></article><article className="card"><h2>Current workflow</h2>{workflow ? <WorkflowView workflow={workflow} /> : <p>No workflow selected.</p>}</article><article className="card"><h2>Quick controls</h2><button className="button button-danger" type="button" disabled={loading} onClick={() => void act(async () => { await api.emergencyStop(); setWorkflow(null); setMessage('Emergency stop requested. No new Autopilot actions will start.') })}>Emergency stop</button><button className="button button-secondary" type="button" disabled={!workflow || loading} onClick={() => void run(api.cancel)}>Cancel current workflow</button></article></section>}
    {pane === 'New task' && <section className="card autopilot-composer"><h2>What would you like Autopilot to do?</h2><label htmlFor="autopilot-task">Task request</label><textarea id="autopilot-task" value={request} maxLength={2000} onChange={e => setRequest(e.target.value)} rows={4} /><div className="autopilot-actions"><button className="button button-primary" disabled={loading || request.trim().length < 3} onClick={() => void makePlan()}>{loading ? 'Planning…' : 'Generate plan'}</button>{plan && <button className="button button-secondary" disabled={loading} onClick={() => void create()}>Create workflow</button>}</div>{plan && <><p className="badge badge-amber">{plan.demo ? 'DEMO · fixture-backed' : 'LIVE'}</p><h3>Review the proposed plan</h3><PlanView plan={plan} />{workflow && <><h3>Execution status: {workflow.status}</h3><WorkflowView workflow={workflow} /><WorkflowControls workflow={workflow} loading={loading} start={() => void run(api.start)} pause={() => void run(api.pause)} resume={() => void run(api.resume)} cancel={() => void run(api.cancel)} /></>}</>}</section>}
    {pane === 'Approvals' && <section className="card"><h2>Approval center</h2><p>Approvals are scoped to your account, a plan hash, a single action and target, and expire automatically.</p>{approvals.length ? approvals.map(item => <article className="autopilot-approval" key={item.id}><h3>{item.action_text}</h3><p>Workflow {item.workflow_id} · step {item.step_id} · expires {new Date(item.expires_at).toLocaleString()}</p><button className="button button-primary" disabled={loading} onClick={() => void decide(item, true)}>Approve this action</button><button className="button button-secondary" disabled={loading} onClick={() => void decide(item, false)}>Deny</button></article>) : <p>No pending approvals.</p>}</section>}
    {pane === 'Browser activity' && <section className="card"><h2>Browser activity and evidence</h2><p>Pages are untrusted input. The demo uses local fictional fixtures; live browsing requires an allowlisted provider.</p>{evidence.length ? evidence.map(item => <article key={item.evidence_id}><h3>{item.title}</h3><p>{item.text}</p><small>{item.evidence_id} · {item.demo ? 'DEMO' : 'LIVE'}</small></article>) : <p>No browser evidence for this workflow.</p>}</section>}
    {pane === 'History' && <section className="card"><h2>Workflow history</h2>{history.map(item => <article className="autopilot-history" key={item.workflow_id}><h3>{item.plan.request}</h3><p>{item.status} · {item.demo ? 'DEMO' : 'LIVE'}</p><WorkflowView workflow={item} /></article>)}</section>}
    {pane === 'Memory' && <section className="card"><h2>Personal memory</h2><p>Memory starts disabled. Only add information after explicit consent; credentials and payment card numbers are rejected.</p><label><input type="checkbox" checked={memoryConsent} onChange={e => { const enabled=e.target.checked; setMemoryConsent(enabled); void act(async () => api.consentMemory(enabled)) }} /> I consent to optional personal memory storage</label><label htmlFor="autopilot-memory">Memory to save</label><textarea id="autopilot-memory" value={memoryText} onChange={e => setMemoryText(e.target.value)} maxLength={1000} /><button className="button button-primary" disabled={!memoryConsent || !memoryText.trim() || loading} onClick={() => void act(async () => { await api.addMemory(memoryText, "user-provided"); setMemoryText(''); setMemories(await api.memories()) })}>Save memory</button>{memories.map(item => <article key={item.id}><p>{item.content}</p><small>{item.provenance} · expires {new Date(item.expires_at).toLocaleDateString()}</small><button className="button button-secondary" onClick={() => void act(async () => { await api.deleteMemory(item.id); setMemories(await api.memories()) })}>Delete memory</button></article>)}</section>}
    {pane === 'Settings' && <section className="card"><h2>Automation settings</h2><p>Demo mode uses fictional data and does not submit email, calendar or application actions.</p><p>Live integrations remain unavailable until explicitly configured in the shared backend.</p><button className="button button-danger" disabled={loading} onClick={() => void act(async () => { await api.emergencyStop(); setMessage('Emergency stop is active.') })}>Emergency stop all Autopilot actions</button></section>}
  </section>
}
function PlanView({ plan }: { plan: Plan }) { return <ol className="autopilot-plan">{plan.steps.map(step => <li key={step.id}><strong>{step.description}</strong><span>{step.tool} · {step.risk} risk{step.approval_required ? ' · approval required' : ''}</span><small>Depends on: {step.dependencies.join(', ') || 'none'} · Expected: {step.expected_output}</small></li>)}</ol> }
function WorkflowView({ workflow }: { workflow: Workflow }) { return <ol className="autopilot-timeline">{workflow.steps.map(step => <li key={step.id} data-status={step.status || 'pending'}><strong>{step.description}</strong><span>{step.status || 'pending'}{step.approval_required ? ' · approval required' : ''}</span>{step.result && <pre>{JSON.stringify(step.result, null, 2)}</pre>}</li>)}</ol> }
function WorkflowControls({ workflow, loading, start, pause, resume, cancel }: { workflow: Workflow; loading: boolean; start: () => void; pause: () => void; resume: () => void; cancel: () => void }) { return <div className="autopilot-actions"><button className="button button-primary" disabled={loading || ['completed', 'cancelled'].includes(workflow.status)} onClick={workflow.status === 'paused' ? resume : start}>{workflow.status === 'paused' ? 'Resume' : 'Start / continue'}</button><button className="button button-secondary" disabled={loading || workflow.status !== 'running'} onClick={pause}>Pause</button><button className="button button-danger" disabled={loading || ['completed', 'cancelled'].includes(workflow.status)} onClick={cancel}>Cancel</button></div> }
