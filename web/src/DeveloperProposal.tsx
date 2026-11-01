import type {DeveloperPatch} from './DeveloperPatch';
import React,{useState} from 'react';
type Input={repository:string;model:string;findings:string;path?:string};
export function DeveloperProposal({input,onClose,onProposal}:{input:Input;onClose:()=>void;onProposal?:(patch:DeveloperPatch)=>void}){
 const [path,setPath]=useState(input.path||''),[approved,setApproved]=useState(false),[busy,setBusy]=useState(false);
 const [prepared,setPrepared]=useState<{sha256:string;prompt:string;agent:string;agent_profile:string}|null>(null);
 const [patch,setPatch]=useState<DeveloperPatch|null>(null),[applyEnabled,setApplyEnabled]=useState(false),[applyApproved,setApplyApproved]=useState(false),[applied,setApplied]=useState(false);
 const [branch,setBranch]=useState('daeloryn/fix-'+Date.now());
 const [error,setError]=useState(''),[result,setResult]=useState('');
 async function run(execute:boolean){
  if(busy||execute&&(!prepared||!approved))return;
  setBusy(true);setError('');setPatch(null);setApplyApproved(false);setApplied(false);
  const controller=new AbortController(),timer=window.setTimeout(()=>controller.abort(),110000);
  try{
   const response=await fetch('/api/copilot/developer/'+(execute?'execute':'prepare'),{method:'POST',signal:controller.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({repository:input.repository,model:input.model,findings:input.findings,path,...(execute?{approved_sha256:prepared!.sha256}:{})})});
   const data=await response.json();if(!response.ok)throw new Error(data.error||'Developer unavailable');
   if(execute){if(data.status==='proposed'&&typeof data.replacement==='string'&&typeof data.original==='string'){const proposed={repository:input.repository,path,original:data.original,replacement:data.replacement,diff:data.patch.diff,sha256:data.patch.sha256};setPatch(proposed);setApplyEnabled(data.patch_apply_enabled===true);onProposal?.(proposed);}setResult(data.status==='no_change'?'Developer proposed no change.':data.patch.diff);setPrepared(null);setApproved(false);}
   else{setPrepared(data);setApproved(false);}
  }catch(e){setError((e instanceof Error?e.message:'Request failed')+(execute?' External outcome may be unknown; do not automatically retry.':''));if(execute){setPrepared(null);setApproved(false);}}
  finally{window.clearTimeout(timer);setBusy(false);}
 }
 async function applyPatch(){
  if(!patch||!applyApproved||!applyEnabled||busy||applied)return;
  setBusy(true);setError('');
  try{
   const response=await fetch('/api/patch/apply',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({repository:patch.repository,path:patch.path,replacement:patch.replacement,approved_sha256:patch.sha256,branch,approved:true})});
   const data=await response.json();if(!response.ok)throw new Error(data.error||'Patch not applied');
   if(data.applied!==true)throw new Error('No application receipt; inspect local Git state before retrying');
   setApplied(true);onProposal?.({...patch,applied:true});setApplyApproved(false);setResult('Applied to '+data.branch+'. Tests have not run. Review the local Git diff.');
  }catch(e){setError((e instanceof Error?e.message:'Connection failed')+'. Inspect local Git state before retrying.');setApplyApproved(false);}
  finally{setBusy(false);}
 }
 return <section className="surface" aria-label="Reviewer to developer proposal"><h3>Reviewer → developer → proposed patch</h3>
 <p>Project: {input.repository} · Model: {input.model}. Select one file supported by the review evidence. Generation proposes changes only; applying requires separate approval. Findings are model claims requiring human review.</p>
 <label>Reviewed file path<input value={path} disabled={busy} onChange={e=>{setPath(e.target.value);setPrepared(null);setApproved(false);setResult('');setPatch(null);setApplyApproved(false);setApplied(false);}} placeholder="src/main/java/example/App.java"/></label>
 <button disabled={busy||!path} onClick={()=>void run(false)}>Prepare developer handoff</button>
 {prepared&&<><p>{prepared.agent} · 1 potentially billable call</p><details><summary>Inspect exact developer context and profile</summary><pre style={{whiteSpace:'pre-wrap'}}>{prepared.prompt+'\n'+prepared.agent_profile}</pre></details>
 <label><input type="checkbox" checked={approved} disabled={busy} onChange={e=>setApproved(e.target.checked)}/> Approve this source, findings, developer and model</label>
 <button disabled={busy||!approved} onClick={()=>void run(true)}>Generate proposed patch</button></>}
 {busy&&<p role="status">Working on developer handoff…</p>}{error&&<p role="alert">{error}</p>}
 {patch&&<section aria-label="Proposed source code"><div className="inspector-suggestion-grid"><label>Original source<pre>{patch.original}</pre></label><label>Proposed source<pre>{patch.replacement}</pre></label></div><button type="button" onClick={()=>void navigator.clipboard.writeText(patch.replacement).catch(()=>setError('Clipboard unavailable'))}>Copy proposed source</button>
 {!applied&&<><p>Application changes this one file on a new branch. The checkout must be clean. No commit, push or tests.</p>{!applyEnabled&&<p>Restart with --enable-patch-apply to enable local application.</p>}
 <label>New patch branch<input disabled={busy} value={branch} onChange={e=>{setBranch(e.target.value);setApplyApproved(false);}}/></label>
 <label><input type="checkbox" disabled={!applyEnabled||busy} checked={applyApproved} onChange={e=>setApplyApproved(e.target.checked)}/> I reviewed this exact diff and approve writing it on the new branch</label>
 <button type="button" disabled={!applyEnabled||!applyApproved||busy} onClick={()=>void applyPatch()}>Apply approved patch locally</button></>}</section>}
 {result&&<><p>{applied?'Applied locally; tests have not run.':'Proposal only. Review before applying; tests have not run.'}</p><pre style={{whiteSpace:'pre-wrap'}}>{result}</pre></>}
 <button disabled={busy} onClick={onClose}>Close developer handoff</button></section>;
}
