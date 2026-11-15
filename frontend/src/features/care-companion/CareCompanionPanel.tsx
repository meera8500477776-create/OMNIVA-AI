import React from "react";
export const personas = ["mother-like", "father-like", "best-friend", "sibling", "girlfriend", "boyfriend"] as const;
export function CareCompanionPanel({ demo = true }: { demo?: boolean }) {
  return <section aria-label="AI Care Companion" className="omniva-care-companion">
    <header><h2>AI Care Companion</h2><p>{demo ? "Offline demo · no microphone or network used" : "AI companion · voice availability depends on configured providers"}</p></header>
    <label>Choose a companion <select defaultValue="best-friend">{personas.map(p => <option key={p}>{p}</option>)}</select></label>
    <p>Every persona is an AI companion, not a real person. Stay connected with people you trust.</p>
    <button type="button">Start in-app conversation</button><button type="button">End conversation</button>
    <label><input type="checkbox" /> Enable scheduled check-ins (opt-in)</label>
    <p>Calls and check-ins are available only through the active app session in this release.</p>
  </section>;
}
