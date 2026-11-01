import {HISTORY_KEY,readHistory,saveHistory} from './chatHistory';
import type {Message,Session} from './chatHistory';
import {ProgressiveReply} from './ProgressiveReply';
import {ProjectPicker} from './ProjectPicker';
import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';
import {chatRequest,reviewRequest,reviewSelectionKey,selectedAgent} from './copilotRequests';

type View = 'Overview' | 'Chat' | 'Agents' | 'Workflows' | 'Benchmarks' | 'Models' | 'Settings';
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
type BenchmarkTrial = {run_id:string;agent:string;provider:string;arm:string;outcome:string;baseline_model:string;daeloryn_model:string;model_identity_verified:boolean;agent_selection_verified:boolean;independent_checks_executed:boolean;comparable:boolean};
type Benchmark = {trials?:BenchmarkTrial[];agent_count: number; expected_cells: number; observed_cells: number; verified_trial_count: number; coverage_percent: number; warning: string};
const AGENTS: Agent[] = [
  {name:'Java Reviewer',scope:'Java',description:'Concurrency, correctness and Java compatibility.'},
  {name:'Spring Framework Expert',scope:'Spring',description:'Transactions, security, configuration and service boundaries.'},
  {name:'React Reviewer',scope:'Frontend',description:'Accessibility, rendering, state and security.'},
  {name:'Kubernetes Engineer',scope:'Platform',description:'Deployments, isolation, reliability and policy.'}
];
const INITIAL: Session[] = [{id:1,name:'New conversation',messages:[{id:1,role:'status',text:'Preview workspace ready. Chat history is saved locally in this browser. Plain chat cannot read repository files. No AI model, agent or repository is connected by default.'}]}];
const initialSessionId = 1;

type PreparedReview = {repository:string;prompt:string;sha256:string;files:string[];warning:string;model:string;agent:string|null;agent_profile:string|null;agent_profile_sha256:string|null;batch_count?:number;coverage?:{all_eligible_files_included:boolean;omitted:{path:string;reason:string}[];excluded:{path:string;reason:string}[];scope:string}};
function ApprovedCopilotReview({repository,task,enabled,model,agent,onResult}:{repository:string;task:string;enabled:boolean;model:string;agent?:string;onResult?:(text:string)=>void}) {
  const [prepared,setPrepared] = useState<PreparedReview|null>(null);
  const [approved,setApproved] = useState(false);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState('');
  const [answer,setAnswer] = useState('');
  const [progress,setProgress] = useState('');
  const [elapsed,setElapsed] = useState(0);
  useEffect(()=>{if(!busy)return;setElapsed(0);const timer=window.setInterval(()=>setElapsed(n=>n+1),1000);return()=>window.clearInterval(timer);},[busy]);
  const reviewTask=task.trim() || 'Review code correctness and security';
  const reset=()=>{setPrepared(null);setApproved(false);setAnswer('');setError('');};
  async function prepareReview() {
    reset();setProgress('Preparing local source context…');setBusy(true);
    try {
      const response=await fetch('/api/copilot/review/prepare',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(reviewRequest({repository,task:reviewTask,model,agent}))});
      if (!response.ok) {const failure=await response.json();throw new Error(failure.error||'Context preparation failed ('+response.status+')');}
      const data:unknown=await response.json();
      if (!data || typeof data!=='object' || !('prompt' in data) || typeof data.prompt!=='string' ||
          !('sha256' in data) || typeof data.sha256!=='string' || !('repository' in data) || data.repository!==repository ||
          !('model' in data) || data.model!==model || !('agent' in data) || data.agent!==(agent||null) ||
          !('agent_profile' in data) || !(data.agent_profile===null||typeof data.agent_profile==='string') ||
          !('files' in data) || !Array.isArray(data.files) || !('warning' in data) || typeof data.warning!=='string')
        throw new Error('Invalid prepared review response');
      setPrepared(data as PreparedReview);
    } catch(e) {setError(e instanceof Error?e.message:'Preparation failed');}
    finally {setBusy(false);}
  }
  async function executeReview() {
    if (!prepared || !approved) return;
    setBusy(true);setError('');setAnswer('');setProgress('Validating approved source before the first model call…');
    const controller=new AbortController();
    const timeout=window.setTimeout(()=>controller.abort(),420000);
    try {
      const response=await fetch('/api/copilot/review/execute',{method:'POST',signal:controller.signal,headers:{'Content-Type':'application/json','Accept':'application/x-ndjson'},
        body:JSON.stringify(reviewRequest({repository,task:reviewTask,model,agent},prepared.sha256))});
      if (!response.ok) throw new Error('Approval expired or Copilot unavailable ('+response.status+'). Prepare again.');
      let data:unknown;
      if(response.headers.get('content-type')?.includes('application/x-ndjson')) {
        if(!response.body)throw new Error('Review stream unavailable');
        const reader=response.body.getReader();const decoder=new TextDecoder();let pending='';
        while(true){
          const {value,done}=await reader.read();pending+=decoder.decode(value,{stream:!done});
          const lines=pending.split('\n');pending=lines.pop()||'';
          for(const line of lines){if(!line.trim())continue;const event=JSON.parse(line);
            if(event.type==='progress')setProgress(event.completed+'/'+event.total+' batches completed · '+(event.phase==='running'?'Copilot is processing batch '+event.batch:'Batch '+event.batch+' received'));
            else if(event.type==='result')data=event.result;
            else if(event.type==='error')throw new Error(event.error);
          }
          if(done)break;
        }
        if(!data)throw new Error('Connection ended before the final result. External outcome may be unknown; do not automatically retry.');
      }else data=await response.json();
      const result=data as {review?:{reply?:string};status?:string;completed_batches?:number;total_batches?:number;failure?:string;coverage?:{all_eligible_files_included:boolean}};
      const summary='Source review: '+(result.status||'completed')+' · '+(result.completed_batches??1)+'/'+(result.total_batches??1)+' batches. Eligible source coverage: '+(result.coverage?.all_eligible_files_included===true?'all included':'see manifest; exclusions/omissions may apply')+'\n'+(result.failure||'')+'\n\n'+(result.review?.reply||JSON.stringify(data,null,2));
      setAnswer(summary);onResult?.(summary);
      setPrepared(null);setApproved(false);
    } catch(e) {setError('Review interrupted: '+(e instanceof Error?e.message:'connection failed')+'. External outcome may be unknown; do not automatically retry.');setPrepared(null);setApproved(false);}
    finally {window.clearTimeout(timeout);setBusy(false);}
  }
  return <section className="surface" aria-label="Approved Copilot source review">
    <h3>Copilot AI source review (opt-in)</h3>
    <p className="muted">Review all supported local project source and build files in approved batches. Inspect coverage and exclusions before sending. No file edits or tests.</p>
    <button type="button" className="outline-button" disabled={!enabled||!model||model==='auto'||busy} onClick={()=>void prepareReview()}>{busy?'Working…':'Prepare AI review context'}</button>
    {busy&&<p role="status">{progress} · {elapsed}s elapsed. Calls run sequentially; an active call can take up to 90 seconds. The five-minute budget is checked between calls.</p>}
    {!enabled&&<p className="muted">Enable Copilot in the local API and confirm a local repository to use this feature.</p>}
    {model==='auto'&&<p className="muted">Choose a concrete Copilot model before preparing source review.</p>}
    <p className="muted">Requested model: {model||'none'} · Agent: {agent||'generic chat'}</p>
    {prepared&&<div><p><strong>SHA-256:</strong> <code>{prepared.sha256}</code></p><p>{prepared.warning}</p>
      <p>{prepared.files.length} files · {prepared.batch_count??1} model calls (potentially billable).</p><details><summary>Source coverage and exclusions</summary><p>{prepared.coverage?.scope||'Prepared source context'}</p><p>{prepared.coverage?.all_eligible_files_included===false?'PARTIAL: some eligible files omitted. Do not treat this as complete project coverage.':'All eligible files included in prepared context.'}</p><ul>{prepared.files.map(file=><li key={file}>{file}</li>)}</ul>{prepared.coverage&&<pre style={{whiteSpace:'pre-wrap'}}>{JSON.stringify({omitted:prepared.coverage.omitted,excluded:prepared.coverage.excluded},null,2)}</pre>}</details>
      {prepared.agent_profile&&<details><summary>Agent profile · {prepared.agent} · {prepared.agent_profile_sha256}</summary><pre style={{whiteSpace:'pre-wrap',maxHeight:240,overflowY:'auto'}}>{prepared.agent_profile}</pre></details>}
      <pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere',maxHeight:320,overflowY:'auto'}}>{prepared.prompt}</pre>
      <label><input type="checkbox" checked={approved} onChange={e=>setApproved(e.target.checked)}/> I inspected the context, model and agent profile and approve sending them to Copilot.</label>
      <button type="button" disabled={!approved||busy} onClick={()=>void executeReview()}>Send approved context to Copilot</button>
    </div>}
    {error&&<p role="alert">{error}</p>}
    {answer&&(onResult?<p role="status">Source review result added to the conversation.</p>:<ProgressiveReply text={answer} animate={true}/>)}
  </section>;
}


function PatchPreview({repository,enabled}:{repository:string;enabled:boolean}) {
 const [path,setPath]=useState('');
 const [replacement,setReplacement]=useState('');
 const [diff,setDiff]=useState('');
 const [digest,setDigest]=useState('');
 const [error,setError]=useState('');
 const [busy,setBusy]=useState(false);
 async function run() {
  setDiff('');setDigest('');setError('');setBusy(true);
  try {
   const response=await fetch('/api/patch/preview',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({repository,path,replacement})});
   if (!response.ok) throw new Error('Preview rejected ('+response.status+')');
   const data:unknown=await response.json();
   if (!data||typeof data!=='object'||!('diff' in data)||typeof data.diff!=='string'||
       !('sha256' in data)||typeof data.sha256!=='string') throw new Error('Invalid diff response');
   setDiff(data.diff);setDigest(data.sha256);
  } catch(e) {setError(e instanceof Error?e.message:'Preview unavailable');}
  finally {setBusy(false);}
 }
 return <section className="surface" aria-label="Patch preview">
  <h3>Patch preview (read-only)</h3>
  <p className="muted">Paste a complete replacement for one local source file. Review its diff before any future approval or write. This does not apply the patch.</p>
  <input aria-label="Relative source file" placeholder="src/main/java/App.java" value={path} onChange={e=>{setPath(e.target.value);setDiff('');setDigest('');}}/>
  <textarea aria-label="Replacement source" rows={8} placeholder="Paste replacement source" value={replacement} onChange={e=>{setReplacement(e.target.value);setDiff('');setDigest('');}}/>
  <button type="button" disabled={!enabled||busy||!path||!replacement} onClick={()=>void run()}>{busy?'Preparing…':'Preview patch'}</button>
  {!enabled&&<p className="muted">Select and confirm a local repository first.</p>}
  {error&&<p role="alert">{error}</p>}
  {digest&&<p>SHA-256: <code>{digest}</code></p>}
  {diff&&<pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere',maxHeight:360,overflowY:'auto'}}>{diff}</pre>}
 </section>;
}


function InterruptedWorkflows() {
 const [items,setItems]=useState<{id:string;stage:string;action:string;reason:string}[]>([]);
 const [error,setError]=useState('');
 const [loaded,setLoaded]=useState(false);
 const [busy,setBusy]=useState(false);
 async function refresh(){
  setBusy(true);setError('');
  try{
   const response=await fetch('/api/workflows/interrupted');
   if(!response.ok)throw new Error(response.status===405?'Start the local API with --workflow-dir to enable inspection':'Workflow inspection unavailable ('+response.status+')');
   const data=await response.json();
   if(!data||!Array.isArray(data.interrupted))throw new Error('Invalid workflow response');
   setItems(data.interrupted);setLoaded(true);
  }catch(e){setError(e instanceof Error?e.message:'Unknown error');}
  finally{setBusy(false);}
 }
 return <section className="surface" aria-label="Interrupted workflows">
  <h3>Interrupted workflows (read-only)</h3>
  <p className="muted">Inspect uncertain local test and publication states. This view never resumes, retries or publishes jobs.</p>
  <button type="button" disabled={busy} onClick={()=>void refresh()}>{busy?'Loading…':'Refresh interrupted jobs'}</button>
  {error&&<p role="alert">{error}</p>}
  {loaded&&items.length===0&&<p role="status">No interrupted workflows reported.</p>}
  {items.map(item=><div key={item.id} className="workflow-stage"><strong>{item.id}</strong><small>{item.stage} · {item.action}</small><p>{item.reason}</p></div>)}
 </section>;
}

function RepairDiagnostics() {
 const [log,setLog]=useState('');
 const [attempt,setAttempt]=useState(1);
 const [result,setResult]=useState<{diagnoses:{category:string;suggestion:string}[];retry_allowed:boolean;log_truncated:boolean}|null>(null);
 const [error,setError]=useState('');
 const [busy,setBusy]=useState(false);
 async function diagnose() {
  setError('');setResult(null);setBusy(true);
  try {
   const response=await fetch('/api/repair/diagnose',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({log,attempt})});
   if(!response.ok)throw new Error('Diagnosis unavailable ('+response.status+')');
   const data=await response.json();
   if(!data||!Array.isArray(data.diagnoses)||typeof data.retry_allowed!=='boolean')throw new Error('Invalid response');
   setResult(data);
  }catch(e){setError(e instanceof Error?e.message:'Unknown error');}
  finally{setBusy(false);}
 }
 return <section className="surface" aria-label="Repair diagnostics">
  <h3>Test failure diagnosis (read-only)</h3>
  <p className="muted">Paste a sanitized test log. Diagnosis runs locally using deterministic rules. No model call, file change, test execution or PR publication occurs.</p>
  <textarea aria-label="Sanitized failed test log" rows={6} maxLength={6000} value={log} onChange={e=>{setLog(e.target.value);setResult(null);}} placeholder="Paste sanitized failure output"/>
  <label>Attempt <select aria-label="Repair attempt" value={attempt} onChange={e=>setAttempt(Number(e.target.value))}>{[1,2,3].map(n=><option key={n} value={n}>{n}</option>)}</select></label>
  <button type="button" disabled={!log.trim()||busy} onClick={()=>void diagnose()}>{busy?'Analyzing…':'Diagnose failure'}</button>
  {error&&<p role="alert">{error}</p>}
  {result&&<div role="status">{result.diagnoses.map((item,i)=><p key={i}><strong>{item.category}:</strong> {item.suggestion}</p>)}<p>Another attempt allowed: {result.retry_allowed?'Yes':'No'}</p></div>}
 </section>;
}

function EngineeringWorkflowGuide({repository,confirmed,onOpenChat}:{repository:string;confirmed:boolean;onOpenChat:()=>void}) {
 const [reviewed,setReviewed]=useState(false);
 const [tested,setTested]=useState(false);
 const [published,setPublished]=useState(false);
 const [notes,setNotes]=useState('');
 const reset=()=>{setReviewed(false);setTested(false);setPublished(false);setNotes('');};
 return <section className="surface" aria-label="Engineering workflow guide">
  <div className="surface-head"><h2>Engineering workflow</h2><span className="subtle-tag">MANUAL APPROVALS</span></div>
  <p className="muted">Repository: {confirmed?repository:'Not confirmed'}. This guide tracks acknowledgements in the current tab only. It does not execute commands, verify test results or publish code.</p>
  <div className="workflow-grid">
   <div className="workflow-stage"><span>01</span><strong>AI source review</strong><small>{confirmed?'Available in Chat':'Confirm a local repository in Chat'}</small></div>
   <div className="workflow-stage"><span>02</span><strong>Patch diff preview</strong><small>Inspect exact SHA-256 in Chat</small></div>
   <div className="workflow-stage"><span>03</span><strong>Approve branch change</strong><small>Python library only; no UI write endpoint</small></div>
   <div className="workflow-stage"><span>04</span><strong>Container tests</strong><small>Explicit opt-in; Docker required</small></div>
   <div className="workflow-stage"><span>05</span><strong>Commit and publish</strong><small>Commit-bound approval; Python library only</small></div>
   <div className="workflow-stage"><span>06</span><strong>Draft GitHub PR</strong><small>Manual review required</small></div>
  </div>
  <button type="button" className="outline-button" onClick={onOpenChat}>Open repository review and patch preview</button>
  <p className="muted">Optional personal checklist (not verified evidence):</p>
  <label><input type="checkbox" checked={reviewed} onChange={e=>{setReviewed(e.target.checked);setTested(false);setPublished(false);}}/> I reviewed the exact patch diff</label>
  <label><input type="checkbox" checked={tested} disabled={!reviewed} onChange={e=>{setTested(e.target.checked);setPublished(false);}}/> I independently checked the test results</label>
  <label><input type="checkbox" checked={published} disabled={!tested} onChange={e=>setPublished(e.target.checked)}/> I verified the draft PR on GitHub</label>
  <textarea aria-label="Workflow notes" rows={3} placeholder="Optional local notes (not persisted)" value={notes} onChange={e=>setNotes(e.target.value)}/>
  <p className="muted">Checklist: {published?'Acknowledged complete (unverified)':tested?'Tests acknowledged (unverified)':reviewed?'Patch reviewed (unverified)':'Not started'}</p>
  <button type="button" className="outline-button" onClick={reset}>Reset checklist</button>
 </section>;
}

function App() {
  const [view,setView] = useState<View>('Overview');
  const [restored] = useState(()=>{
    try{return {history:readHistory(window.localStorage),error:''};}
    catch{return {history:null,error:'Stored history is unavailable or invalid.'};}
  });
  const [sessions,setSessions] = useState<Session[]>(restored.history?.sessions??INITIAL);
  const [sessionId,setSessionId] = useState(restored.history?.activeId??initialSessionId);
  const [historyError,setHistoryError] = useState(restored.error);
  const [historyBlocked,setHistoryBlocked] = useState(Boolean(restored.error));
  const [renaming,setRenaming] = useState(false);
  const [renameDraft,setRenameDraft] = useState('');
  const [revealingId,setRevealingId] = useState<number|null>(null);
  useEffect(()=>{
    if(historyBlocked)return;
    try{saveHistory(window.localStorage,sessions,sessionId);setHistoryError('');}
    catch{setHistoryError('History could not be saved (storage unavailable or limit exceeded). Keep this tab open; new messages remain in memory.');}
  },[sessions,sessionId,historyBlocked]);
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
        if ('trials' in reportData && (!Array.isArray(reportData.trials) || !reportData.trials.every((t:unknown)=>{
          if (!t || typeof t!=='object') return false;
          const row=t as Record<string,unknown>;
          return ['run_id','agent','provider','arm','outcome','baseline_model','daeloryn_model'].every(k=>typeof row[k]==='string') &&
            ['model_identity_verified','agent_selection_verified','independent_checks_executed','comparable'].every(k=>typeof row[k]==='boolean');
        }))) throw new Error('Invalid benchmark trial details');
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
    const id = Math.max(Date.now(),...sessions.map(s=>s.id+1));
    setSessions(previous=>[{id,name:'New conversation',messages:[{id,role:'status',text:'New local conversation. Source review requires separate context approval.'}]},...previous]);
    setSessionId(id);setDraft('');setView('Chat');setMenuOpen(false);
  }
  async function send(event: React.FormEvent) {
    event.preventDefault();
    const text=draft.trim();
    if (!text || sending) return;
    const stamp=Math.max(Date.now(),...session.messages.map(m=>m.id+2)), targetSession=sessionId;
    const selectedModel=provider==='copilot'?copilotModel:model;
    const enabled=provider==='copilot'?copilotEnabled:chatEnabled;
    const history=session.messages.filter(m=>m.role==='user'||m.role==='assistant')
      .slice(-10).map(m=>({role:m.role as 'user'|'assistant',content:m.text}));
    setSessions(previous=>previous.map(s=>s.id===targetSession?{...s,
      name:!s.renamed&&s.name==='New conversation'?text.replace(/\s+/g,' ').slice(0,38):s.name,
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
        body:JSON.stringify(chatRequest(selectedModel,[...history,{role:'user',content:text}],provider==='copilot'?selectedAgent(agent):undefined))});
      if (!response.ok) throw new Error(provider+' request failed ('+response.status+').');
      const result: unknown=await response.json();
      if (!result||typeof result!=='object') throw new Error('Invalid response');
      const answer='reply' in result?result.reply:null;
      const routing='routing' in result && result.routing && typeof result.routing==='object' &&
        'requested_model' in result.routing && typeof result.routing.requested_model==='string'
        ? result.routing.requested_model : null;
      if (typeof answer!=='string') throw new Error('Missing assistant reply');
      setRevealingId(stamp+1);
      setSessions(previous=>previous.map(s=>s.id===targetSession?{...s,messages:[...s.messages,
        {id:stamp+1,role:'assistant',text:(provider==='copilot'&&agent!=='Automatic (preview)'?'[Requested agent: '+agent+']\n\n':'')+(routing?'[Auto-selected model: '+routing+']\n\n'+answer:answer)}]}:s));
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
        <div className="notice"><span className="notice-icon">ⓘ</span><div><strong>Workspace is in preview mode</strong><p>Chat can use explicitly enabled local providers and named Copilot agents. Workflow screens remain previews; model and agent compliance are not independently attested.</p></div><button onClick={()=>setView('Settings')}>View status →</button></div>
        <div className="metrics"><Metric label="Agent catalog" value={remoteAgents?String(remoteAgents.length):"—"} note={remoteAgents?"Loaded from repository":"Waiting for API"} icon="◇"/><Metric label="Connected models" value="0" note="No verified sessions" icon="◈"/><Metric label="Active workflows" value="0" note="Execution backend offline" icon="⑂"/><Metric label="Verified comparisons" value={benchmarks?String(benchmarks.verified_trial_count):"—"} note="Independent evidence only" icon="▥"/></div>
        <div className="section-title"><div><h2>Start with a task</h2><p>Choose a workflow to prepare your next request.</p></div><button className="text-action" onClick={()=>setView('Chat')}>Open chat →</button></div>
        <div className="quick-grid">{PRESETS.map((p,i)=><button key={p.name} className="quick-card" onClick={()=>{setDraft(p.text);setView('Chat')}}><span className="quick-icon">{['⌘','⬡','✓'][i]}</span><strong>{p.name}</strong><p>{p.text}</p><span className="quick-arrow">↗</span></button>)}</div>
        <div className="split"><section className="surface"><div className="surface-head"><h2>Execution pipeline</h2><span className="subtle-tag">DESIGN PREVIEW</span></div><div className="pipeline">{['Request','Agent routing','Approval','Execution','Evidence'].map((step,i)=><div key={step} className="pipeline-step"><span>{i+1}</span><strong>{step}</strong>{i<4&&<b>→</b>}</div>)}</div><p className="muted">Stages are illustrative; no pipeline is currently running.</p></section><section className="surface"><div className="surface-head"><h2>Environment health</h2><span className="subtle-tag">LOCAL</span></div><StatusLine label="Frontend console" state="Preview available"/><StatusLine label="AI provider connection" state="Not configured"/><StatusLine label="Independent evaluation" state="No active run"/></section></div>
      </>}
      {view==='Chat'&&<><div className="page-heading"><div><div className="eyebrow">AGENT WORKSPACE</div><h1>AI Chat</h1><p>Prepare engineering tasks and select an agent. Execution requires a trusted backend.</p></div><button className="outline-button" onClick={newChat}>＋ New chat</button></div>
        <div className="chat-layout"><section className="chat-panel"><div className="chat-toolbar"><div><span className="chat-orb">✧</span><strong>{session.name}</strong><small>{historyError?'Not saved · memory only':'Saved in this browser'}</small><button type="button" className="text-action" onClick={()=>{setRenameDraft(session.name);setRenaming(true);}}>Rename conversation</button></div><button className="icon-button" onClick={()=>setShowDetails(!showDetails)} aria-label="Toggle session details">☷</button></div>
          {renaming&&<form className="rename-form" onSubmit={e=>{e.preventDefault();const name=renameDraft.trim();if(!name||name.length>100||/[\x00-\x1f]/.test(name))return;setSessions(previous=>previous.map(s=>s.id===sessionId?{...s,name,renamed:true}:s));setRenaming(false);}}><label>Conversation name<input autoFocus maxLength={100} value={renameDraft} onChange={e=>setRenameDraft(e.target.value)}/></label><button className="outline-button" type="submit" disabled={!renameDraft.trim()}>Save name</button><button className="outline-button" type="button" onClick={()=>setRenaming(false)}>Cancel rename</button></form>}
          {historyError&&<p role="alert">{historyError}</p>}
          <div className="chat-messages" aria-live="polite">{session.messages.map(m=><article key={m.id} className={'bubble '+m.role}><div className="bubble-author">{m.role==='user'?'YOU':m.role==='assistant'?'DAELORYN · ASSISTANT':'DAELORYN · SYSTEM STATUS'}</div>{m.role==='assistant'?<ProgressiveReply text={m.text} animate={revealingId===m.id}/>:<p>{m.text}</p>}</article>)}</div>
          <p className="chat-context-notice">Plain chat cannot read the selected folder or run commands. For code analysis, enter the task below, select a local repository and a concrete model, then use <strong>Prepare AI review context</strong> and approve the source.</p><form className="composer" onSubmit={send}><label htmlFor="task-input">Message</label><textarea id="task-input" aria-describedby="composer-hint" onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.ctrlKey&&!e.altKey&&!e.metaKey&&!e.nativeEvent.isComposing&&e.keyCode!==229){e.preventDefault();if(draft.trim()&&!sending&&!e.repeat)e.currentTarget.form?.requestSubmit();}}} value={draft} onChange={e=>setDraft(e.target.value)} placeholder="Ask Daeloryn to review code, plan a workflow, or assess architecture…" rows={3}/><div className="composer-footer"><span id="composer-hint">Enter to send · Shift+Enter for a new line · {provider==='copilot'?(copilotEnabled?'Copilot enabled locally · plain chat has no repository access':'Copilot disabled'):(chatEnabled?'Local Ollama · no tools or repository access':'Ollama disabled')}</span><button disabled={!draft.trim() || sending} type="submit">{sending ? "Generating…" : "Send message"} <span>↗</span></button></div></form>
        </section>{showDetails&&<aside className="details-panel"><h3>Session configuration</h3><p className="muted">Select a Daeloryn agent for Copilot chat. Automatic recommendations remain advisory. Source review requires separate context approval.</p>{agentRecommendation && <p className="muted">Suggested specialist: {agentRecommendation}</p>}<ProjectPicker onAdded={rows=>{setRepositoryCatalog(rows);setRepositoryConfirmed(false);setRepositoryRecommendation('');}}/><label>Local repository (read-only suggestion)<select value={repositoryConfirmed?repositoryRecommendation:''} onChange={e=>{setRepositoryRecommendation(e.target.value);setRepositoryConfirmed(Boolean(e.target.value));}}><option value="">Not confirmed</option>{githubCatalog.map(r=><option key={'github:'+r.name} value={r.name}>{r.name} (GitHub{r.private?', private':''}{r.language?', '+r.language:''})</option>)}{repositoryCatalog.map(r=><option key={r.path} value={r.name}>{r.name}</option>)}</select></label>{repositoryRecommendation && <p className="muted">Suggested repository: {repositoryRecommendation}. Confirm it manually before any future repository operation. Current chat does not access the repository.</p>}<ApprovedCopilotReview key={reviewSelectionKey({repository:repositoryRecommendation,task:draft,model:copilotModel,agent:selectedAgent(agent)})+'|'+repositoryConfirmed+'|'+provider} repository={repositoryRecommendation} task={draft} enabled={provider==='copilot'&&copilotEnabled&&repositoryConfirmed&&repositoryCatalog.some(r=>r.name===repositoryRecommendation)} model={copilotModel} agent={selectedAgent(agent)} onResult={text=>{const id=Date.now();setRevealingId(id);setSessions(previous=>previous.map(s=>s.id===sessionId?{...s,name:!s.renamed&&s.name==='New conversation'?'Review '+repositoryRecommendation:s.name,messages:[...s.messages,{id,role:'assistant',text}]}:s));}}/><PatchPreview key={repositoryRecommendation+'|'+repositoryConfirmed} repository={repositoryRecommendation} enabled={repositoryConfirmed&&repositoryCatalog.some(r=>r.name===repositoryRecommendation)}/><div className="review-controls"><button type="button" className="outline-button" disabled={reviewBusy} onClick={()=>void runLocalReview()}>{reviewBusy?'Inspecting…':'Run local code review (read-only)'}</button><p className="muted">Only local checkouts. Findings are heuristic, not confirmed defects. No AI upload, edits or test execution.</p>{reviewError&&<p role="alert">{reviewError}</p>}{reviewResult&&<section aria-label="Code review results"><h3>{reviewResult.repository}: {reviewResult.findings.length} review leads</h3>{reviewResult.workflow&&<div className="surface"><h3>Engineering workflow</h3><p>Current stage: {reviewResult.workflow.stage}</p><p className="muted">Approval gates: context → proposal → patch → verified tests → PR readiness.</p><p className="muted">{reviewResult.workflow.limitations}</p></div>}{reviewResult.remediation_plan&&<div className="surface"><h3>Remediation & regression-test plan</h3><p className="muted">Human review required. No patches, tests, branches or pull requests have been created.</p>{reviewResult.remediation_plan.actions.map((a,i)=><article key={i}><strong>{a.file}:{a.line} · {a.rule}</strong><p>Suggested change: {a.suggested_change}</p><p>Regression test: {a.regression_test}</p></article>)}</div>}<p className="muted">{reviewResult.source_files_scanned} source files inspected. {reviewResult.limitations}</p>{reviewResult.architecture&&<div className="surface"><h3>Architecture evidence</h3><p className="muted">{reviewResult.architecture.limitations}</p><h4>Framework hints</h4><p>{reviewResult.architecture.framework_hints.map(h=>h.name+' ('+h.import_occurrences+')').join(', ')||'No known framework imports found'}</p><h4>Source components</h4><ul>{reviewResult.architecture.components.map(c=><li key={c.file}>{c.file} · {c.language}{c.symbols.length?' · '+c.symbols.join(', '):''}</li>)}</ul></div>}{reviewResult.findings.map((f,i)=><article key={i} className="surface"><strong>{f.severity.toUpperCase()} · {f.rule}</strong><p>{f.file}:{f.line}</p><p>{f.evidence}</p><p className="muted">Suggested fix: {f.suggested_fix}</p></article>)}</section>}</div><label>Agent<select value={agent} onChange={e=>setAgent(e.target.value)}><option>Automatic (preview)</option>{displayedAgents.map(a=><option key={a.name}>{a.name}</option>)}</select></label><label>Provider<select value={provider} onChange={e=>setProvider(e.target.value as 'copilot'|'ollama')}><option value="copilot">GitHub Copilot</option><option value="ollama">Local Ollama</option></select></label>{provider==='copilot'?<label>Copilot model<select value={copilotModel} onChange={e=>setCopilotModel(e.target.value)}><option value="auto">Automatic (task-based)</option>{copilotModels.map(m=><option key={m} value={m}>{m}</option>)}</select></label>:<label>Model<select value={model} onChange={e=>setModel(e.target.value)}><option value="">No model selected</option>{installedModels.map(m=><option key={m} value={m}>{m}</option>)}</select></label>}{provider==='copilot' && copilotDiscoveryError && <p className="muted">{copilotDiscoveryError} — automatic routing will fail closed.</p>}<div className="detail-divider"/><h3>Execution safeguards</h3><StatusLine label="Provider" state={(provider==='copilot'?copilotEnabled:chatEnabled)?"Enabled locally":"Disabled"}/><StatusLine label="Workspace access" state="Approved source batches only"/><StatusLine label="Code modifications" state="Disabled"/><StatusLine label="Source review approval" state="Required"/><div className="details-note">Copilot uses the selected model and named Daeloryn agent when enabled. Plain chat has no repository context; source review sends only approved source batches. Provider model and agent compliance are not independently attested.</div></aside>}</div>
      </>}
      {view==='Agents'&&<><PageHeading eyebrow="SPECIALIST DIRECTORY" title="Agent catalog" description="Explore engineering roles. The full repository catalog will be loaded by the future API."/><div className="filter-bar"><input aria-label="Search agents" value={search} onChange={e=>setSearch(e.target.value)} placeholder="⌕  Search specialists…"/><span>{remoteAgents ? 'Repository catalog · '+remoteAgents.length+' agents' : 'Illustrative profiles · API offline'}</span></div><div className="agent-grid">{filteredAgents.map(a=><article className="agent-card" key={a.name}><div className="agent-card-top"><span className="agent-symbol">✧</span><span className="subtle-tag">{a.scope}</span></div><h3>{a.name}</h3><p>{a.description}</p><div className="agent-bottom"><span>○ Not connected</span><button onClick={()=>{setAgent(a.name);setView('Chat')}}>Select for chat →</button></div></article>)}</div>{filteredAgents.length===0&&<Empty text="No agents match your search."/>}</>}
      {view==='Workflows'&&<><PageHeading eyebrow="EXECUTION ORCHESTRATION" title="Workflows" description="Review the staged engineering workflow and its explicit safety gates."/><EngineeringWorkflowGuide key={repositoryRecommendation+'|'+repositoryConfirmed} repository={repositoryRecommendation} confirmed={repositoryConfirmed} onOpenChat={()=>setView('Chat')}/><RepairDiagnostics/><InterruptedWorkflows/></>}
      {view==='Benchmarks'&&<><PageHeading eyebrow="QUALITY & EVIDENCE" title="Benchmarks" description="Recorded comparisons; identity and execution flags are supplied by the record producer, not independently attested by this dashboard."/><div className="metrics compact"><Metric label="Reported verified trials" value={benchmarks?String(benchmarks.verified_trial_count):"—"} note="Requires all verification flags" icon="✓"/><Metric label="Agent coverage" value={benchmarks?benchmarks.coverage_percent+"%":"—"} note={benchmarks?benchmarks.observed_cells+" / "+benchmarks.expected_cells+" cells":"Awaiting data"} icon="◇"/></div><section className="surface"><div className="surface-head"><h2>Comparison results</h2><span className="subtle-tag">{benchmarks?.trials?.length?`${benchmarks.trials.length} RECORDS`:'NO DATA'}</span></div><p className="muted">{benchmarks?.warning} No provider calls are started by this page.</p><div className="table-wrap"><table><thead><tr><th>Run / agent</th><th>Provider / arm</th><th>Requested models</th><th>Outcome</th><th>Evidence flags</th></tr></thead><tbody>{benchmarks?.trials?.length?benchmarks.trials.map(t=><tr key={JSON.stringify([t.agent,t.provider,t.arm,t.run_id])}><td>{t.run_id}<br/>{t.agent}</td><td>{t.provider}<br/>{t.arm}</td><td>Baseline: {t.baseline_model}<br/>Daeloryn: {t.daeloryn_model}</td><td>{t.outcome.split('_').join(' ')}</td><td>Model: {t.model_identity_verified?'reported verified':'unverified'}<br/>Agent: {t.agent_selection_verified?'reported verified':'unverified'}<br/>Checks: {t.independent_checks_executed?'reported executed':'not verified'}<br/>Comparable: {t.comparable?'reported yes':'no'}</td></tr>):<tr><td colSpan={5} className="table-empty">{benchmarks?'No per-trial records available. Configure --records-dir with benchmark-trial JSON files.':'Benchmark API unavailable.'}</td></tr>}</tbody></table></div></section></>}
      {view==='Models'&&<><PageHeading eyebrow="INTELLIGENT ROUTING" title="Model router" description="Choose a suitable model by task complexity, cost and capability when provider discovery is available."/><div className="model-grid">{[{name:'Lightweight tasks',model:'Haiku',icon:'⚡',description:'Simple classification, formatting and low-complexity requests.'},{name:'Engineering work',model:'Sonnet',icon:'⌘',description:'Code review, implementation and multi-file reasoning.'},{name:'Complex reasoning',model:'Opus',icon:'◈',description:'Architecture, difficult investigations and high-risk changes.'}].map(m=><article className="model-card" key={m.name}><span className="model-icon">{m.icon}</span><small>{m.name.toUpperCase()}</small><h2>{m.model}</h2><p>{m.description}</p><div className="model-footer">Illustrative routing tier · not discovered</div></article>)}</div><div className="notice"><span className="notice-icon">ⓘ</span><div><strong>Model availability is not verified</strong><p>These tiers describe intended routing behavior, not currently available models or live prices.</p></div></div></>}
      {view==='Settings'&&<><PageHeading eyebrow="WORKSPACE CONFIGURATION" title="Settings" description="Connection status and security boundaries for this local frontend."/><div className="settings-grid"><section className="surface"><h2>Connections</h2><StatusLine label="AI API" state={chatEnabled ? "Local Ollama enabled" : "Not configured"}/><StatusLine label="Backend API" state={apiStatus}/><StatusLine label="Repository catalog" state={remoteAgents?"Read-only loaded":"Unavailable"}/><StatusLine label="Streaming events" state="Unavailable"/>{dataError&&<p className="muted" role="status">API: {dataError}</p>}</section><section className="surface"><h2>Privacy & controls</h2><p className="muted">Chat names and messages are saved unencrypted in localStorage in this browser profile, up to 50 conversations and 2 MB. They persist on refresh, but are not synced to the backend or other devices. Clearing browser data removes them. Enabled providers receive submitted messages. Source review still requires separate approval.</p><div className="detail-divider"/><button className="outline-button" onClick={()=>{try{window.localStorage.removeItem(HISTORY_KEY);}catch{setHistoryError('Could not clear browser storage. Clear site data in browser settings.');return;}const freshId=Math.max(Date.now(),...sessions.map(s=>s.id+1));setHistoryBlocked(false);setSessions([{...INITIAL[0],id:freshId}]);setSessionId(freshId);setDraft('');setRevealingId(null);setView('Chat')}}>Clear local conversation history</button></section></div></>}
      </main>
    </div>
  </div>;
}
function Metric({label,value,note,icon}:{label:string;value:string;note:string;icon:string}) {return <div className="metric"><div className="metric-top"><span>{label}</span><span className="metric-icon">{icon}</span></div><strong>{value}</strong><small>{note}</small></div>}
function PageHeading({eyebrow,title,description}:{eyebrow:string;title:string;description:string}){return <div className="page-heading"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{description}</p></div></div>}
function StatusLine({label,state}:{label:string;state:string}){return <div className="status-line"><span>{label}</span><span>{state}</span></div>}
function Empty({text}:{text:string}){return <div className="empty-state"><div>◇</div><strong>Nothing to display yet</strong><p>{text}</p></div>}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
