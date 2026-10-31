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
  const [agentRecommendation,setAgentRecommendation] = useState('');
  const [repositoryRecommendation,setRepositoryRecommendation] = useState('');
  const [repositoryConfirmed,setRepositoryConfirmed] = useState(false);
  const [repositoryCatalog,setRepositoryCatalog] = useState<{name:string;path:string;technologies:string[]}[]>([]);
  const [githubCatalog,setGithubCatalog] = useState<{name:string;language:string;private:boolean}[]>([]);
  const [reviewBusy,setReviewBusy] = useState(false);
  const [reviewResult,setReviewResult] = useState<{repository:string;source_files_scanned:number;findings:{rule:string;severity:string;file:string;line:number;evidence:string;suggested_fix:string}[];limitations:string;workflow?:{stage:string;source_transmitted:boolean;patch_applied:boolean;tests_executed:boolean;pr_created:boolean;limitations:string};remediation_plan?:{actions:{file:string;line:number;rule:string;suggested_change:string;regression_test:string;status:string}[];approval_required:boolean;patch_generated:boolean;tests_executed:boolean};architecture?:{components:{file:string;language:string;symbols:string[]}[];framework_hints:{name:string;import_occurrences:number}[];limitations:string}}|null>(null);
  const [reviewError,setReviewError] = useState('');
  const [model,setModel] = useState('');
  const [installedModels,setInstalledModels] = useState<string[]>([]);
  const [chatEnabled,setChatEnabled] = useState(false);
  const [copilotEnabled,setCopilotEnabled] = useState(false);
  const [provider,setProvider] = useState<'copilot' | 'ollama'>('copilot');
  const [copilotModel,setCopilotModel] = useState('auto');
  const [copilotModels,setCopilotModels] = useState<string[]>([]);
  const [copilotDiscoveryError,setCopilotDiscoveryError] = useState('');
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
          if (state && typeof state==='object' && 'enabled' in state && state.enabled===true) {
            setCopilotEnabled(true);
            try {
              const discovered = await fetch('/api/copilot/models',{signal:controller.signal});
              if (!discovered.ok) throw new Error('Live Copilot model discovery unavailable');
              const catalog: unknown = await discovered.json();
              if (!catalog || typeof catalog!=='object' || !('models' in catalog) ||
                  !Array.isArray(catalog.models) || !catalog.models.every((m: unknown)=>typeof m==='string'))
                throw new Error('Invalid Copilot model catalog');
              setCopilotModels(catalog.models as string[]);
            } catch (error) {
              if (!controller.signal.aborted) setCopilotDiscoveryError(error instanceof Error?error.message:'Discovery unavailable');
            }
          }
        }
        const modelsData: unknown = await modelsResponse.json();
        if (!healthData || typeof healthData!=='object' || !('execution_enabled' in healthData) || healthData.execution_enabled!==false) throw new Error('Unexpected execution state');
        if (!agentData || typeof agentData!=='object' || !('agents' in agentData) || !Array.isArray(agentData.agents) || !agentData.agents.every((a: unknown)=>a!==null && typeof a==='object' && 'name' in a && typeof a.name==='string' && 'scope' in a && typeof a.scope==='string' && 'description' in a && typeof a.description==='string')) throw new Error('Invalid agent catalog');
        if (!reportData || typeof reportData!=='object' || !('verified_trial_count' in reportData) || typeof reportData.verified_trial_count!=='number' || !('observed_cells' in reportData) || typeof reportData.observed_cells!=='number' || !('expected_cells' in reportData) || typeof reportData.expected_cells!=='number' || !('agent_count' in reportData) || typeof reportData.agent_count!=='number' || !('coverage_percent' in reportData) || typeof reportData.coverage_percent!=='number') throw new Error('Invalid benchmark summary');
        if (controller.signal.aborted) return;
        if (modelsData && typeof modelsData === 'object' && 'models' in modelsData && Array.isArray(modelsData.models) && modelsData.models.every((m: unknown)=>typeof m==='string') && 'chat_enabled' in modelsData && typeof modelsData.chat_enabled==='boolean') {
          setInstalledModels(modelsData.models as string[]);
          setChatEnabled(modelsData.chat_enabled);
          const discoveredModels = modelsData.models as string[];
          if (discoveredModels.length) setModel(previous=>previous || discoveredModels[0]);
        }
        try {
          const response=await fetch('/api/repositories',{signal:controller.signal});
          if (response.ok) {
            const data:unknown=await response.json();
            if (data && typeof data==='object' && 'repositories' in data &&
                Array.isArray(data.repositories) &&
                data.repositories.every((r:unknown)=>r!==null && typeof r==='object' &&
                  'name' in r && typeof r.name==='string' && 'path' in r && typeof r.path==='string' &&
                  'technologies' in r && Array.isArray(r.technologies)))
              setRepositoryCatalog(data.repositories as {name:string;path:string;technologies:string[]}[]);
          }
        } catch { /* optional repository catalog; chat remains usable */ }
        try {
          const githubResponse=await fetch('/api/github/repositories',{signal:controller.signal});
          if (githubResponse.ok) {
            const data:unknown=await githubResponse.json();
            if (data && typeof data==='object' && 'repositories' in data &&
                Array.isArray(data.repositories) &&
                data.repositories.every((r:unknown)=>r!==null && typeof r==='object' &&
                  'name' in r && typeof r.name==='string' &&
                  'language' in r && typeof r.language==='string' &&
                  'private' in r && typeof r.private==='boolean'))
              setGithubCatalog(data.repositories as {name:string;language:string;private:boolean}[]);
          }
        } catch { /* GitHub discovery is optional */ }
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
    const text=draft.trim();
    if (!text || sending) return;
    const stamp=Date.now(), targetSession=sessionId;
    const selectedModel=provider==='copilot'?copilotModel:model;
    const enabled=provider==='copilot'?copilotEnabled:chatEnabled;
    const history=session.messages.filter(m=>m.role==='user'||m.role==='assistant')
      .slice(-10).map(m=>({role:m.role,content:m.text}));
    setSessions(previous=>previous.map(s=>s.id===targetSession?{...s,
      name:s.name==='New conversation'?text.slice(0,38):s.name,
      messages:[...s.messages,{id:stamp,role:'user',text}]}:s));
    setDraft('');
    if (!enabled || !selectedModel) {
      setSessions(previous=>previous.map(s=>s.id===targetSession?{...s,messages:[...s.messages,
        {id:stamp+1,role:'status',text:'Not executed: enable the selected provider and choose a model.'}]}:s));
      return;
    }
    setSending(true);
    try {
      if (provider==='copilot') {
        try {
          const suggestion=await fetch('/api/repository-routing',{method:'POST',
            headers:{'Content-Type':'application/json'},body:JSON.stringify({task:text})});
          if (suggestion.ok) {
            const data:unknown=await suggestion.json();
            if (data && typeof data==='object' && 'repository' in data &&
                data.repository && typeof data.repository==='object' &&
                'name' in data.repository && typeof data.repository.name==='string') {
              const suggestedName: string = data.repository.name;
              if (!repositoryConfirmed) setRepositoryRecommendation(suggestedName);
            } else if (!repositoryConfirmed) setRepositoryRecommendation('No unique repository match');
          } else setRepositoryRecommendation('Repository recommendation unavailable');
        } catch { setRepositoryRecommendation('Repository recommendation unavailable'); }
      }
      if (provider==='copilot' && agent==='Automatic (preview)') {
        try {
          const suggestion=await fetch('/api/agent-routing',{method:'POST',
            headers:{'Content-Type':'application/json'},body:JSON.stringify({task:text})});
          if (suggestion.ok) {
            const data: unknown=await suggestion.json();
            if (data && typeof data==='object' && 'agent' in data && typeof data.agent==='string')
              setAgentRecommendation(data.agent);
            else setAgentRecommendation('No unambiguous specialist');
          } else setAgentRecommendation('Agent recommendation unavailable');
        } catch { setAgentRecommendation('Agent recommendation unavailable'); }
      }

      const url=provider==='copilot'?'/api/copilot/chat':'/api/chat';
      const response=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({model:selectedModel,messages:[...history,{role:'user',content:text}]})});
      if (!response.ok) throw new Error(provider+' request failed ('+response.status+').');
      const result: unknown=await response.json();
      if (!result||typeof result!=='object') throw new Error('Invalid response');
      const answer='reply' in result?result.reply:null;
      const routing='routing' in result && result.routing && typeof result.routing==='object' &&
        'requested_model' in result.routing && typeof result.routing.requested_model==='string'
        ? result.routing.requested_model : null;
      if (typeof answer!=='string') throw new Error('Missing assistant reply');
      setSessions(previous=>previous.map(s=>s.id===targetSession?{...s,messages:[...s.messages,
        {id:stamp+1,role:'assistant',text:routing?'[Auto-selected model: '+routing+']\\n\\n'+answer:answer}]}:s));
    } catch(error) {
      setSessions(previous=>previous.map(s=>s.id===targetSession?{...s,messages:[...s.messages,
        {id:stamp+1,role:'status',text:error instanceof Error?error.message:'Provider unavailable'}]}:s));
    } finally {setSending(false);}
  }
  async function runLocalReview() {
    setReviewError('');setReviewResult(null);
    if (!repositoryConfirmed || !repositoryCatalog.some(r=>r.name===repositoryRecommendation)) {
      setReviewError('Select and confirm a local repository first. GitHub cloud repositories are not supported.');
      return;
    }
    setReviewBusy(true);
    try {
      const response=await fetch('/api/code-review',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({repository:repositoryRecommendation,task:draft.trim() || 'Review code correctness and security'})});
      if (!response.ok) throw new Error('Read-only review unavailable ('+response.status+').');
      const data:unknown=await response.json();
      if (!data || typeof data!=='object' || !('findings' in data) || !Array.isArray(data.findings) ||
          !('repository' in data) || typeof data.repository!=='string' ||
          !('source_files_scanned' in data) || typeof data.source_files_scanned!=='number' ||
          !('limitations' in data) || typeof data.limitations!=='string' ||
          !data.findings.every((f:unknown)=>f!==null && typeof f==='object' &&
            'file' in f && typeof f.file==='string' && 'line' in f && typeof f.line==='number' &&
            'rule' in f && typeof f.rule==='string' && 'severity' in f && typeof f.severity==='string' &&
            'evidence' in f && typeof f.evidence==='string' && 'suggested_fix' in f && typeof f.suggested_fix==='string'))
        throw new Error('Invalid review response');
      setReviewResult(data as {repository:string;source_files_scanned:number;findings:{rule:string;severity:string;file:string;line:number;evidence:string;suggested_fix:string}[];limitations:string;workflow?:{stage:string;source_transmitted:boolean;patch_applied:boolean;tests_executed:boolean;pr_created:boolean;limitations:string};remediation_plan?:{actions:{file:string;line:number;rule:string;suggested_change:string;regression_test:string;status:string}[];approval_required:boolean;patch_generated:boolean;tests_executed:boolean};architecture?:{components:{file:string;language:string;symbols:string[]}[];framework_hints:{name:string;import_occurrences:number}[];limitations:string}});
    } catch (error) {setReviewError(error instanceof Error?error.message:'Review unavailable');}
    finally {setReviewBusy(false);}
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
          <form className="composer" onSubmit={send}><label htmlFor="task-input">Message</label><textarea id="task-input" value={draft} onChange={e=>setDraft(e.target.value)} placeholder="Ask Daeloryn to review code, plan a workflow, or assess architecture…" rows={3}/><div className="composer-footer"><span>⌁ {chatEnabled ? 'Local Ollama · no tools or repository access' : 'No selected provider connected'}</span><button disabled={!draft.trim() || sending} type="submit">{sending ? "Generating…" : "Send message"} <span>↗</span></button></div></form>
        </section>{showDetails&&<aside className="details-panel"><h3>Session configuration</h3><p className="muted">Agent recommendation is advisory; no agent tools or workspace access.</p>{agentRecommendation && <p className="muted">Suggested specialist: {agentRecommendation}</p>}<label>Local repository (read-only suggestion)<select value={repositoryConfirmed?repositoryRecommendation:''} onChange={e=>{setRepositoryRecommendation(e.target.value);setRepositoryConfirmed(Boolean(e.target.value));}}><option value="">Not confirmed</option>{githubCatalog.map(r=><option key={'github:'+r.name} value={r.name}>{r.name} (GitHub{r.private?', private':''}{r.language?', '+r.language:''})</option>)}{repositoryCatalog.map(r=><option key={r.path} value={r.name}>{r.name}</option>)}</select></label>{repositoryRecommendation && <p className="muted">Suggested repository: {repositoryRecommendation}. Confirm it manually before any future repository operation. Current chat does not access the repository.</p>}<div className="review-controls"><button type="button" className="outline-button" disabled={reviewBusy} onClick={()=>void runLocalReview()}>{reviewBusy?'Inspecting…':'Run local code review (read-only)'}</button><p className="muted">Only local checkouts. Findings are heuristic, not confirmed defects. No AI upload, edits or test execution.</p>{reviewError&&<p role="alert">{reviewError}</p>}{reviewResult&&<section aria-label="Code review results"><h3>{reviewResult.repository}: {reviewResult.findings.length} review leads</h3>{reviewResult.workflow&&<div className="surface"><h3>Engineering workflow</h3><p>Current stage: {reviewResult.workflow.stage}</p><p className="muted">Approval gates: context → proposal → patch → verified tests → PR readiness.</p><p className="muted">{reviewResult.workflow.limitations}</p></div>}{reviewResult.remediation_plan&&<div className="surface"><h3>Remediation & regression-test plan</h3><p className="muted">Human review required. No patches, tests, branches or pull requests have been created.</p>{reviewResult.remediation_plan.actions.map((a,i)=><article key={i}><strong>{a.file}:{a.line} · {a.rule}</strong><p>Suggested change: {a.suggested_change}</p><p>Regression test: {a.regression_test}</p></article>)}</div>}<p className="muted">{reviewResult.source_files_scanned} source files inspected. {reviewResult.limitations}</p>{reviewResult.architecture&&<div className="surface"><h3>Architecture evidence</h3><p className="muted">{reviewResult.architecture.limitations}</p><h4>Framework hints</h4><p>{reviewResult.architecture.framework_hints.map(h=>h.name+' ('+h.import_occurrences+')').join(', ')||'No known framework imports found'}</p><h4>Source components</h4><ul>{reviewResult.architecture.components.map(c=><li key={c.file}>{c.file} · {c.language}{c.symbols.length?' · '+c.symbols.join(', '):''}</li>)}</ul></div>}{reviewResult.findings.map((f,i)=><article key={i} className="surface"><strong>{f.severity.toUpperCase()} · {f.rule}</strong><p>{f.file}:{f.line}</p><p>{f.evidence}</p><p className="muted">Suggested fix: {f.suggested_fix}</p></article>)}</section>}</div><label>Agent<select value={agent} onChange={e=>setAgent(e.target.value)}><option>Automatic (preview)</option>{displayedAgents.map(a=><option key={a.name}>{a.name}</option>)}</select></label><label>Provider<select value={provider} onChange={e=>setProvider(e.target.value as 'copilot'|'ollama')}><option value="copilot">GitHub Copilot</option><option value="ollama">Local Ollama</option></select></label>{provider==='copilot'?<label>Copilot model<select value={copilotModel} onChange={e=>setCopilotModel(e.target.value)}><option value="auto">Automatic (task-based)</option>{copilotModels.map(m=><option key={m} value={m}>{m}</option>)}</select></label>:<label>Model<select value={model} onChange={e=>setModel(e.target.value)}><option value="">No model selected</option>{installedModels.map(m=><option key={m} value={m}>{m}</option>)}</select></label>}{provider==='copilot' && copilotDiscoveryError && <p className="muted">{copilotDiscoveryError} — automatic routing will fail closed.</p>}<div className="detail-divider"/><h3>Execution safeguards</h3><StatusLine label="Provider" state="Disconnected"/><StatusLine label="Workspace access" state="Disabled"/><StatusLine label="Code modifications" state="Disabled"/><StatusLine label="Approval gates" state="Not active"/><div className="details-note">Model selection can invoke local Ollama only when explicitly enabled. Agent selection is still preview-only; no tools or repository modifications.</div></aside>}</div>
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
