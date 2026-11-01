import {useEffect,useRef,useState} from 'react';

type Agent={name:string;scope:string;description:string};
type Project={name:string;path:string;technologies:string[]};
type Mode='review'|'architecture'|'fix-plan';
type Arm='baseline'|'daeloryn';
type Assessment={confirmed:string;falsePositives:string;references:string};
const emptyAssessment=():Record<Arm,Assessment>=>({baseline:{confirmed:'',falsePositives:'',references:''},daeloryn:{confirmed:'',falsePositives:'',references:''}});
type Coverage={scope:string;all_eligible_files_included:boolean;omitted:{path:string;reason:string}[];excluded:{path:string;reason:string}[]};
type PreparedArm={sha256:string;prompt:string;files:string[];batch_count:number;agent:string|null;agent_profile:string|null;coverage:Coverage};
type PreparedPair={
  repository:string;mode:Mode;model:string;agent:string;task:string;sha256:string;
  source_sha256:string;approval_required:boolean;source_transmitted:boolean;
  baseline:PreparedArm;daeloryn:PreparedArm;total_model_calls:number;warning:string;
};
type ArmReceipt={status:string;completed_batches:number;total_batches:number;failure?:string|null;review?:{reply:string}};
type SavedArm={status:string;completed_batches:number;total_batches:number;reply:string;failure?:string|null};
type SavedRun={run_id:string;status:string;repository:string;mode:Mode;model:string;agent:string;created_at:string;updated_at:string;error?:string|null;arms:Record<Arm,SavedArm>;result?:PairResult|null};
type RunSummary=Pick<SavedRun,'run_id'|'status'|'repository'|'mode'|'model'|'agent'|'created_at'|'updated_at'>;
type PairResult={kind:string;status:string;model:string;agent:string;source_sha256:string;
  winner:string;arms:Partial<Record<Arm,ArmReceipt>>;warning:string;
  model_identity_verified:boolean;agent_selection_verified:boolean;
  independent_checks_executed:boolean};

const tasks:Record<Mode,string>={
  review:'Code review · confirmed findings & proposed tests',
  architecture:'Architecture · evidence-backed improvements',
  'fix-plan':'Bug-fix plan · no edits or executed tests'
};
const defaults:Record<Mode,string>={
  review:'java-reviewer',architecture:'java-architect','fix-plan':'java-developer'
};

function safeError(data:unknown,status:number):string{
  if(data&&typeof data==='object'&&'error' in data&&typeof data.error==='string')
    return data.error;
  return 'Request failed ('+status+')';
}

export function BenchmarkRunner({projects,models,agents,enabled,onOpenChat}:{
  projects:Project[];models:string[];agents:Agent[];enabled:boolean;onOpenChat:()=>void;
}){
  const [repository,setRepository]=useState('');
  const [mode,setMode]=useState<Mode>('review');
  const [model,setModel]=useState('');
  const [agent,setAgent]=useState('java-reviewer');
  const [manifest,setManifest]=useState<PreparedPair|null>(null);
  const [approved,setApproved]=useState(false);
  const [busy,setBusy]=useState(false);
  const [running,setRunning]=useState(false);
  const [savedRuns,setSavedRuns]=useState<RunSummary[]>([]);
  const [selectedRunId,setSelectedRunId]=useState('');
  const [runReceipt,setRunReceipt]=useState<SavedRun|null>(null);
  const [historyError,setHistoryError]=useState('');
  const [progress,setProgress]=useState('');
  const [partial,setPartial]=useState<Record<Arm,string>>({baseline:'',daeloryn:''});
  const [result,setResult]=useState<PairResult|null>(null);
  const [assessments,setAssessments]=useState<Record<Arm,Assessment>>(emptyAssessment);
  const [humanChecked,setHumanChecked]=useState(false);
  const [error,setError]=useState('');
  const active=useRef<AbortController|null>(null);
  const inFlight=useRef(false);
  // Deliberately no automatic preparation or execution on model/project changes.
  useEffect(()=>()=>active.current?.abort(),[]);
  // Navigation only stops GET polling. A previously approved run belongs to
  // the backend worker, not this React component or an HTTP response stream.
  useEffect(()=>{
    let mounted=true;
    const update=async()=>{
      try{
        const res=await fetch('/api/benchmark/runs',{cache:'no-store'});
        if(!res.ok)throw new Error('Local benchmark history unavailable');
        const value:unknown=await res.json();
        if(!value||typeof value!=='object'||!('runs' in value)||!Array.isArray(value.runs))
          throw new Error('Invalid benchmark run history');
        if(mounted){
          const rows=value.runs as RunSummary[];
          setSavedRuns(rows);
          setSelectedRunId(previous=>previous||rows[0]?.run_id||'');
          setHistoryError('');
        }
      }catch(e){if(mounted)setHistoryError(e instanceof Error?e.message:'Run history unavailable');}
    };
    void update();
    const timer=window.setInterval(()=>void update(),1800);
    return()=>{mounted=false;window.clearInterval(timer);};
  },[]);
  useEffect(()=>{
    if(!selectedRunId){setRunReceipt(null);return;}
    let mounted=true;
    const update=async()=>{
      try{
        const res=await fetch('/api/benchmark/runs/'+encodeURIComponent(selectedRunId),{cache:'no-store'});
        if(!res.ok)throw new Error('Saved benchmark run unavailable');
        const value=await res.json() as SavedRun;
        if(!value||value.run_id!==selectedRunId||!value.arms)
          throw new Error('Invalid persisted benchmark receipt');
        if(mounted){
          setRunReceipt(value);
          setRunning(value.status==='running');
          setResult(value.result||null);
          setPartial({baseline:value.arms.baseline?.reply||'',daeloryn:value.arms.daeloryn?.reply||''});
          const current=value.arms.daeloryn?.status==='running'?'daeloryn':'baseline';
          const arm=value.arms[current];
          setProgress(value.status==='running'?
            (current==='baseline'?'Plain Copilot':'Copilot + Daeloryn')+
            ' · '+String(arm?.completed_batches??0)+'/'+String(arm?.total_batches??0)+' batches completed':
            'Saved run: '+value.status+(value.error?' · '+value.error:''));
        }
      }catch(e){if(mounted)setHistoryError(e instanceof Error?e.message:'Run receipt unavailable');}
    };
    void update();
    const timer=window.setInterval(()=>void update(),1200);
    return()=>{mounted=false;window.clearInterval(timer);};
  },[selectedRunId]);
  const availableModels=models.filter(m=>m!=='auto');
  const chosenModel=availableModels.includes(model)?model:availableModels[0]||'';
  const selectedAgent=agents.some(a=>a.name===agent)?agent:agents.some(a=>a.name===defaults[mode])?defaults[mode]:agents[0]?.name||'';
  function clear(){
    setManifest(null);setApproved(false);setResult(null);setError('');
    setSelectedRunId('');setRunReceipt(null);
    setPartial({baseline:'',daeloryn:''});setProgress('');
    setAssessments(emptyAssessment());setHumanChecked(false);
  }
  function chooseMode(next:Mode){setMode(next);setAgent(defaults[next]);clear();}
  const selection={repository,mode,model:chosenModel,agent:selectedAgent};
  const canPrepare=Boolean(enabled&&repository&&projects.some(p=>p.name===repository)&&
    chosenModel&&selectedAgent&&!busy&&!inFlight.current&&!savedRuns.some(r=>r.status==='running'));

  async function prepare(){
    if(!canPrepare)return;
    setBusy(true);clear();setProgress('Reading selected local source once for both arms…');
    const controller=new AbortController();active.current=controller;
    try{
      const response=await fetch('/api/benchmark/prepare',{
        method:'POST',signal:controller.signal,
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify(selection)
      });
      const data:unknown=await response.json();
      if(!response.ok)throw new Error(safeError(data,response.status));
      if(!data||typeof data!=='object'||!('sha256' in data)||typeof data.sha256!=='string'||
         !/^[a-f0-9]{64}$/.test(data.sha256)||
         !('source_sha256' in data)||typeof data.source_sha256!=='string'||
         !('repository' in data)||data.repository!==repository||
         !('model' in data)||data.model!==chosenModel||
         !('agent' in data)||data.agent!==selectedAgent||
         !('mode' in data)||data.mode!==mode||
         !('approval_required' in data)||data.approval_required!==true||
         !('total_model_calls' in data)||typeof data.total_model_calls!=='number'||
         !('baseline' in data)||!('daeloryn' in data))
        throw new Error('Invalid benchmark preparation receipt');
      setManifest(data as PreparedPair);
      setProgress('Snapshot prepared. No Copilot calls made.');
    }catch(e){
      if(!controller.signal.aborted)setError(e instanceof Error?e.message:'Preparation failed');
    }finally{setBusy(false);}
  }
  async function execute(){
    if(!manifest||!approved||busy||inFlight.current||savedRuns.some(r=>r.status==='running'))return;
    inFlight.current=true;setBusy(true);setError('');
    setResult(null);setPartial({baseline:'',daeloryn:''});
    setAssessments(emptyAssessment());setHumanChecked(false);
    setProgress('Validating the approved snapshot for a durable local run…');
    try{
      const response=await fetch('/api/benchmark/start',{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify(selectionWithDigest(manifest))
      });
      const data:unknown=await response.json();
      if(!response.ok)throw new Error(safeError(data,response.status));
      if(!data||typeof data!=='object'||!('run_id' in data)||
         typeof data.run_id!=='string'||!/^[a-f0-9]{32}$/.test(data.run_id))
        throw new Error('Invalid persistent benchmark ID');
      setManifest(null);setApproved(false);
      setSelectedRunId(data.run_id);
      setRunning(true);
      setProgress('Approved run '+data.run_id.slice(0,8)+' started; you can leave this page.');
    }catch(e){
      setError('Benchmark start failed: '+(e instanceof Error?e.message:'network failure')+
        '. If the network failed, inspect saved runs before attempting another call.');
      setManifest(null);setApproved(false);
    }finally{inFlight.current=false;setBusy(false);}
  }
  function assessmentResult():string{
    if(!humanChecked||result?.status!=='completed')return 'No reviewed result yet';
    const a=assessments.baseline,b=assessments.daeloryn;
    const valid=(value:Assessment)=>/^(0|[1-9]\d*)$/.test(value.confirmed)&&
      /^(0|[1-9]\d*)$/.test(value.falsePositives)&&Boolean(value.references.trim());
    if(!valid(a)||!valid(b))return 'Enter nonnegative whole counts and supporting file/line references for both arms';
    const bc=Number(a.confirmed),dc=Number(b.confirmed);
    const bf=Number(a.falsePositives),df=Number(b.falsePositives);
    if(dc===bc&&df===bf)return 'Human-assessed tie on entered criteria';
    if(dc>=bc&&df<=bf)return 'Human-assessed pilot advantage: Daeloryn (not independent certification)';
    if(bc>=dc&&bf<=df)return 'Human-assessed pilot advantage: Plain Copilot (not independent certification)';
    return 'Inconclusive: trade-off between confirmed findings and false positives';
  }
  function selectionWithDigest(p:PreparedPair){
    return {repository:p.repository,mode:p.mode,model:p.model,agent:p.agent,approved_sha256:p.sha256};
  }
  return <section className="surface benchmark-runner" aria-label="Paired benchmark runner">
    <div className="surface-head"><div><h2>New A/B benchmark</h2>
      <p>Same source snapshot, task and requested Copilot model. Plain Copilot vs Copilot + trusted Daeloryn agent.</p></div>
      <span className="subtle-tag">READ-ONLY PILOT</span>
    </div>

    <section className="benchmark-history" aria-label="Saved benchmark runs">
      <div className="surface-head"><h3>Saved A/B runs</h3><span className="subtle-tag">LOCAL DISK · PILOT RESULTS</span></div>
      <p className="muted">Approved benchmarks continue on the local API when you change pages. Results persist through browser refresh and backend restart. A run interrupted by a backend restart is marked interrupted, never retried automatically. Provider responses are stored on this computer.</p>
      {historyError&&<p role="alert">{historyError}</p>}
      {savedRuns.length>0?<label>Open saved run
        <select aria-label="Saved benchmark run" value={selectedRunId} onChange={e=>{
          setSelectedRunId(e.target.value);setResult(null);setPartial({baseline:'',daeloryn:''});
          setManifest(null);setApproved(false);setAssessments(emptyAssessment());setHumanChecked(false);
        }}>
          <option value="">Select a saved run</option>
          {savedRuns.map(r=><option key={r.run_id} value={r.run_id}>{r.repository} · {r.mode} · {r.status} · {new Date(r.created_at).toLocaleString()} · {r.run_id.slice(0,8)}</option>)}
        </select>
      </label>:<p>No saved runs yet. Results lost before this feature was installed cannot be reconstructed from discarded browser state.</p>}
      {runReceipt&&<p role="status"><strong>Run {runReceipt.run_id.slice(0,8)} · {runReceipt.status}</strong> · Created {new Date(runReceipt.created_at).toLocaleString()} · Updated {new Date(runReceipt.updated_at).toLocaleString()}</p>}
    </section>
    <div className="benchmark-form">
      <label>Local project
        <select aria-label="Benchmark project" value={repository} disabled={busy} onChange={e=>{setRepository(e.target.value);clear();}}>
          <option value="">Select an approved local checkout</option>
          {projects.map(p=><option key={p.path} value={p.name}>{p.name}</option>)}
        </select>
      </label>
      <label>Same Copilot model for both arms
        <select aria-label="Benchmark model" value={chosenModel} disabled={busy} onChange={e=>{setModel(e.target.value);clear();}}>
          {availableModels.length===0?<option value="">No discovered Copilot models</option>:
            availableModels.map(m=><option key={m} value={m}>{m}</option>)}
        </select>
      </label>
      <label>Type of benchmark
        <select aria-label="Benchmark type" value={mode} disabled={busy} onChange={e=>chooseMode(e.target.value as Mode)}>
          {Object.entries(tasks).map(([k,v])=><option key={k} value={k}>{v}</option>)}
        </select>
      </label>
      <label>Daeloryn specialist
        <select aria-label="Benchmark agent" value={selectedAgent} disabled={busy} onChange={e=>{setAgent(e.target.value);clear();}}>
          {agents.length===0?<option value="">No trusted agents loaded</option>:
            agents.map(a=><option key={a.name} value={a.name}>{a.name}</option>)}
        </select>
      </label>
    </div>
    {!projects.length&&<p role="status">No local projects registered. <button className="text-action" type="button" onClick={onOpenChat}>Open Chat to add one</button>.</p>}
    {!enabled&&<p role="status">Enable Copilot in the local API to run an A/B benchmark.</p>}
    {mode==='fix-plan'&&<p className="muted">Fix-plan mode generates proposals only. Patches, builds and regression tests are not executed; real implementation benchmarking requires an independently isolated worker.</p>}
    {!manifest&&!running&&<button type="button" disabled={!canPrepare} onClick={()=>void prepare()}>{busy?'Preparing…':'Prepare A/B benchmark'}</button>}
    {manifest&&!running&&<div className="benchmark-manifest">
      <p><strong>{manifest.baseline.files.length} eligible files · {manifest.total_model_calls} potentially billable model calls</strong></p>
      <p>Requested model: {manifest.model} · Agent: {manifest.agent}</p>
      <p>Source SHA-256: <code>{manifest.source_sha256}</code></p>
      <p className="muted">{manifest.warning}</p>
      <details><summary>Inspect exact baseline/specialist prompts, source coverage and exclusions</summary>
        <p>Approval SHA-256: <code>{manifest.sha256}</code></p>
        <p>Baseline batches: {manifest.baseline.batch_count} · Daeloryn batches: {manifest.daeloryn.batch_count}</p>
        <p>{manifest.baseline.coverage?.scope}</p>
        <p>Eligible coverage: {manifest.baseline.coverage?.all_eligible_files_included?'All included':'PARTIAL — some sources omitted'}</p>
        <ul>{manifest.baseline.files.map(path=><li key={path}>{path}</li>)}</ul>
        <pre>{JSON.stringify({omitted:manifest.baseline.coverage?.omitted,excluded:manifest.baseline.coverage?.excluded},null,2)}</pre>
        <h3>Baseline prompt</h3><pre>{manifest.baseline.prompt}</pre>
        <h3>Daeloryn prompt & trusted agent</h3><pre>{manifest.daeloryn.agent_profile}</pre>
        <pre>{manifest.daeloryn.prompt}</pre>
      </details>
      <label className="benchmark-approval"><input type="checkbox" checked={approved} onChange={e=>setApproved(e.target.checked)} disabled={busy}/>
        I inspected both exact prompts, model, agent, coverage and potentially billable calls and approve sending this snapshot to Copilot twice.
      </label>
      <div className="benchmark-actions">
        <button type="button" disabled={!approved||busy} onClick={()=>void execute()}>Approve & run A/B</button>
        <button type="button" className="outline-button" disabled={busy} onClick={clear}>Discard preparation</button>
      </div>
    </div>}
    {(busy||runReceipt)&&<p role="status">{progress}</p>}
    {error&&<p role="alert">{error}</p>}
    {(runReceipt||running||result||partial.baseline||partial.daeloryn)&&<div className="benchmark-results">
      <div className="benchmark-columns">
        {(['baseline','daeloryn'] as const).map(arm=><article className="benchmark-arm" key={arm}>
          <h3>{arm==='baseline'?'Plain Copilot':'Copilot + Daeloryn'}</h3>
          <p>{runReceipt?.arms[arm]?runReceipt.arms[arm].status+' · '+runReceipt.arms[arm].completed_batches+'/'+runReceipt.arms[arm].total_batches+' batches':'Pending / in progress'}</p>
          {runReceipt?.arms[arm]?.failure&&<p role="alert">Failure: {runReceipt.arms[arm].failure}</p>}
          <pre>{runReceipt?.arms[arm]?.reply||result?.arms[arm]?.review?.reply||partial[arm]||'No model response yet'}</pre>
        </article>)}
      </div>
      {runReceipt?.error&&<p role="alert">{runReceipt.error}</p>}
      {result&&<div className="benchmark-conclusion">
        <strong>Winner: Not determined</strong>
        <p>{result.warning}</p>
        <p>Model identity independently verified: No · Agent activation independently verified: No · Regression checks executed: No.</p>
        <p>Compare confirmed unique findings, false positives, fix usefulness and source coverage manually before drawing a conclusion.</p>
      </div>}
      {result&&result.status==='completed'&&runReceipt?.mode==='review'&&<section className="benchmark-adjudication" aria-label="Human review of benchmark findings">
        <h3>Optional manual evidence assessment</h3>
        <p className="muted">Check actual file/line evidence and deduplicate root causes first. Enter counts for each arm; this assessment is user-supplied and is not an independently verified trial.</p>
        <div className="benchmark-columns">
          {(['baseline','daeloryn'] as const).map(arm=><div className="benchmark-arm" key={arm}>
            <h3>{arm==='baseline'?'Plain Copilot':'Copilot + Daeloryn'}</h3>
            <label>Confirmed unique defects
              <input aria-label={arm+' confirmed defects'} inputMode="numeric" value={assessments[arm].confirmed} onChange={e=>{setHumanChecked(false);setAssessments(old=>({...old,[arm]:{...old[arm],confirmed:e.target.value}}));}}/>
            </label>
            <label>False positives
              <input aria-label={arm+' false positives'} inputMode="numeric" value={assessments[arm].falsePositives} onChange={e=>{setHumanChecked(false);setAssessments(old=>({...old,[arm]:{...old[arm],falsePositives:e.target.value}}));}}/>
            </label>
            <label>Verified issue IDs and file:line references
              <textarea aria-label={arm+' evidence references'} value={assessments[arm].references} onChange={e=>{setHumanChecked(false);setAssessments(old=>({...old,[arm]:{...old[arm],references:e.target.value}}));}} rows={3}/>
            </label>
          </div>)}
        </div>
        <label className="benchmark-approval"><input type="checkbox" checked={humanChecked} onChange={e=>setHumanChecked(e.target.checked)}/>
          I manually checked source evidence for both arms and the entered counts are my own assessment, not automated verification.
        </label>
        <p role="status"><strong>{assessmentResult()}</strong></p>
      </section>}
    </div>}
    {running&&<p className="muted">Running on the local API. Navigation does not interrupt provider calls. Interrupted or partial outcomes are never automatically retried.</p>}
  </section>;
}
