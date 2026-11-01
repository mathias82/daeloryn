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
  const markedRef=useRef<HTMLDivElement|null>(null);
  const selected=files.includes(file)?file:files[0]||'';
  const visibleCount=expanded?180:42;
  const preview=useMemo(()=>sourcePreview(snapshot.sources,selected,line,visibleCount),
    [snapshot.sources,selected,line,visibleCount]);
  const valid=snapshot.references.filter(r=>r.verified);
  const unverified=snapshot.references.filter(r=>!r.verified);
  const marks=valid.filter(r=>r.file===selected);
  const active=marks.find(r=>line>=r.line&&line<=r.endLine);
  const patch=draft&&draft.snapshotSha256===snapshot.sha256?draftPatch(draft):null;
  const matchingSuggestion=active&&draft&&draft.file===active.file&&draft.start===active.line&&draft.end===active.endLine
    ? active.suggestionText : undefined;
  function beginSuggestion(){
    const start=active?.line??line,end=active?.endLine??line;
    const proposal=startSuggestion(snapshot.sources,selected,start,end,snapshot.sha256);
    if(!proposal){setDraftMessage('The selected source lines were not available completely in the approved snapshot. Select another line.');return;}
    setDraft(proposal);setEditMode(true);setDraftMessage('');
  }
  async function copyPatch(){
    if(!patch)return;
    try{
      await navigator.clipboard.writeText(patch);
      setDraftMessage('Patch copied. No files were modified. Review and apply it manually after checking tests.');
    }catch{setDraftMessage('Clipboard permission unavailable. Select and copy the diff manually.');}
  }

  useEffect(()=>{setFile(files[0]||'');setLine(1);setLineInput('1');setDraft(null);setEditMode(false);setDraftMessage('');},
    [snapshot.sha256,files[0]]);
  useEffect(()=>{
    if(!expanded)return;
    const onKey=(event:KeyboardEvent)=>{if(event.key==='Escape')setExpanded(false);};
    window.addEventListener('keydown',onKey);
    return()=>window.removeEventListener('keydown',onKey);
  },[expanded]);
  useEffect(()=>{markedRef.current?.scrollIntoView({block:'center',behavior:'instant'});},
    [line,selected,expanded]);
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
          <small>{nearbyDeclaration(snapshot.sources,selected,line)||'Source excerpt · original line numbers'}</small>
        </div>
        {active&&<p className="inspector-target-note" role="status">
          Highlighted: {active.kind==='bug'?'possible bug':active.kind==='change'?'suggested method/code change':'source citation'}
          {' · '}line {active.line}{active.endLine>active.line?'–'+active.endLine:''}
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
        <div className="inspector-code" role="region" aria-label="Read-only source excerpt">
          {preview.length?preview.map((row,index)=>{
            const cites=marks.filter(r=>row.line>=r.line&&row.line<=r.endLine);
            const isCurrent=row.line===line;
            return <div
              className={'inspector-code-line'+(isCurrent?' inspector-code-target':'')+
                (cites.some(r=>r.kind==='bug')?' inspector-code-bug':
                 cites.some(r=>r.kind==='change')?' inspector-code-change':
                 cites.length?' inspector-code-citation':'')}
              key={row.line+'|'+index}
              ref={isCurrent?markedRef:undefined}
              aria-label={cites.length?'Line '+row.line+' marked by model result':'Line '+row.line}>
              <span>{row.line}</span><code>{row.text||' '}</code>
              {cites.length>0&&<span className="inspector-line-marker" aria-label="Model-cited line">●</span>}
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
                <pre aria-label="Original source lines">{draft.original}</pre>
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
              <pre>{patch||'No changes proposed yet. Edit the replacement code to preview a patch.'}</pre>
            </div>
          </>}
          {draftMessage&&<p role="status">{draftMessage}</p>}
        </section>}
      </>}
    </div>
    <footer>Read-only workspace · suggestions are local drafts · Esc closes full screen · no source modification</footer>
  </aside>;
}
