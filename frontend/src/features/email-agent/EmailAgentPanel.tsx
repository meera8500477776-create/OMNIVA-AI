import React from "react";
export type EmailRow = { id: string; sender: string; subject: string; category: string; summary: string; unread: boolean };
export function EmailAgentPanel({ demo = true, rows = [] }: { demo?: boolean; rows?: EmailRow[] }) {
  return <section aria-label="Email Agent" className="omniva-email-agent">
    <header><div><h2>Email Agent</h2><p>{demo ? "Demo inbox · fictional messages" : "Connected inbox"}</p></div><button type="button">Connect Gmail</button></header>
    <nav aria-label="Inbox filters"><button type="button">All</button><button type="button">Unread</button><button type="button">Urgent</button><button type="button">Promotions</button></nav>
    <ul>{rows.map(row => <li key={row.id}><strong>{row.subject}</strong><span>{row.sender} · {row.category}</span><p>{row.summary}</p><button type="button">Review and draft</button></li>)}</ul>
    <p>Sending requires an explicit approval for each message.</p>
  </section>;
}
