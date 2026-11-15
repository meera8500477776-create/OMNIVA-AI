import { api } from './lib/api'
import { CareCompanionPanel } from './features/care-companion/CareCompanionPanel'
import { EmailAgentPanel } from './features/email-agent/EmailAgentPanel'
import { AutopilotDashboard, type AutopilotApi } from './features/autopilot/AutopilotDashboard'
import './features/autopilot/autopilot.css'

const autopilotApi: AutopilotApi = {
  plan: request => api('/autopilot/plans', { method: 'POST', body: JSON.stringify({ request }) }),
  get: id => api(`/autopilot/workflows/${id}`),
  createWorkflow: planId => api('/autopilot/workflows', { method: 'POST', body: JSON.stringify({ plan_id: planId }) }),
  start: id => api(`/autopilot/workflows/${id}/start`, { method: 'POST' }),
  pause: id => api(`/autopilot/workflows/${id}/pause`, { method: 'POST' }),
  resume: id => api(`/autopilot/workflows/${id}/resume`, { method: 'POST' }),
  cancel: id => api(`/autopilot/workflows/${id}/cancel`, { method: 'POST' }),
  history: () => api('/autopilot/history'),
  approvals: () => api('/autopilot/approvals'),
  consentMemory: async consented => { await api('/autopilot/memory/consent', { method: 'POST', body: JSON.stringify({ consented }) }) },
  addMemory: async (content, provenance) => { await api('/autopilot/memory', { method: 'POST', body: JSON.stringify({ content, provenance }) }) },
  decideApproval: async (item, confirmed) => api(`/autopilot/approvals/${item.id}/${confirmed ? 'approve' : 'deny'}`, { method: 'POST', body: JSON.stringify({ confirmed, plan_hash: item.plan_hash, action_hash: item.action_hash, action_text: item.action_text }) }),
  emergencyStop: async () => { await api('/autopilot/emergency-stop', { method: 'POST' }) },
  memories: query => api(`/autopilot/memory${query ? `?query=${encodeURIComponent(query)}` : ''}`),
  deleteMemory: async id => { await api(`/autopilot/memory/${id}`, { method: 'DELETE' }) },
  browserEvidence: id => api(`/autopilot/workflows/${id}/browser-evidence`),
}

export function CareCompanionPage() { return <div className="content-page"><CareCompanionPanel /></div> }
export function EmailAgentPage() { return <div className="content-page"><EmailAgentPanel /></div> }
export function AutopilotPage() { return <div className="content-page"><AutopilotDashboard api={autopilotApi} mode="demo" /></div> }
