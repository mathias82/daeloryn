import {useEffect,useMemo,useState} from 'react';
import {nearbyDeclaration,sourcePreview} from './sourceInspector';
import type {InspectorSnapshot} from './sourceInspector';

export function CodeInspector({snapshot,onClose}:{
  snapshot:InspectorSnapshot;onClose:()=>void;
}){
  const files=useMemo(()=>[...new Set(snapshot.sources.map(s=>s.file))], [snapshot.sources]);
  const [file,setFile]=useState('');
  const [line,setLine]=useState(1);
  const selected=files.includes(file)?file:files[0]||'';
  useEffect(()=>{setFile(files[0]||'');setLine(1);},[snapshot.sha256,files[0]]);
  const preview=useMemo(()=>sourcePreview(snapshot.sources,selected,line),[snapshot.sources,selected,line]);
  const valid=snapshot.references.filter(r=>r.verified);
  const unverified=snapshot.references.filter(r=>!r.verified);
  function jump(path:string,at:number){setFile(path);setLine(at);}
  return <aside className="code-inspector" aria-label="Code Inspector">
    <header className="inspector-header">
      <div><strong>Code Inspector</strong><small>{snapshot.repository} · read-only source preview</small></div>
      <button type="button" className="outline-button" aria-label="Close Code Inspector" onClick={onClose}>×</button>
    </header>
    <div className="inspector-progress" role="status">
      <span>{snapshot.status}</span><span>{snapshot.completed}/{snapshot.total} batches</span>
    </div>
    <div className="inspector-findings">
      <strong>References in model results</strong>
      <p className="muted">Links are checked against the approved source snapshot, <em>not</em> independently confirmed bugs. Findings can contain false positives.</p>
      {valid.length===0&&<p className="muted">No matching file:line references yet. New batch responses appear here as they finish.</p>}
      {valid.map((r,i)=><button className="inspector-ref" type="button"
        key={r.batch+'|'+r.file+'|'+r.line+'|'+i}
        onClick={()=>jump(r.file,r.line)}>
        <span>{r.file}:{r.line}</span><small>Batch {r.batch} · line found in snapshot</small>
        <span className="inspector-excerpt">{r.excerpt}</span>
      </button>)}
      {unverified.length>0&&<details className="inspector-unverified">
        <summary>{unverified.length} unverified references (not navigable)</summary>
        {unverified.map((r,i)=><p key={r.file+'|'+i}>{r.file}:{r.line} · batch {r.batch} · no matching line in approved snapshot</p>)}
      </details>}
    </div>
    <div className="inspector-source">
      <label>Inspected file
        <select aria-label="Inspected source file" value={selected}
          onChange={event=>{setFile(event.target.value);setLine(1);}}>
          {files.map(f=><option key={f} value={f}>{f}</option>)}
        </select>
      </label>
      {selected&&<><div className="inspector-source-caption">
        <strong>{selected}</strong><small>{nearbyDeclaration(snapshot.sources,selected,line)||'Source excerpt · original line numbers'}</small>
      </div>
      <div className="inspector-code" role="region" aria-label="Read-only source excerpt">
        {preview.length?preview.map((row,index)=><div className={'inspector-code-line '+(row.line===line?'inspector-code-target':'')} key={row.line+'|'+index}>
          <span>{row.line}</span><code>{row.text||' '}</code>
        </div>):<p>Source lines unavailable in this snapshot.</p>}
      </div></>}
    </div>
    <footer>Read-only · inspected source only · no workspace modifications</footer>
  </aside>;
}
