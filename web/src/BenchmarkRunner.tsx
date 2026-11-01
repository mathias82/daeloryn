import {useEffect,useRef,useState} from 'react';

type Agent={name:string;scope:string;description:string};
type Project={name:string;path:string;technologies:string[]};
type Mode='review'|'architecture'|'fix-plan';
type Arm='baseline'|'daeloryn';
type Coverage={scope:string;all_eligible_files_included:boolean;omitted:{path:string;reason:string}[];excluded:{path:string;reason:string}[]};
type PreparedArm={sha256:string;prompt:string;files:string[];batch_count:number;agent:string|null;agent_profile:string|null;coverage:Coverage};
type PreparedPair={
  repository:string;mode:Mode;model:string;agent:string;task:string;sha256:string;
  source_sha256:string;approval_required:boolean;source_transmitted:boolean;
  baseline:PreparedArm;daeloryn:PreparedArm;total_model_calls:number;warning:string;
};
type ArmReceipt={status:string;completed_batches:number;total_batches:number;failure?:string|null;review:{reply:string}};
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
  const [progress,setProgress]=useState('');
  const [partial,setPartial]=useState<Record<Arm,string>>({baseline:'',daeloryn:''});
  const [result,setResult]=useState<PairResult|null>(null);
  const [error,setError]=useState('');
  const active=useRef<AbortController|null>(null);
  const inFlight=useRef(false);
  // Deliberately no automatic preparation or execution on model/project changes.
  useEffect(()=>()=>active.current?.abort(),[]);
  const availableModels=models.filter(m=>m!=='auto');
  const chosenModel=availableModels.includes(model)?model:availableModels[0]||'';
  const selectedAgent=agents.some(a=>a.name===agent)?agent:agents.some(a=>a.name===defaults[mode])?defaults[mode]:agents[0]?.name||'';
  function clear(){
    setManifest(null);setApproved(false);setResult(null);setError('');
    setPartial({baseline:'',daeloryn:''});setProgress('');
  }
  function chooseMode(next:Mode){setMode(next);setAgent(defaults[next]);clear();}
  const selection={repository,mode,model:chosenModel,agent:selectedAgent};
  const canPrepare=Boolean(enabled&&repository&&projects.some(p=>p.name===repository)&&
    chosenModel&&selectedAgent&&!busy&&!inFlight.current);

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
    if(!manifest||!approved||busy||inFlight.current)return;
    inFlight.current=true;setBusy(true);setRunning(true);setError('');
    setResult(null);setPartial({baseline:'',daeloryn:''});
    setProgress('Validating approved snapshot before first model call…');
    const controller=new AbortController();active.current=controller;
    // Two review arms, each up to 300 seconds between calls plus one active call.
    const timeout=window.setTimeout(()=>controller.abort(),900000);
    try{
      const response=await fetch('/api/benchmark/execute',{
        method:'POST',signal:controller.signal,
        headers:{'Content-Type':'application/json','Accept':'application/x-ndjson'},
        body:JSON.stringify(selectionWithDigest(manifest))
      });
      if(!response.ok){
        let detail:unknown=null;
        try{detail=await response.json();}catch{/* non-JSON failure */}
        throw new Error(safeError(detail,response.status));
      }
      if(!response.body||!response.headers.get('content-type')?.includes('application/x-ndjson'))
        throw new Error('Expected a streamed benchmark response');
      const reader=response.body.getReader(),decoder=new TextDecoder();
      let pending='',complete:PairResult|null=null;
      function process(line:string){
        if(!line.trim())return;
        const event=JSON.parse(line) as Record<string,unknown>;
        const arm=event.arm==='baseline'||event.arm==='daeloryn'?event.arm:null;
        if(event.type==='arm_started'&&arm)setProgress((arm==='baseline'?'Plain Copilot':'Copilot + Daeloryn')+' · started');
        if(event.type==='progress'&&arm)
          setProgress((arm==='baseline'?'Plain Copilot':'Copilot + Daeloryn')+
            ' · '+String(event.completed)+'/'+String(event.total)+' batches completed');
        if(event.type==='batch_reply'&&arm&&typeof event.reply==='string'){
          const number=typeof event.batch==='number'?event.batch:0;
          setPartial(previous=>({...previous,[arm]:previous[arm]+
            (previous[arm]?'\n\n':'')+'Batch '+number+':\n'+event.reply}));
        }
        if(event.type==='arm_finished'&&arm)
          setProgress((arm==='baseline'?'Plain Copilot':'Copilot + Daeloryn')+
            ' · '+String(event.status));
        if(event.type==='result'&&event.result&&typeof event.result==='object')
          complete=event.result as PairResult;
        if(event.type==='error')throw new Error(typeof event.error==='string'?event.error:'Benchmark interrupted');
      }
      while(true){
        const {value,done}=await reader.read();
        pending+=decoder.decode(value,{stream:!done});
        const lines=pending.split('\n');pending=lines.pop()||'';
        for(const line of lines)process(line);
        if(done){process(pending);break;}
      }
      if(!complete||complete.kind!=='paired-source-review-observation'||
        !complete.arms||!complete.warning)
        throw new Error('Stream ended without a valid final comparison; outcome may be unknown');
      setResult(complete);
      setProgress(complete.status==='completed'?'Both model arms returned. Human review needed.':
        'Partial run. Do not automatically retry unknown outcomes.');
      setManifest(null);setApproved(false);
    }catch(e){
      setError('Benchmark interrupted: '+(e instanceof Error?e.message:'connection failure')+
        '. External outcome may be unknown; do not retry automatically.');
      setManifest(null);setApproved(false);
    }finally{
      window.clearTimeout(timeout);inFlight.current=false;
      setBusy(false);setRunning(false);
    }
  }
  function selectionWithDigest(p:PreparedPair){
    return {repository:p.repository,mode:p.mode,model:p.model,agent:p.agent,approved_sha256:p.sha256};
  }
  return <section className="surface benchmark-runner" aria-label="Paired benchmark runner">
    <div className="surface-head"><div><h2>New A/B benchmark</h2>
      <p>Same source snapshot, task and requested Copilot model. Plain Copilot vs Copilot + trusted Daeloryn agent.</p></div>
      <span className="subtle-tag">READ-ONLY PILOT</span>
    </div>
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
    {busy&&<p role="status">{progress}</p>}
    {error&&<p role="alert">{error}</p>}
    {(running||result||partial.baseline||partial.daeloryn)&&<div className="benchmark-results">
      <div className="benchmark-columns">
        {(['baseline','daeloryn'] as const).map(arm=><article className="benchmark-arm" key={arm}>
          <h3>{arm==='baseline'?'Plain Copilot':'Copilot + Daeloryn'}</h3>
          <p>{result?.arms[arm]?result.arms[arm]?.status:'Pending / in progress'}</p>
          <pre>{result?.arms[arm]?.review?.reply||partial[arm]||'No model response yet'}</pre>
        </article>)}
      </div>
      {result&&<div className="benchmark-conclusion">
        <strong>Winner: Not determined</strong>
        <p>{result.warning}</p>
        <p>Model identity independently verified: No · Agent activation independently verified: No · Regression checks executed: No.</p>
        <p>Compare confirmed unique findings, false positives, fix usefulness and source coverage manually before drawing a conclusion.</p>
      </div>}
    </div>}
    {running&&<button className="outline-button" type="button" onClick={()=>{active.current?.abort();setProgress('Stopping observation; an in-flight remote call may have unknown outcome.');}}>Stop observing (no auto retry)</button>}
  </section>;
}
