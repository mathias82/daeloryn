import {useEffect,useRef,useState} from 'react';
import {reviewRequest} from './copilotRequests';
import type {ReviewSelection} from './copilotRequests';

type Manifest = {
  repository:string; model:string; agent:string|null; prompt:string; sha256:string;
  scope:'focused'|'full';estimated_provider_calls?:number;verified_usage_credits?:number|null;
  files:string[]; batch_count:number; warning:string; approval_required:boolean;
  agent_profile:string|null; agent_profile_sha256:string|null;
  coverage?:{all_eligible_files_included:boolean;scope:string;
    omitted:{path:string;reason:string}[];excluded:{path:string;reason:string}[]};
};
type ReviewResult = {review?:{reply?:string};status?:string;completed_batches?:number;
  total_batches?:number;failure?:string;coverage?:{all_eligible_files_included:boolean}};

export function InlineContextReview({selection,onCompleted,onCancelled}:{
  selection:ReviewSelection;onCompleted:(answer:string)=>void;onCancelled:(unknownOutcome:boolean)=>void;
}) {
  const [prepared,setPrepared]=useState<Manifest|null>(null);
  const [approved,setApproved]=useState(false);
  const [busy,setBusy]=useState(true);
  const [executing,setExecuting]=useState(false);
  const [status,setStatus]=useState('Preparing the selected project snapshot…');
  const [partial,setPartial]=useState('');
  const [error,setError]=useState('');
  const [elapsed,setElapsed]=useState(0);
  const active=useRef<AbortController|null>(null);
  useEffect(()=>{
    const controller=new AbortController();
    active.current=controller;
    async function prepare(){
      try{
        const response=await fetch('/api/copilot/review/prepare',{
          method:'POST',signal:controller.signal,headers:{'Content-Type':'application/json'},
          body:JSON.stringify(reviewRequest(selection))
        });
        const data:unknown=await response.json();
        if(!response.ok)throw new Error(data&&typeof data==='object'&&'error' in data&&typeof data.error==='string'?data.error:'Context preparation failed');
        if(!data||typeof data!=='object'||!('sha256' in data)||typeof data.sha256!=='string'||
          !/^[0-9a-f]{64}$/.test(data.sha256)||!('prompt' in data)||typeof data.prompt!=='string'||
          !('repository' in data)||data.repository!==selection.repository||
          !('model' in data)||typeof data.model!=='string'||data.model==='auto'||
          !('scope' in data)||data.scope!==(selection.scope||'full')||
          (selection.model!=='auto'&&data.model!==selection.model)||
          !('agent' in data)||data.agent!==(selection.agent||null)||
          !('files' in data)||!Array.isArray(data.files)||
          !('batch_count' in data)||typeof data.batch_count!=='number'||
          !('warning' in data)||typeof data.warning!=='string'||
          !('approval_required' in data)||data.approval_required!==true)
          throw new Error('Invalid approved source manifest');
        if(!controller.signal.aborted)setPrepared(data as Manifest);
      }catch(e){
        if(!controller.signal.aborted)setError(e instanceof Error?e.message:'Project context unavailable');
      }finally{if(!controller.signal.aborted)setBusy(false);}
    }
    // StrictMode mounts effects twice in development. Defer the read to a
    // microtask so the first (cleaned-up) effect never reaches the API.
    queueMicrotask(()=>{if(!controller.signal.aborted)void prepare();});
    return()=>controller.abort();
  },[selection.repository,selection.task,selection.model,selection.agent,selection.scope]);
  useEffect(()=>()=>{active.current?.abort();},[]);
  useEffect(()=>{
    if(!busy)return;
    const timer=window.setInterval(()=>setElapsed(x=>x+1),1000);
    return()=>window.clearInterval(timer);
  },[busy]);

  async function execute(){
    if(!prepared||!approved||busy)return;
    setExecuting(true);setBusy(true);setError('');setPartial('');
    setStatus('Rechecking the approved source snapshot before the first model call…');
    setElapsed(0);
    const controller=new AbortController();active.current=controller;
    const timer=window.setTimeout(()=>controller.abort(),420000);
    try{
      const approvedSelection={...selection,model:prepared.model};
      const response=await fetch('/api/copilot/review/execute',{
        method:'POST',signal:controller.signal,
        headers:{'Content-Type':'application/json','Accept':'application/x-ndjson'},
        body:JSON.stringify(reviewRequest(approvedSelection,prepared.sha256))
      });
      if(!response.ok)throw new Error('Approval expired, project changed, or provider unavailable ('+response.status+'). No automatic retry.');
      let data:unknown;
      if(response.headers.get('content-type')?.includes('application/x-ndjson')){
        if(!response.body)throw new Error('Review response stream unavailable');
        const reader=response.body.getReader(),decoder=new TextDecoder();
        let pending='';
        function processLine(line:string){
          if(!line.trim())return;
          const event=JSON.parse(line) as Record<string,unknown>;
          if(event.type==='progress'){
            const completed=typeof event.completed==='number'?event.completed:0;
            const total=typeof event.total==='number'?event.total:prepared!.batch_count;
            setStatus(String(completed)+'/'+String(total)+' batches completed · '+(event.phase==='running'?'Processing batch '+String(event.batch):'Batch '+String(event.batch)+' received'));
          }else if(event.type==='batch_reply'&&typeof event.reply==='string'&&typeof event.batch==='number'){
            const heading=prepared!.batch_count>1?'Batch '+String(event.batch)+':\n':'';
            setPartial(previous=>previous+(previous?'\n\n':'')+heading+event.reply);
          }else if(event.type==='result')data=event.result;
          else if(event.type==='error')throw new Error(typeof event.error==='string'?event.error:'Review stream interrupted');
        }
        while(true){
          const {value,done}=await reader.read();
          pending+=decoder.decode(value,{stream:!done});
          const lines=pending.split('\n');pending=lines.pop()||'';
          for(const line of lines)processLine(line);
          if(done){processLine(pending);break;}
        }
        if(!data)throw new Error('Stream ended before final receipt. External outcome may be unknown; do not retry automatically.');
      }else data=await response.json();
      if(!data||typeof data!=='object'||!('review' in data)||
        !data.review||typeof data.review!=='object'||!('reply' in data.review)||
        typeof data.review.reply!=='string')throw new Error('Invalid final review receipt');
      const receipt=data as ReviewResult;
      const summary=(prepared.scope==='focused'?'Focused source answer: ':'Full source review: ')+(receipt.status||'unknown')+' · '+String(receipt.completed_batches??0)+'/'+String(receipt.total_batches??prepared.batch_count)+
        ' batches. Eligible source coverage: '+(receipt.coverage?.all_eligible_files_included===true?'all included':'partial or see exclusions')+
        (receipt.failure?'\n'+receipt.failure:'')+'\n\n'+(receipt.review?.reply||'(No reply received)');
      onCompleted(summary);
    }catch(e){
      setApproved(false);setPrepared(null);
      setError('Review interrupted: '+(e instanceof Error?e.message:'network failure')+'. External outcome may be unknown; do not automatically retry.');
    }finally{window.clearTimeout(timer);setBusy(false);setExecuting(false);}
  }
  return <section className="surface inline-context-review" aria-label="Chat project context approval">
    <h3>{selection.scope==='focused'?'Focused project context':'Full project review'} · {selection.repository}</h3>
    <p className="muted">{selection.scope==='focused'?'Only relevant filename-matched excerpts and top-level build documentation are prepared. This is not full-project coverage.':'All eligible project sources are prepared within explicit safety limits.'} You approve source transmission before any model calls. No edits, commands or tests.</p>
    {busy&&<p role="status">{status} · {elapsed}s elapsed</p>}
    {prepared&&!executing&&<div>
      <p><strong>{prepared.files.length} source files · {prepared.batch_count} potentially billable model calls</strong> · {prepared.model}</p>
      <p className="muted">Estimated AI Credit charge: unavailable (model-dependent). Actual verified credits: {typeof prepared.verified_usage_credits==='number'?String(prepared.verified_usage_credits):'not supplied by Copilot CLI'}. The batch count is exact; no currency estimate is fabricated.</p>
      <p className="muted">{prepared.warning}</p>
      {prepared.coverage?.all_eligible_files_included===false&&<p role="status">{selection.scope==='focused'?'Focused selection only. Other files were not inspected.':'Partial coverage: some eligible files were omitted.'}</p>}
      <details><summary>Inspect exact source, approval SHA-256 and exclusions</summary>
        <p>SHA-256: <code>{prepared.sha256}</code></p>
        <p>{prepared.coverage?.scope||'Selected local project'}</p>
        <ul>{prepared.files.map(f=><li key={f}>{f}</li>)}</ul>
        <pre style={{whiteSpace:'pre-wrap',maxHeight:240,overflowY:'auto'}}>{JSON.stringify({omitted:prepared.coverage?.omitted,excluded:prepared.coverage?.excluded},null,2)}</pre>
        {prepared.agent_profile&&<pre style={{whiteSpace:'pre-wrap',maxHeight:240,overflowY:'auto'}}>{prepared.agent_profile}</pre>}
        <pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere',maxHeight:300,overflowY:'auto'}}>{prepared.prompt}</pre>
      </details>
      <label><input type="checkbox" checked={approved} disabled={busy} onChange={e=>setApproved(e.target.checked)}/> I inspected the exact source context, model, agent and call count, and approve sending them to Copilot.</label>
      <button type="button" disabled={!approved||busy} onClick={()=>void execute()}>Approve and analyze project</button>
    </div>}
    {partial&&<div className="inline-context-partial"><strong>Completed batch results (live)</strong><p style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{partial}</p></div>}
    {error&&<p role="alert">{error}</p>}
    <button type="button" className="outline-button" onClick={()=>{active.current?.abort();onCancelled(executing);}}>
      {executing?'Stop review (outcome may be unknown)':'Cancel project review'}
    </button>
  </section>;
}
