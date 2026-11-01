import React,{useState} from 'react';
type Input={repository:string;model:string;findings:string};
export function DeveloperProposal({input,onClose}:{input:Input;onClose:()=>void}){
 const [path,setPath]=useState(''),[approved,setApproved]=useState(false),[busy,setBusy]=useState(false);
 const [prepared,setPrepared]=useState<{sha256:string;prompt:string;agent:string;agent_profile:string}|null>(null);
 const [error,setError]=useState(''),[result,setResult]=useState('');
 async function run(execute:boolean){
  if(busy||execute&&(!prepared||!approved))return;
  setBusy(true);setError('');
  const controller=new AbortController(),timer=window.setTimeout(()=>controller.abort(),110000);
  try{
   const response=await fetch('/api/copilot/developer/'+(execute?'execute':'prepare'),{method:'POST',signal:controller.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({...input,path,...(execute?{approved_sha256:prepared!.sha256}:{})})});
   const data=await response.json();if(!response.ok)throw new Error(data.error||'Developer unavailable');
   if(execute){setResult(data.status==='no_change'?'Developer proposed no change.':data.patch.diff);setPrepared(null);setApproved(false);}
   else{setPrepared(data);setApproved(false);}
  }catch(e){setError((e instanceof Error?e.message:'Request failed')+(execute?' External outcome may be unknown; do not automatically retry.':''));if(execute){setPrepared(null);setApproved(false);}}
  finally{window.clearTimeout(timer);setBusy(false);}
 }
 return <section className="surface" aria-label="Reviewer to developer proposal"><h3>Reviewer → developer → proposed patch</h3>
 <p>Project: {input.repository} · Model: {input.model}. Select one file supported by the review evidence. No writes or tests. Findings are model claims requiring human review.</p>
 <label>Reviewed file path<input value={path} disabled={busy} onChange={e=>{setPath(e.target.value);setPrepared(null);setApproved(false);setResult('');}} placeholder="src/main/java/example/App.java"/></label>
 <button disabled={busy||!path} onClick={()=>void run(false)}>Prepare developer handoff</button>
 {prepared&&<><p>{prepared.agent} · 1 potentially billable call</p><details><summary>Inspect exact developer context and profile</summary><pre style={{whiteSpace:'pre-wrap'}}>{prepared.prompt+'\n'+prepared.agent_profile}</pre></details>
 <label><input type="checkbox" checked={approved} disabled={busy} onChange={e=>setApproved(e.target.checked)}/> Approve this source, findings, developer and model</label>
 <button disabled={busy||!approved} onClick={()=>void run(true)}>Generate proposed patch</button></>}
 {busy&&<p role="status">Working on developer handoff…</p>}{error&&<p role="alert">{error}</p>}
 {result&&<><p>Proposal only. Review before applying; tests have not run.</p><pre style={{whiteSpace:'pre-wrap'}}>{result}</pre></>}
 <button disabled={busy} onClick={onClose}>Close developer handoff</button></section>;
}
