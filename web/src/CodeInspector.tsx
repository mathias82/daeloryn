import {useEffect,useMemo,useRef,useState} from 'react';
import {nearbyDeclaration,sourcePreview} from './sourceInspector';
import {draftPatch,startSuggestion} from './suggestionDraft';
import type {SuggestionDraft} from './suggestionDraft';
import type {InspectorSnapshot} from './sourceInspector';

/** Read-only navigation over the exact, approved code snapshot. */
export function CodeInspector({snapshot,onClose}:{
  snapshot:InspectorSnapshot;onClose:()=>void;
}){
  const files=useMemo(()=>[...new Set(snapshot.sources.map(s=>s.file))],[snapshot.sources]);
  const [file,setFile]=useState('');
  const [line,setLine]=useState(1);
  const [expanded,setExpanded]=useState(false);
  const [lineInput,setLineInput]=useState('1');
  const [editMode,setEditMode]=useState(false);
  const [draft,setDraft]=useState<SuggestionDraft|null>(null);
  const [draftMessage,setDraftMessage]=useState('');
  const [branch,setBranch]=useState(()=>('daeloryn/fix-'+Date.now().toString(36)));
  const [applyConfirmed,setApplyConfirmed]=useState(false);
  const [applyBusy,setApplyBusy]=useState(false);
  const [applied,setApplied]=useState<{branch:string;file:string;tests_executed:boolean}|null>(null);
  const [suite,setSuite]=useState('maven');
  const [testsApproved,setTestsApproved]=useState(false);
  const [testsBusy,setTestsBusy]=useState(false);
  const [testOutcome,setTestOutcome]=useState<{suite:string;verified:boolean;returncode:number;output:string}|null>(null);
  const [fullSource,setFullSource]=useState<{file:string;lines:string[];redacted_lines:number[];line_count:number;source_sha256:string}|null>(null);
  const [sourceLoading,setSourceLoading]=useState(false);
  const [sourceError,setSourceError]=useState('');
  const markedRef=useRef<HTMLDivElement|null>(null);
  const selected=files.includes(file)?file:files[0]||'';
  const visibleCount=expanded?180:42;
  const preview=useMemo(()=>fullSource?.file===selected?
    fullSource.lines.map((text,index)=>({line:index+1,text})):
    sourcePreview(snapshot.sources,selected,line,visibleCount),
    [fullSource,snapshot.sources,selected,line,visibleCount]);
  const valid=snapshot.references.filter(r=>r.verified);
  const unverified=snapshot.references.filter(r=>!r.verified);
  const marks=valid.filter(r=>r.file===selected);
  const focused=snapshot.navigation?.file===selected?snapshot.navigation:null;
  const focusRanges=focused?.ranges||[];
  const active=marks.find(r=>line>=r.line&&line<=r.endLine);
  const patch=draft&&draft.snapshotSha256===snapshot.sha256?draftPatch(draft):null;
  const matchingSuggestion=active&&draft&&draft.file===active.file&&draft.start===active.line&&draft.end===active.endLine
    ? active.suggestionText : undefined;
  function beginSuggestion(){
    const start=active?.line??line,end=active?.endLine??line;
    const proposal=startSuggestion(snapshot.sources,selected,start,end,snapshot.sha256);
    if(!proposal){setDraftMessage('The selected source lines were not available completely in the approved snapshot. Select another line.');return;}
    setDraft(proposal);setEditMode(true);setDraftMessage('');setApplyConfirmed(false);
  }
  async function copyPatch(){
    if(!patch)return;
    try{
      await navigator.clipboard.writeText(patch);
      setDraftMessage('Patch copied. No files were modified. Review and apply it manually after checking tests.');
    }catch{setDraftMessage('Clipboard permission unavailable. Select and copy the diff manually.');}
  }

  async function applyApprovedPatch(){
    const access=snapshot.sourceAccess;
    if(!access||!draft||!patch||!fullSource||draft.file!==fullSource.file||
      !applyConfirmed||applyBusy||applied||!/^daeloryn\/[a-z0-9][a-z0-9-]{0,50}$/.test(branch))return;
    setApplyBusy(true);setDraftMessage('');
    try{
      const response=await fetch('/api/copilot/review/patch/apply',{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({...access,file:draft.file,start:draft.start,end:draft.end,
          original:draft.original,replacement:draft.replacement,
          source_sha256:fullSource.source_sha256,branch,approved:true})
      });
      const value=await response.json() as {status?:string;branch?:string;file?:string;tests_executed?:boolean;error?:string};
      if(!response.ok)throw new Error(value.error||'Local write refused ('+response.status+')');
      if(value.status!=='applied'||value.branch!==branch||value.file!==draft.file)
        throw new Error('Invalid local patch receipt');
      setApplied({branch,file:draft.file,tests_executed:false});
      setApplyConfirmed(false);
      setDraftMessage('Approved patch applied to '+branch+'. No tests, commits or PRs were made. This review snapshot is now stale.');
    }catch(error){setDraftMessage(error instanceof Error?error.message:'Patch could not be applied');}
    finally{setApplyBusy(false);}
  }
  async function runApprovedTests(){
    if(!applied||!testsApproved||testsBusy)return;
    setTestsBusy(true);setDraftMessage('');
    try{
      const response=await fetch('/api/copilot/review/tests',{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({repository:snapshot.repository,branch:applied.branch,suite,approved:true})
      });
      const value=await response.json() as {verified?:boolean;suite?:string;returncode?:number;output?:string;error?:string};
      if(!response.ok)throw new Error(value.error||'Test execution refused ('+response.status+')');
      if(typeof value.verified!=='boolean'||typeof value.output!=='string'||
        typeof value.returncode!=='number'||value.suite!==suite)
        throw new Error('Invalid test result');
      setTestOutcome({verified:value.verified,suite,returncode:value.returncode,output:value.output});
      setDraftMessage(value.verified?'Approved host tests passed. Review the branch before a commit.':
        'Approved tests failed. Inspect the output; no commit or PR was created.');
    }catch(error){setDraftMessage(error instanceof Error?error.message:'Tests could not start');}
    finally{setTestsBusy(false);setTestsApproved(false);}
  }

  useEffect(()=>{setFile(files[0]||'');setLine(1);setLineInput('1');setDraft(null);setEditMode(false);setDraftMessage('');setApplied(null);setApplyConfirmed(false);},
    [snapshot.sha256,files[0]]);
  useEffect(()=>{
    const nav=snapshot.navigation;
    if(nav&&files.includes(nav.file)&&Number.isSafeInteger(nav.line)&&nav.line>0){
      setFile(nav.file);setLine(nav.line);setLineInput(String(nav.line));
    }
  },[snapshot.navigation?.revision]);
  useEffect(()=>{
    const selection=snapshot.sourceAccess;
    if(!selection||!selected){setFullSource(null);setSourceError('');return;}
    const controller=new AbortController();
    setFullSource(null);setSourceLoading(true);setSourceError('');
    async function openApprovedClass(){
      try{
        const response=await fetch('/api/copilot/review/source',{
          method:'POST',signal:controller.signal,
          headers:{'Content-Type':'application/json'},
          body:JSON.stringify({...selection,file:selected})
        });
        const data:unknown=await response.json();
        if(!response.ok){
          const detail=data&&typeof data==='object'&&'error' in data&&
            typeof data.error==='string'?data.error:'Source view unavailable ('+response.status+')';
          throw new Error(detail);
        }
        if(!data||typeof data!=='object'||!('file' in data)||data.file!==selected||
            !('source_sha256' in data)||typeof data.source_sha256!=='string'||
            !('lines' in data)||!Array.isArray(data.lines)||
            !data.lines.every((line:unknown)=>typeof line==='string')||
            !('redacted_lines' in data)||!Array.isArray(data.redacted_lines)||
            !data.redacted_lines.every((n:unknown)=>Number.isSafeInteger(n))||
            !('line_count' in data)||typeof data.line_count!=='number'||
            !('local_only' in data)||data.local_only!==true||
            !('model_calls' in data)||data.model_calls!==0)
          throw new Error('Invalid local source preview response');
        if(!controller.signal.aborted)
          setFullSource(data as unknown as {file:string;lines:string[];redacted_lines:number[];line_count:number;source_sha256:string});
      }catch(e){
        if(!controller.signal.aborted)
          setSourceError('Full-class preview unavailable: '+(e instanceof Error?e.message:'unknown error')+
            '. Only approved review excerpts are shown.');
      }finally{if(!controller.signal.aborted)setSourceLoading(false);}
    }
    void openApprovedClass();
    return()=>controller.abort();
  },[selected,snapshot.sha256,snapshot.sourceAccess?.approved_sha256]);
  useEffect(()=>{
    if(!expanded)return;
    const onKey=(event:KeyboardEvent)=>{if(event.key==='Escape')setExpanded(false);};
    window.addEventListener('keydown',onKey);
    return()=>window.removeEventListener('keydown',onKey);
  },[expanded]);
  useEffect(()=>{markedRef.current?.scrollIntoView({block:'center',behavior:'instant'});},
    [line,selected,expanded,fullSource]);
  function jump(path:string,at:number){
    if(!files.includes(path)||!Number.isSafeInteger(at)||at<1)return;
    setFile(path);setLine(at);setLineInput(String(at));
  }
  function moveWindow(offset:number){
    const next=Math.max(1,line+offset);
    jump(selected,next);
  }
  return <aside className={'code-inspector'+(expanded?' code-inspector-fullscreen':'')}
    role={expanded?'dialog':'complementary'}
    aria-label="Code Inspector" aria-modal={expanded||undefined}>
    <header className="inspector-header">
      <div><strong>Code Inspector</strong><small>{snapshot.repository} · approved read-only source</small></div>
      <div className="inspector-header-actions">
        <button type="button" className="outline-button" aria-label={editMode?'Inspect mode':'Edit suggestion mode'}
          aria-pressed={editMode} onClick={()=>{if(editMode){setEditMode(false);}else{beginSuggestion();}}}>
          {editMode?'Inspect mode':'Edit suggestion'}
        </button>
        <button type="button" className="outline-button" aria-label={expanded?'Exit full screen Code Inspector':'Full screen Code Inspector'}
          onClick={()=>setExpanded(v=>!v)}>{expanded?'Exit full screen':'Full screen'}</button>
        <button type="button" className="outline-button" aria-label="Close Code Inspector" onClick={onClose}>×</button>
      </div>
    </header>
    <div className="inspector-progress" role="status">
      <span>{snapshot.status}</span><span>{snapshot.completed}/{snapshot.total} batches</span>
    </div>
    <div className="inspector-findings">
      <strong>Model-highlighted findings and suggested changes</strong>
      <p className="muted">Highlighted lines are cited by the model and located in the approved snapshot. They are not confirmed bugs or approved edits.</p>
      {valid.length===0&&<p className="muted">No matching file:line references yet. References appear when a batch finishes.</p>}
      {valid.map((r,i)=><button className={'inspector-ref'+(active===r?' inspector-ref-active':'')} type="button"
        key={r.batch+'|'+r.file+'|'+r.line+'|'+i}
        onClick={()=>jump(r.file,r.line)}>
        <span>{r.file}:{r.line}{r.endLine>r.line?'-'+r.endLine:''}</span>
        <small>Batch {r.batch} · {r.kind==='bug'?'Model-reported bug':r.kind==='change'?'Suggested change':'Cited source'} · source line located</small>
        <span className="inspector-excerpt">{r.excerpt}</span>
      </button>)}
      {unverified.length>0&&<details className="inspector-unverified">
        <summary>{unverified.length} unverified references (not navigable)</summary>
        {unverified.map((r,i)=><p key={r.file+'|'+i}>{r.file}:{r.line} · batch {r.batch} · no matching line in snapshot</p>)}
      </details>}
    </div>
    <div className="inspector-source">
      <label>Inspected file
        <select aria-label="Inspected source file" value={selected}
          onChange={event=>jump(event.target.value,1)}>
          {files.map(f=><option key={f} value={f}>{f}</option>)}
        </select>
      </label>
      {selected&&<>
        <div className="inspector-source-caption">
          <strong>{selected}</strong>
          <small>{fullSource?.file===selected?'Full class/file · '+fullSource.line_count+' lines · local only · 0 model calls':
            nearbyDeclaration(snapshot.sources,selected,line)||'Approved source excerpt · original line numbers'}</small>
        </div>
        {(active||focused)&&<p className="inspector-target-note" role="status">
          Highlighted: {active?.kind==='bug'?'possible bug':active?.kind==='change'?'suggested method/code change':'model-cited source'}
          {' · '}line {focused?.line??active?.line}{(focused?.endLine??active?.endLine??0)>(focused?.line??active?.line??0)?'–'+(focused?.endLine??active?.endLine):''}
          {' · '}not independently verified
        </p>}
        <div className="inspector-source-actions">
          <button type="button" className="outline-button" onClick={()=>moveWindow(-visibleCount)}
            aria-label="Previous source lines">Previous lines</button>
          <label>Go to line
            <input aria-label="Go to source line" type="number" min="1" value={lineInput}
              onChange={e=>setLineInput(e.target.value)}
              onKeyDown={e=>{if(e.key==='Enter')jump(selected,Number(lineInput));}}/>
          </label>
          <button type="button" className="outline-button"
            onClick={()=>jump(selected,Number(lineInput))}>Go</button>
          <button type="button" className="outline-button" onClick={()=>moveWindow(visibleCount)}
            aria-label="Next source lines">Next lines</button>
        </div>
        {sourceLoading&&<p className="inspector-source-loading" role="status">Loading entire class locally (no provider call)…</p>}
        {sourceError&&<p role="alert" className="inspector-source-error">{sourceError}</p>}
        <div className="inspector-code" role="region" aria-label={fullSource?.file===selected?'Full local source file':'Read-only source excerpt'}>
          {preview.length?preview.map((row,index)=>{
            const cites=marks.filter(r=>row.line>=r.line&&row.line<=r.endLine);
            const focusedCite=focusRanges.some(r=>row.line>=r.line&&row.line<=r.endLine);
            const isCurrent=row.line===line;
            const isCited=cites.length>0||focusedCite;
            return <div
              className={'inspector-code-line'+(isCurrent?' inspector-code-target':'')+
                (cites.some(r=>r.kind==='bug')?' inspector-code-bug':
                 cites.some(r=>r.kind==='change')?' inspector-code-change':
                 isCited?' inspector-code-citation':'')+
                (focusedCite?' inspector-code-focused':'')}
              key={row.line+'|'+index}
              ref={isCurrent?markedRef:undefined}
              aria-label={isCited?'Line '+row.line+' cited by model (not independently verified)':'Line '+row.line}>
              <span>{row.line}</span><code>{row.text||' '}</code>
              {isCited&&<span className="inspector-line-marker" aria-label="Model-cited line">●</span>}
            </div>;
          }):<p>Source lines unavailable in this approved snapshot.</p>}
        </div>
        {editMode&&<section className="inspector-suggestion-panel" aria-label="Edit suggestion draft">
          <div className="inspector-suggestion-heading">
            <strong>Edit suggestion · local draft</strong>
            <button className="outline-button" type="button" onClick={beginSuggestion}>Use selected line / finding</button>
          </div>
          <p className="muted">This is a proposed replacement for {draft?.file||selected}:{draft?.start??line}{draft&&draft.end>draft.start?'-'+draft.end:''}. It is NOT applied to the checkout. Inspect the scope and test it before using.</p>
          {draft&&draft.snapshotSha256===snapshot.sha256&&<>
            <div className="inspector-suggestion-grid">
              <label>Original source (read-only)
                <pre role="region" aria-label="Original source lines">{draft.original}</pre>
              </label>
              <label>Suggested replacement (editable)
                <textarea aria-label="Suggested replacement" value={draft.replacement} rows={6}
                  maxLength={12000} onChange={e=>{setDraft({...draft,replacement:e.target.value,origin:'manual'});setDraftMessage('');}}/>
              </label>
            </div>
            {matchingSuggestion&&<button type="button" className="outline-button"
              onClick={()=>{setDraft({...draft,replacement:matchingSuggestion,origin:'model-excerpt'});setDraftMessage('Model snippet loaded as an unverified editable proposal. No project files changed.');}}>
              Use model-proposed code snippet
            </button>}
            <div className="inspector-suggestion-actions">
              <button type="button" className="outline-button" onClick={()=>{setDraft({...draft,replacement:draft.original,origin:'manual'});setDraftMessage('');}}>Reset draft</button>
              <button type="button" disabled={!patch} onClick={()=>void copyPatch()}>Copy proposed patch</button>
            </div>
            <div className="inspector-diff" aria-label="Suggested diff preview">
              <strong>Diff preview · source unchanged</strong>
              <pre role="region" aria-label="Suggested diff preview content">{patch||'No changes proposed yet. Edit the replacement code to preview a patch.'}</pre>
            </div>
            {patch&&snapshot.sourceAccess&&!applied&&<>
              <div className="inspector-apply-panel" role="group" aria-label="Approve developer patch">
                <strong>Apply this patch · explicit local write approval</strong>
                <p className="muted">The exact line replacement will be written to a newly created Git branch in your selected checkout. The tree must be clean, source unchanged and local writes explicitly enabled via <code>./start.sh --enable-code-writes</code>. No model calls, commits, pushes or tests occur automatically.</p>
                <label>New fix branch
                  <input aria-label="New fix branch" value={branch} maxLength={59}
                    onChange={e=>{setBranch(e.target.value);setApplyConfirmed(false);}}/>
                </label>
                <label className="benchmark-approval"><input type="checkbox"
                  aria-label="I approve writing this exact diff to a new local Git branch"
                  checked={applyConfirmed} onChange={e=>setApplyConfirmed(e.target.checked)}/>
                  I reviewed the exact diff and approve writing this file on a clean, new local Git branch.
                </label>
                <button type="button" disabled={!applyConfirmed||applyBusy||sourceLoading||
                  !fullSource||fullSource.file!==draft.file||
                  !/^daeloryn\/[a-z0-9][a-z0-9-]{0,50}$/.test(branch)}
                  onClick={()=>void applyApprovedPatch()}>
                  {applyBusy?'Applying reviewed patch…':'Apply approved fix to local branch'}
                </button>
              </div>
            </>}
            {applied&&<div className="inspector-apply-panel" role="group" aria-label="Approved developer patch applied">
              <strong>Fix applied on {applied.branch}</strong>
              <p>Changed: {applied.file}. The old review snapshot is stale. Run tests, inspect Git diff and review before committing.</p>
              <label>Test suite (executes project code on this Mac)
                <select aria-label="Approved test suite" value={suite} onChange={e=>{setSuite(e.target.value);setTestsApproved(false);}}>
                  <option value="maven">Maven: mvn -B test</option>
                  <option value="npm">npm: npm test -- --runInBand</option>
                  <option value="python">Python: python3 -m unittest discover -s tests</option>
                </select>
              </label>
              <label className="benchmark-approval"><input type="checkbox"
                aria-label="Approve executing selected tests with host permissions"
                checked={testsApproved} onChange={e=>setTestsApproved(e.target.checked)}/>
                I approve running this selected test command with my local user privileges (not sandboxed).
              </label>
              <button type="button" disabled={!testsApproved||testsBusy}
                onClick={()=>void runApprovedTests()}>{testsBusy?'Running approved tests…':'Run approved tests'}</button>
              {testOutcome&&<details open><summary>{testOutcome.verified?'Tests passed':'Tests failed'} · {testOutcome.suite} · exit {testOutcome.returncode}</summary>
                <pre role="region" aria-label="Local test output">{testOutcome.output}</pre></details>}
            </div>}
          </>}
          {draftMessage&&<p role="status">{draftMessage}</p>}
        </section>}
      </>}
    </div>
    <footer>Read-only review by default · code is modified only by explicit approved local patch · Esc closes full screen</footer>
  </aside>;
}
