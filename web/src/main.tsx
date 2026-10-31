import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

type Message = { role: 'user' | 'system'; text: string };
type Tab = 'Chat' | 'Agents' | 'Workflows' | 'Benchmarks';
const tabs: Tab[] = ['Chat', 'Agents', 'Workflows', 'Benchmarks'];
const initial: Message[] = [{role:'system',text:'Daeloryn Console is in preview mode. AI provider execution is not connected. No prompts are sent to a model.'}];

function App() {
  const [tab,setTab] = useState<Tab>('Chat');
  const [messages,setMessages] = useState<Message[]>(initial);
  const [draft,setDraft] = useState('');
  const [agent,setAgent] = useState('Auto-select (preview)');
  function submit(event: React.FormEvent) {
    event.preventDefault();
    const text = draft.trim();
    if (!text) return;
    setMessages(previous => [...previous,{role:'user',text},{role:'system',text:'Not executed: no live provider session is configured. Your prompt remains in this browser tab.'}]);
    setDraft('');
  }
  return <div className="shell">
    <aside className="sidebar">
      <div className="brand"><span className="mark">◇</span> Daeloryn <small>ENGINEERING CONSOLE</small></div>
      <nav aria-label="Main navigation">{tabs.map(t=><button key={t} className={tab===t?'active':''} onClick={()=>setTab(t)}>{t}</button>)}</nav>
      <div className="sidebar-foot">Local preview · No AI API connected</div>
    </aside>
    <main>
      <header><div><span className="eyebrow">WORKSPACE / LOCAL</span><h1>{tab}</h1></div><span className="status">● Preview mode</span></header>
      {tab==='Chat' ? <section className="chat">
        <div className="chat-head"><div><h2>Engineering assistant</h2><p>Plan tasks, review code, and coordinate agents once a verified execution backend is connected.</p></div>
        <label>Agent<select value={agent} onChange={e=>setAgent(e.target.value)}><option>Auto-select (preview)</option><option>Java Reviewer (preview)</option><option>Spring Expert (preview)</option><option>Security Reviewer (preview)</option></select></label></div>
        <div className="messages" aria-live="polite">{messages.map((m,i)=><article key={i} className={'message '+m.role}><span>{m.role==='user'?'You':'Daeloryn · Status'}</span><p>{m.text}</p></article>)}</div>
        <form onSubmit={submit} className="composer"><label htmlFor="prompt">Your task</label><textarea id="prompt" value={draft} onChange={e=>setDraft(e.target.value)} placeholder="e.g. Review a Java service for concurrency and security risks…" rows={3}/><div className="compose-bottom"><small>Local UI only · No execution, files or credentials transmitted</small><button type="submit" disabled={!draft.trim()}>Add to chat ↗</button></div></form>
      </section> : <section className="panel"><h2>{tab} overview</h2><p>{tab==='Agents'?'The repository agent catalog will appear here when the backend API is connected.':tab==='Workflows'?'Execution history and approval gates require the backend event stream.':'Independent benchmark results will be loaded from validated reports.'}</p><div className="empty">No verified live data connected</div></section>}
    </main>
  </div>;
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
