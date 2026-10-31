import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

type View = 'Overview' | 'Chat' | 'Agents' | 'Workflows' | 'Benchmarks' | 'Models' | 'Settings';
type Message = { id: number; role: 'user' | 'status' | 'assistant'; text: string };
type Session = { id: number; name: string; messages: Message[] };
const NAV: { label: View; icon: string }[] = [
  {label:'Overview',icon:'◫'},{label:'Chat',icon:'◉'},{label:'Agents',icon:'◇'},
  {label:'Workflows',icon:'⑂'},{label:'Benchmarks',icon:'▥'},{label:'Models',icon:'◈'},{label:'Settings',icon:'⚙'}
];
const PRESETS = [
  {name:'Java code review',text:'Review my Java project for correctness, concurrency, security and recovery issues.'},
  {name:'Architecture review',text:'Assess the architecture and propose a minimal, evidence-backed improvement plan.'},
  {name:'Test strategy',text:'Propose regression tests for the current implementation and its failure modes.'}
];
type Agent = {name: string; scope: string; description: string};
type Benchmark = {agent_count: number; expected_cells: number; observed_cells: number; verified_trial_count: number; coverage_percent: number; warning: string};
const AGENTS: Agent[] = [
  {name:'Java Reviewer',scope:'Java',description:'Concurrency, correctness and Java compatibility.'},
  {name:'Spring Framework Expert',scope:'Spring',description:'Transactions, security, configuration and service boundaries.'},
  {name:'React Reviewer',scope:'Frontend',description:'Accessibility, rendering, state and security.'},
  {name:'Kubernetes Engineer',scope:'Platform',description:'Deployments, isolation, reliability and policy.'}
];
const INITIAL: Session[] = [{id:1,name:'New conversation',messages:[{id:1,role:'status',text:'Preview workspace ready. Chat messages stay in this browser tab. No AI model, agent or repository is connected by default.'}]}];
const initialSessionId = 1;
function App() {
  const [view,setView] = useState<View>('Overview');
  const [sessions,setSessions] = useState<Session[]>(INITIAL);
  const [sessionId,setSessionId] = useState(initialSessionId);
  const [draft,setDraft] = useState('');
  const [agent,setAgent] = useState('Automatic (preview)');
  const [model,setModel] = useState('');
  const [installedModels,setInstalledModels] = useState<string[]>([]);
  const [chatEnabled,setChatEnabled] = useState(false);
  const [sending,setSending] = useState(false);
  const [search,setSearch] = useState('');
  const [remoteAgents,setRemoteAgents] = useState<Agent[] | null>(null);
  const [benchmarks,setBenchmarks] = useState<Benchmark | null>(null);
  const [apiStatus,setApiStatus] = useState<'checking' | 'connected' | 'offline'>('checking');
  const [dataError,setDataError] = useState('');
  useEffect(()=>{
    const controller = new AbortController();
    async function load() {
      try {
        const [health, agents, report, modelsResponse] = await Promise.all([
          fetch('/api/health',{signal:controller.signal}),
          fetch('/api/agents',{signal:controller.signal}),
          fetch('/api/benchmarks',{signal:controller.signal}),
          fetch('/api/models',{signal:controller.signal})
        ]);
        if (!health.ok || !agents.ok || !report.ok || !modelsResponse.ok) throw new Error('Read-only API unavailable');
        const healthData: unknown = await health.json();
        const agentData: unknown = await agents.json();
        const reportData: unknown = await report.json();
        const copilotStatus = await fetch('/api/copilot/status',{signal:controller.signal});
        if (copilotStatus.ok) {
          const state: unknown = await copilotStatus.json();
          if (state && typeof state==='object' && 'enabled' in state && state.enabled===true) setCopilotEnabled(true);
        }
        const modelsData: unknown = await modelsResponse.json();
        if (!healthData || typeof healthData!=='object' || !('execution_enabled' in healthData) || healthData.execution_enabled!==false) throw new Error('Unexpected execution state');
        if (!agentData || typeof agentData!=='object' || !('agents' in agentData) || !Array.isArray(agentData.agents) || !agentData.agents.every((a: unknown)=>a!==null && typeof a==='object' && 'name' in a && typeof a.name==='string' && 'scope' in a && typeof a.scope==='string' && 'description' in a && typeof a.description==='string')) throw new Error('Invalid agent catalog');
        if (!reportData || typeof reportData!=='object' || !('verified_trial_count' in reportData) || typeof reportData.verified_trial_count!=='number' || !('observed_cells' in reportData) || typeof reportData.observed_cells!=='number' || !('expected_cells' in reportData) || typeof reportData.expected_cells!=='number' || !('agent_count' in reportData) || typeof reportData.agent_count!=='number' || !('coverage_percent' in reportData) || typeof reportData.coverage_percent!=='number') throw new Error('Invalid benchmark summary');
        if (controller.signal.aborted) return;
        if (modelsData && typeof modelsData === 'object' && 'models' in modelsData && Array.isArray(modelsData.models) && modelsData.models.every((m: unknown)=>typeof m==='string') && 'chat_enabled' in modelsData && typeof modelsData.chat_enabled==='boolean') {
          setInstalledModels(modelsData.models as string[]);
          setChatEnabled(modelsData.chat_enabled);
          if (modelsData.models.length) setModel(previous=>previous || modelsData.models[0]);
        }
        setRemoteAgents(agentData.agents as Agent[]);
        setBenchmarks(reportData as Benchmark);
        setApiStatus('connected');
      } catch(error) {
        if (controller.signal.aborted) return;
        setApiStatus('offline');
        setDataError(error instanceof Error ? error.message : 'Unknown API error');
      }
    }
    void load();
    return ()=>controller.abort();
  },[]);
  const displayedAgents = remoteAgents ?? AGENTS;
  const [menuOpen,setMenuOpen] = useState(false);
  const [showDetails,setShowDetails] = useState(true);
  const session = sessions.find(s=>s.id===sessionId) ?? sessions[0];
  const filteredAgents = useMemo(()=>displayedAgents.filter(a=>(a.name+' '+a.scope+' '+a.description).toLowerCase().includes(search.toLowerCase())),[search,displayedAgents]);
  function newChat() {
    const id = Date.now();
    setSessions(previous=>[{id,name:'New conversation',messages:[{id,role:'status',text:'New local conversation. No provider is connected.'}]},...previous]);
    setSessionId(id);setDraft('');setView('Chat');setMenuOpen(false);
  }
  async function send(event: React.FormEvent) {
    event.preventDefault();
    const text = draft.trim();
    if (!text || sending) return;
    const stamp = Date.now();
    const history = session.messages.filter(m=>m.role==='user' || m.role==='assistant')
      .slice(-18).map(m=>({role:m.role,content:m.text}));
    setSessions(previous=>previous.map(s=>s.id===sessionId?{...s,
      name:s.name==='New conversation'?text.slice(0,38):s.name,
      messages:[...s.messages,{id:stamp,role:'user',text}]}:s));
    setDraft('');
    if (!chatEnabled || !model) {
      setSessions(previous=>previous.map(s=>s.id===sessionId?{...s,messages:[...s.messages,
        {id:stamp+1,role:'status',text:'Not executed. Start the backend with --enable-local-chat and install an Ollama model.'}]}:s));
      return;
    }
    setSending(true);
    try {
      const response = await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({model,messages:[...history,{role:'user',content:text}]})});
      if (!response.ok) throw new Error('Local model request failed ('+response.status+').');
      const result: unknown = await response.json();
      if (!result || typeof result!=='object' || !('reply' in result) || typeof result.reply!=='string') throw new Error('Invalid local model response.');
      setSessions(previous=>previous.map(s=>s.id===sessionId?{...s,messages:[...s.messages,
        {id:stamp+1,role:'assistant',text:result.reply as string}]}:s));
    } catch(error) {
      setSessions(previous=>previous.map(s=>s.id===sessionId?{...s,messages:[...s.messages,
        {id:stamp+1,role:'status',text:error instanceof Error?error.message:'Local chat unavailable'}]}:s));
    } finally {setSending(false);}
  }
  const title=view==='Overview'?'Engineering workspace':view;
  return <div className="app">
    <aside className={'sidebar '+(menuOpen?'expanded':'')}>
      <div className="identity"><div className="logo">✧</div><div><strong>daeloryn</strong><small>ENGINEERING INTELLIGENCE</small></div></div>
      <button className="new-chat" onClick={newChat}><span>＋</span> New conversation <span className="shortcut">↗</span></button>
      <div className="nav-label">WORKSPACE</div>
      <nav aria-label="Main navigation">{NAV.map(item=><button key={item.label} className={'nav-item '+(view===item.label?'selected':'')} onClick={()=>{setView(item.label);setMenuOpen(false)}}><span className="nav-icon">{item.icon}</span>{item.label}{item.label==='Chat'&&<span className="nav-count">{sessions.length}</span>}</button>)}</nav>
      <div className="nav-label history-label">RECENT CHATS</div>
      <div className="history">{sessions.map(s=><button key={s.id} className={'history-item '+(view==='Chat'&&sessionId===s.id?'current':'')} onClick={()=>{setSessionId(s.id);setView('Chat');setMenuOpen(false)}} title={s.name}>◌ <span>{s.name}</span></button>)}</div>
      <div className="side-bottom"><div className="side-status"><span className="status-dot"/> Local preview <small>Read-only API: {apiStatus}</small></div><div className="avatar-row"><span className="avatar">D</span><div><strong>Local workspace</strong><small>Developer mode</small></div><span>⌄</span></div></div>
    </aside>
    <div className="workspace">
      <header className="topbar"><div className="breadcrumbs"><button className="mobile-menu" onClick={()=>setMenuOpen(!menuOpen)} aria-label="Toggle navigation">☰</button><span>Workspace</span><span className="crumb-sep">/</span><strong>{title}</strong></div><div className="top-actions"><span className="preview-chip"><span className="status-dot"/> Preview environment</span><button className="icon-button" title="Settings" onClick={()=>setView('Settings')}>⚙</button><span className="top-avatar">D</span></div></header>
      <main className="content">
      {view==='Overview'&&<><div className="page-intro"><div className="eyebrow">YOUR ENGINEERING COMMAND CENTER</div><h1>Build with intelligence<span className="accent">.</span></h1><p>Coordinate specialist agents, inspect execution evidence, and measure outcomes in one workspace.</p></div>
        <div className="notice"><span className="notice-icon">ⓘ</span><div><strong>Workspace is in preview mode</strong><p>These screens show the product interface. No live agents, model calls, workflow executions or verified benchmark results are connected.</p></div><button onClick={()=>setView('Settings')}>View status →</button></div>
        <div className="metrics"><Metric label="Agent catalog" value={remoteAgents?String(remoteAgents.length):"—"} note={remoteAgents?"Loaded from repository":"Waiting for API"} icon="◇"/><Metric label="Connected models" value="0" note="No verified sessions" icon="◈"/><Metric label="Active workflows" value="0" note="Execution backend offline" icon="⑂"/><Metric label="Verified comparisons" value={benchmarks?String(benchmarks.verified_trial_count):"—"} note="Independent evidence only" icon="▥"/></div>
        <div className="section-title"><div><h2>Start with a task</h2><p>Choose a workflow to prepare your next request.</p></div><button className="text-action" onClick={()=>setView('Chat')}>Open chat →</button></div>
        <div className="quick-grid">{PRESETS.map((p,i)=><button key={p.name} className="quick-card" onClick={()=>{setDraft(p.text);setView('Chat')}}><span className="quick-icon">{['⌘','⬡','✓'][i]}</span><strong>{p.name}</strong><p>{p.text}</p><span className="quick-arrow">↗</span></button>)}</div>
        <div className="split"><section className="surface"><div className="surface-head"><h2>Execution pipeline</h2><span className="subtle-tag">DESIGN PREVIEW</span></div><div className="pipeline">{['Request','Agent routing','Approval','Execution','Evidence'].map((step,i)=><div key={step} className="pipeline-step"><span>{i+1}</span><strong>{step}</strong>{i<4&&<b>→</b>}</div>)}</div><p className="muted">Stages are illustrative; no pipeline is currently running.</p></section><section className="surface"><div className="surface-head"><h2>Environment health</h2><span className="subtle-tag">LOCAL</span></div><StatusLine label="Frontend console" state="Preview available"/><StatusLine label="AI provider connection" state="Not configured"/><StatusLine label="Independent evaluation" state="No active run"/></section></div>
      </>}
      {view==='Chat'&&<><div className="page-heading"><div><div className="eyebrow">AGENT WORKSPACE</div><h1>AI Chat</h1><p>Prepare engineering tasks and select an agent. Execution requires a trusted backend.</p></div><button className="outline-button" onClick={newChat}>＋ New chat</button></div>
        <div className="chat-layout"><section className="chat-panel"><div className="chat-toolbar"><div><span className="chat-orb">✧</span><strong>{session.name}</strong><small>Local conversation</small></div><button className="icon-button" onClick={()=>setShowDetails(!showDetails)} aria-label="Toggle session details">☷</button></div>
          <div className="chat-messages" aria-live="polite">{session.messages.map(m=><article key={m.id} className={'bubble '+m.role}><div className="bubble-author">{m.role==='user'?'YOU':'DAELORYN · SYSTEM STATUS'}</div><p>{m.text}</p></article>)}</div>
          <form className="composer" onSubmit={send}><label htmlFor="task-input">Message</label><textarea id="task-input" value={draft} onChange={e=>setDraft(e.target.value)} placeholder="Ask Daeloryn to review code, plan a workflow, or assess architecture…" rows={3}/><div className="composer-footer"><span>⌁ {chatEnabled ? 'Local Ollama · no tools or repository access' : 'No live model connected · no prompt transmitted'}</span><button disabled={!draft.trim() || sending} type="submit">{sending ? "Generating…" : chatEnabled ? "Send to local model" : "Add message"} <span>↗</span></button></div></form>
        </section>{showDetails&&<aside className="details-panel"><h3>Session configuration</h3><p className="muted">Preview-only selections</p><label>Agent<select value={agent} onChange={e=>setAgent(e.target.value)}><option>Automatic (preview)</option>{displayedAgents.map(a=><option key={a.name}>{a.name}</option>)}</select></label><label>Model<select value={model} onChange={e=>setModel(e.target.value)}><option value="">No model selected</option>{installedModels.map(m=><option key={m} value={m}>{m}</option>)}</select></label><div className="detail-divider"/><h3>Execution safeguards</h3><StatusLine label="Provider" state="Disconnected"/><StatusLine label="Workspace access" state="Disabled"/><StatusLine label="Code modifications" state="Disabled"/><StatusLine label="Approval gates" state="Not active"/><div className="details-note">Model selection can invoke local Ollama only when explicitly enabled. Agent selection is still preview-only; no tools or repository modifications.</div></aside>}</div>
      </>}
      {view==='Agents'&&<><PageHeading eyebrow="SPECIALIST DIRECTORY" title="Agent catalog" description="Explore engineering roles. The full repository catalog will be loaded by the future API."/><div className="filter-bar"><input aria-label="Search agents" value={search} onChange={e=>setSearch(e.target.value)} placeholder="⌕  Search specialists…"/><span>{remoteAgents ? 'Repository catalog · '+remoteAgents.length+' agents' : 'Illustrative profiles · API offline'}</span></div><div className="agent-grid">{filteredAgents.map(a=><article className="agent-card" key={a.name}><div className="agent-card-top"><span className="agent-symbol">✧</span><span className="subtle-tag">{a.scope}</span></div><h3>{a.name}</h3><p>{a.description}</p><div className="agent-bottom"><span>○ Not connected</span><button onClick={()=>{setAgent(a.name);setView('Chat')}}>Select for chat →</button></div></article>)}</div>{filteredAgents.length===0&&<Empty text="No agents match your search."/>}</>}
      {view==='Workflows'&&<><PageHeading eyebrow="EXECUTION ORCHESTRATION" title="Workflows" description="Track request lifecycle, approvals and execution events once the backend is connected."/><div className="notice"><span className="notice-icon">ⓘ</span><div><strong>Execution disabled</strong><p>No workflows are running. The following pipeline is an interface preview only.</p></div></div><section className="surface"><div className="surface-head"><h2>Workflow lifecycle</h2><span className="subtle-tag">REFERENCE DESIGN</span></div><div className="workflow-grid">{['Request submitted','Route to specialist','Review proposed changes','Explicit human approval','Isolated execution','Independent verification'].map((s,i)=><div key={s} className="workflow-stage"><span>0{i+1}</span><strong>{s}</strong><small>Not started</small></div>)}</div></section><Empty text="No real workflow history is available."/></>}
      {view==='Benchmarks'&&<><PageHeading eyebrow="QUALITY & EVIDENCE" title="Benchmarks" description="Compare agent performance only after independently validated executions."/><div className="metrics compact"><Metric label="Verified trials" value={benchmarks?String(benchmarks.verified_trial_count):"—"} note="Verified flags from reports" icon="✓"/><Metric label="Agent coverage" value={benchmarks?benchmarks.coverage_percent+"%":"—"} note={benchmarks?benchmarks.observed_cells+" / "+benchmarks.expected_cells+" cells":"Awaiting validated data"} icon="◇"/><Metric label="Precision / recall" value="—" note="No scores to display" icon="▥"/></div><section className="surface"><div className="surface-head"><h2>Comparison results</h2><span className="subtle-tag">NO DATA</span></div><div className="table-wrap"><table><thead><tr><th>Agent</th><th>Provider</th><th>Model verified</th><th>F1</th><th>Evidence</th></tr></thead><tbody><tr><td colSpan={5} className="table-empty">{benchmarks ? 'Summary loaded; per-trial details not exposed by this API.' : 'Benchmark API unavailable.'}</td></tr></tbody></table></div></section></>}
      {view==='Models'&&<><PageHeading eyebrow="INTELLIGENT ROUTING" title="Model router" description="Choose a suitable model by task complexity, cost and capability when provider discovery is available."/><div className="model-grid">{[{name:'Lightweight tasks',model:'Haiku',icon:'⚡',description:'Simple classification, formatting and low-complexity requests.'},{name:'Engineering work',model:'Sonnet',icon:'⌘',description:'Code review, implementation and multi-file reasoning.'},{name:'Complex reasoning',model:'Opus',icon:'◈',description:'Architecture, difficult investigations and high-risk changes.'}].map(m=><article className="model-card" key={m.name}><span className="model-icon">{m.icon}</span><small>{m.name.toUpperCase()}</small><h2>{m.model}</h2><p>{m.description}</p><div className="model-footer">Illustrative routing tier · not discovered</div></article>)}</div><div className="notice"><span className="notice-icon">ⓘ</span><div><strong>Model availability is not verified</strong><p>These tiers describe intended routing behavior, not currently available models or live prices.</p></div></div></>}
      {view==='Settings'&&<><PageHeading eyebrow="WORKSPACE CONFIGURATION" title="Settings" description="Connection status and security boundaries for this local frontend."/><div className="settings-grid"><section className="surface"><h2>Connections</h2><StatusLine label="AI API" state={chatEnabled ? "Local Ollama enabled" : "Not configured"}/><StatusLine label="Backend API" state={apiStatus}/><StatusLine label="Repository catalog" state={remoteAgents?"Read-only loaded":"Unavailable"}/><StatusLine label="Streaming events" state="Unavailable"/>{dataError&&<p className="muted" role="status">API: {dataError}</p>}</section><section className="surface"><h2>Privacy & controls</h2><p className="muted">Conversation history exists only in React memory and disappears on refresh. No browser storage, external API calls, secret injection or arbitrary command execution are enabled.</p><div className="detail-divider"/><button className="outline-button" onClick={()=>{setSessions(INITIAL);setSessionId(1);setDraft('');setView('Chat')}}>Clear local conversation history</button></section></div></>}
      </main>
    </div>
  </div>;
}
function Metric({label,value,note,icon}:{label:string;value:string;note:string;icon:string}) {return <div className="metric"><div className="metric-top"><span>{label}</span><span className="metric-icon">{icon}</span></div><strong>{value}</strong><small>{note}</small></div>}
function PageHeading({eyebrow,title,description}:{eyebrow:string;title:string;description:string}){return <div className="page-heading"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{description}</p></div></div>}
function StatusLine({label,state}:{label:string;state:string}){return <div className="status-line"><span>{label}</span><span>{state}</span></div>}
function Empty({text}:{text:string}){return <div className="empty-state"><div>◇</div><strong>Nothing to display yet</strong><p>{text}</p></div>}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);  async function send(event: React.FormEvent) {
    event.preventDefault();
    const text = draft.trim();
    if (!text || sending) return;
    const stamp=Date.now();
    const targetSession=sessionId;
    const history=session.messages.filter(m=>m.role==='user'||m.role==='assistant')
      .slice(-10).map(m=>({role:m.role,content:m.text}));
    setSessions(previous=>previous.map(s=>s.id===targetSession?{...s,name:s.name==='New conversation'?text.slice(0,38):s.name,
      messages:[...s.messages,{id:stamp,role:'user',text}]}:s));
    setDraft('');
    if (!copilotEnabled || !model.trim()) {
      setSessions(previous=>previous.map(s=>s.id===targetSession?{...s,messages:[...s.messages,
        {id:stamp+1,role:'status',text:'Not executed. Enable Copilot chat on the backend and enter an available model ID.'}]}:s));
      return;
    }
    setSending(true);
    try {
      const response=await fetch('/api/copilot/chat',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({model:model.trim(),messages:[...history,{role:'user',content:text}]})});
      if (!response.ok) throw new Error('Copilot request failed ('+response.status+').');
      const result: unknown=await response.json();
      if (!result||typeof result!=='object'||!('reply' in result)||typeof result.reply!=='string')
        throw new Error('Invalid Copilot response');
      setSessions(previous=>previous.map(s=>s.id===targetSession?{...s,messages:[...s.messages,
        {id:stamp+1,role:'assistant',text:result.reply as string}]}:s));
    } catch(error) {
      setSessions(previous=>previous.map(s=>s.id===targetSession?{...s,messages:[...s.messages,
        {id:stamp+1,role:'status',text:error instanceof Error?error.message:'Copilot unavailable'}]}:s));
    } finally {setSending(false);}
  }
  const title=view==='Overview'?'Engineering workspace':view;
  return <div className="app">
    <aside className={'sidebar '+(menuOpen?'expanded':'')}>
      <div className="identity"><div className="logo">✧</div><div><strong>daeloryn</strong><small>ENGINEERING INTELLIGENCE</small></div></div>
      <button className="new-chat" onClick={newChat}><span>＋</span> New conversation <span className="shortcut">↗</span></button>
      <div className="nav-label">WORKSPACE</div>
      <nav aria-label="Main navigation">{NAV.map(item=><button key={item.label} className={'nav-item '+(view===item.label?'selected':'')} onClick={()=>{setView(item.label);setMenuOpen(false)}}><span className="nav-icon">{item.icon}</span>{item.label}{item.label==='Chat'&&<span className="nav-count">{sessions.length}</span>}</button>)}</nav>
      <div className="nav-label history-label">RECENT CHATS</div>
      <div className="history">{sessions.map(s=><button key={s.id} className={'history-item '+(view==='Chat'&&sessionId===s.id?'current':'')} onClick={()=>{setSessionId(s.id);setView('Chat');setMenuOpen(false)}} title={s.name}>◌ <span>{s.name}</span></button>)}</div>
      <div className="side-bottom"><div className="side-status"><span className="status-dot"/> Local preview <small>Read-only API: {apiStatus}</small></div><div className="avatar-row"><span className="avatar">D</span><div><strong>Local workspace</strong><small>Developer mode</small></div><span>⌄</span></div></div>
    </aside>
    <div className="workspace">
      <header className="topbar"><div className="breadcrumbs"><button className="mobile-menu" onClick={()=>setMenuOpen(!menuOpen)} aria-label="Toggle navigation">☰</button><span>Workspace</span><span className="crumb-sep">/</span><strong>{title}</strong></div><div className="top-actions"><span className="preview-chip"><span className="status-dot"/> Preview environment</span><button className="icon-button" title="Settings" onClick={()=>setView('Settings')}>⚙</button><span className="top-avatar">D</span></div></header>
      <main className="content">
      {view==='Overview'&&<><div className="page-intro"><div className="eyebrow">YOUR ENGINEERING COMMAND CENTER</div><h1>Build with intelligence<span className="accent">.</span></h1><p>Coordinate specialist agents, inspect execution evidence, and measure outcomes in one workspace.</p></div>
        <div className="notice"><span className="notice-icon">ⓘ</span><div><strong>Workspace is in preview mode</strong><p>These screens show the product interface. No live agents, model calls, workflow executions or verified benchmark results are connected.</p></div><button onClick={()=>setView('Settings')}>View status →</button></div>
        <div className="metrics"><Metric label="Agent catalog" value={remoteAgents?String(remoteAgents.length):"—"} note={remoteAgents?"Loaded from repository":"Waiting for API"} icon="◇"/><Metric label="Connected models" value="0" note="No verified sessions" icon="◈"/><Metric label="Active workflows" value="0" note="Execution backend offline" icon="⑂"/><Metric label="Verified comparisons" value={benchmarks?String(benchmarks.verified_trial_count):"—"} note="Independent evidence only" icon="▥"/></div>
        <div className="section-title"><div><h2>Start with a task</h2><p>Choose a workflow to prepare your next request.</p></div><button className="text-action" onClick={()=>setView('Chat')}>Open chat →</button></div>
        <div className="quick-grid">{PRESETS.map((p,i)=><button key={p.name} className="quick-card" onClick={()=>{setDraft(p.text);setView('Chat')}}><span className="quick-icon">{['⌘','⬡','✓'][i]}</span><strong>{p.name}</strong><p>{p.text}</p><span className="quick-arrow">↗</span></button>)}</div>
        <div className="split"><section className="surface"><div className="surface-head"><h2>Execution pipeline</h2><span className="subtle-tag">DESIGN PREVIEW</span></div><div className="pipeline">{['Request','Agent routing','Approval','Execution','Evidence'].map((step,i)=><div key={step} className="pipeline-step"><span>{i+1}</span><strong>{step}</strong>{i<4&&<b>→</b>}</div>)}</div><p className="muted">Stages are illustrative; no pipeline is currently running.</p></section><section className="surface"><div className="surface-head"><h2>Environment health</h2><span className="subtle-tag">LOCAL</span></div><StatusLine label="Frontend console" state="Preview available"/><StatusLine label="AI provider connection" state="Not configured"/><StatusLine label="Independent evaluation" state="No active run"/></section></div>
      </>}
      {view==='Chat'&&<><div className="page-heading"><div><div className="eyebrow">AGENT WORKSPACE</div><h1>AI Chat</h1><p>Prepare engineering tasks and select an agent. Execution requires a trusted backend.</p></div><button className="outline-button" onClick={newChat}>＋ New chat</button></div>
        <div className="chat-layout"><section className="chat-panel"><div className="chat-toolbar"><div><span className="chat-orb">✧</span><strong>{session.name}</strong><small>Local conversation</small></div><button className="icon-button" onClick={()=>setShowDetails(!showDetails)} aria-label="Toggle session details">☷</button></div>
          <div className="chat-messages" aria-live="polite">{session.messages.map(m=><article key={m.id} className={'bubble '+m.role}><div className="bubble-author">{m.role==='user'?'YOU':'DAELORYN · SYSTEM STATUS'}</div><p>{m.text}</p></article>)}</div>
          <form className="composer" onSubmit={send}><label htmlFor="task-input">Message</label><textarea id="task-input" value={draft} onChange={e=>setDraft(e.target.value)} placeholder="Ask Daeloryn to review code, plan a workflow, or assess architecture…" rows={3}/><div className="composer-footer"><span>⌁ {chatEnabled ? 'Local Ollama · no tools or repository access' : 'No live model connected · no prompt transmitted'}</span><button disabled={!draft.trim() || sending} type="submit">{sending ? "Generating…" : chatEnabled ? "Send to local model" : "Add message"} <span>↗</span></button></div></form>
        </section>{showDetails&&<aside className="details-panel"><h3>Session configuration</h3><p className="muted">Preview-only selections</p><label>Agent<select value={agent} onChange={e=>setAgent(e.target.value)}><option>Automatic (preview)</option>{displayedAgents.map(a=><option key={a.name}>{a.name}</option>)}</select></label><label>Model<select value={model} onChange={e=>setModel(e.target.value)}><option value="">No model selected</option>{installedModels.map(m=><option key={m} value={m}>{m}</option>)}</select></label><div className="detail-divider"/><h3>Execution safeguards</h3><StatusLine label="Provider" state="Disconnected"/><StatusLine label="Workspace access" state="Disabled"/><StatusLine label="Code modifications" state="Disabled"/><StatusLine label="Approval gates" state="Not active"/><div className="details-note">Model selection can invoke local Ollama only when explicitly enabled. Agent selection is still preview-only; no tools or repository modifications.</div></aside>}</div>
      </>}
      {view==='Agents'&&<><PageHeading eyebrow="SPECIALIST DIRECTORY" title="Agent catalog" description="Explore engineering roles. The full repository catalog will be loaded by the future API."/><div className="filter-bar"><input aria-label="Search agents" value={search} onChange={e=>setSearch(e.target.value)} placeholder="⌕  Search specialists…"/><span>{remoteAgents ? 'Repository catalog · '+remoteAgents.length+' agents' : 'Illustrative profiles · API offline'}</span></div><div className="agent-grid">{filteredAgents.map(a=><article className="agent-card" key={a.name}><div className="agent-card-top"><span className="agent-symbol">✧</span><span className="subtle-tag">{a.scope}</span></div><h3>{a.name}</h3><p>{a.description}</p><div className="agent-bottom"><span>○ Not connected</span><button onClick={()=>{setAgent(a.name);setView('Chat')}}>Select for chat →</button></div></article>)}</div>{filteredAgents.length===0&&<Empty text="No agents match your search."/>}</>}
      {view==='Workflows'&&<><PageHeading eyebrow="EXECUTION ORCHESTRATION" title="Workflows" description="Track request lifecycle, approvals and execution events once the backend is connected."/><div className="notice"><span className="notice-icon">ⓘ</span><div><strong>Execution disabled</strong><p>No workflows are running. The following pipeline is an interface preview only.</p></div></div><section className="surface"><div className="surface-head"><h2>Workflow lifecycle</h2><span className="subtle-tag">REFERENCE DESIGN</span></div><div className="workflow-grid">{['Request submitted','Route to specialist','Review proposed changes','Explicit human approval','Isolated execution','Independent verification'].map((s,i)=><div key={s} className="workflow-stage"><span>0{i+1}</span><strong>{s}</strong><small>Not started</small></div>)}</div></section><Empty text="No real workflow history is available."/></>}
      {view==='Benchmarks'&&<><PageHeading eyebrow="QUALITY & EVIDENCE" title="Benchmarks" description="Compare agent performance only after independently validated executions."/><div className="metrics compact"><Metric label="Verified trials" value={benchmarks?String(benchmarks.verified_trial_count):"—"} note="Verified flags from reports" icon="✓"/><Metric label="Agent coverage" value={benchmarks?benchmarks.coverage_percent+"%":"—"} note={benchmarks?benchmarks.observed_cells+" / "+benchmarks.expected_cells+" cells":"Awaiting validated data"} icon="◇"/><Metric label="Precision / recall" value="—" note="No scores to display" icon="▥"/></div><section className="surface"><div className="surface-head"><h2>Comparison results</h2><span className="subtle-tag">NO DATA</span></div><div className="table-wrap"><table><thead><tr><th>Agent</th><th>Provider</th><th>Model verified</th><th>F1</th><th>Evidence</th></tr></thead><tbody><tr><td colSpan={5} className="table-empty">{benchmarks ? 'Summary loaded; per-trial details not exposed by this API.' : 'Benchmark API unavailable.'}</td></tr></tbody></table></div></section></>}
      {view==='Models'&&<><PageHeading eyebrow="INTELLIGENT ROUTING" title="Model router" description="Choose a suitable model by task complexity, cost and capability when provider discovery is available."/><div className="model-grid">{[{name:'Lightweight tasks',model:'Haiku',icon:'⚡',description:'Simple classification, formatting and low-complexity requests.'},{name:'Engineering work',model:'Sonnet',icon:'⌘',description:'Code review, implementation and multi-file reasoning.'},{name:'Complex reasoning',model:'Opus',icon:'◈',description:'Architecture, difficult investigations and high-risk changes.'}].map(m=><article className="model-card" key={m.name}><span className="model-icon">{m.icon}</span><small>{m.name.toUpperCase()}</small><h2>{m.model}</h2><p>{m.description}</p><div className="model-footer">Illustrative routing tier · not discovered</div></article>)}</div><div className="notice"><span className="notice-icon">ⓘ</span><div><strong>Model availability is not verified</strong><p>These tiers describe intended routing behavior, not currently available models or live prices.</p></div></div></>}
      {view==='Settings'&&<><PageHeading eyebrow="WORKSPACE CONFIGURATION" title="Settings" description="Connection status and security boundaries for this local frontend."/><div className="settings-grid"><section className="surface"><h2>Connections</h2><StatusLine label="AI API" state={chatEnabled ? "Local Ollama enabled" : "Not configured"}/><StatusLine label="Backend API" state={apiStatus}/><StatusLine label="Repository catalog" state={remoteAgents?"Read-only loaded":"Unavailable"}/><StatusLine label="Streaming events" state="Unavailable"/>{dataError&&<p className="muted" role="status">API: {dataError}</p>}</section><section className="surface"><h2>Privacy & controls</h2><p className="muted">Conversation history exists only in React memory and disappears on refresh. No browser storage, external API calls, secret injection or arbitrary command execution are enabled.</p><div className="detail-divider"/><button className="outline-button" onClick={()=>{setSessions(INITIAL);setSessionId(1);setDraft('');setView('Chat')}}>Clear local conversation history</button></section></div></>}
      </main>
    </div>
  </div>;
}
function Metric({label,value,note,icon}:{label:string;value:string;note:string;icon:string}) {return <div className="metric"><div className="metric-top"><span>{label}</span><span className="metric-icon">{icon}</span></div><strong>{value}</strong><small>{note}</small></div>}
function PageHeading({eyebrow,title,description}:{eyebrow:string;title:string;description:string}){return <div className="page-heading"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{description}</p></div></div>}
function StatusLine({label,state}:{label:string;state:string}){return <div className="status-line"><span>{label}</span><span>{state}</span></div>}
function Empty({text}:{text:string}){return <div className="empty-state"><div>◇</div><strong>Nothing to display yet</strong><p>{text}</p></div>}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
