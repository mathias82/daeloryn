import {useEffect,useRef,useState} from 'react';
export type LocalProject={name:string;path:string;technologies:string[]};

export function ProjectPicker({onAdded}:{onAdded:(rows:LocalProject[])=>void}) {
  const dialog=useRef<HTMLDialogElement>(null);
  const [path,setPath]=useState('');
  const [recursive,setRecursive]=useState(false);
  const [rows,setRows]=useState<LocalProject[]>([]);
  const [selected,setSelected]=useState<string[]>([]);
  const [approved,setApproved]=useState(false);
  const [busy,setBusy]=useState(false);
  const [searched,setSearched]=useState(false);
  const [error,setError]=useState('');
  useEffect(()=>()=>{dialog.current?.close();},[]);
  function reset(){setSearched(false);setRows([]);setSelected([]);setApproved(false);setError('');}
  async function request(body:Record<string,unknown>){
    const response=await fetch('/api/repositories/manage',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const result=await response.json();
    if(!response.ok) throw new Error(result.error||'Project registration unavailable');
    return result;
  }
  async function run(action:'browse'|'preview'|'add'){
    setBusy(true);setError('');
    try{
      if(action==='browse'){
        const result=await request({action});
        if(result.path){reset();setPath(result.path);}
      }else if(action==='preview'){
        reset();
        const result=await request({action,path,recursive});
        setRows(result.candidates);setSearched(true);
      }else{
        const result=await request({action,paths:selected,approved});
        onAdded(result.repositories);dialog.current?.close();reset();
      }
    }catch(e){setError(e instanceof Error?e.message:'Project registration unavailable');}
    finally{setBusy(false);}
  }
  return <>
    <button type="button" className="outline-button" onClick={()=>{reset();dialog.current?.showModal();}}>Add project</button>
    <dialog ref={dialog} className="project-dialog" aria-labelledby="project-dialog-title" onCancel={e=>{if(busy)e.preventDefault();}}>
      <h2 id="project-dialog-title">Add local projects</h2>
      <p>Choose a project, or search a parent folder for nested Git checkouts. This registers local access only. Sending source to AI requires separate approval.</p>
      <label>Absolute folder path<input autoFocus value={path} disabled={busy} placeholder="/Users/your-name/IdeaProjects" onChange={e=>{setPath(e.target.value);reset();}}/></label>
      <button type="button" className="outline-button" disabled={busy} onClick={()=>void run('browse')}>Browse folders (macOS)</button>
      <label className="project-check"><input type="checkbox" checked={recursive} disabled={busy} onChange={e=>{setRecursive(e.target.checked);reset();}}/>Find projects in subfolders</label>
      <button type="button" className="outline-button" disabled={busy||!path.trim()} onClick={()=>void run('preview')}>Find projects</button>
      {searched&&rows.length===0&&<p role="status">No supported Git projects found in this folder.</p>}
      {rows.length>0&&<fieldset><legend>Select projects to add</legend>{rows.map(row=><label className="project-check" key={row.path}><input type="checkbox" disabled={busy} checked={selected.includes(row.path)} onChange={e=>{setSelected(previous=>e.target.checked?[...previous,row.path]:previous.filter(p=>p!==row.path));setApproved(false);}}/><span><strong>{row.name}</strong><small>{row.path}</small></span></label>)}</fieldset>}
      {rows.length>0&&<label className="project-check"><input type="checkbox" checked={approved} disabled={busy} onChange={e=>setApproved(e.target.checked)}/>I approve registering the selected local projects. No AI upload.</label>}
      {error&&<p role="alert">{error}</p>}
      {busy&&<p role="status">Working… If the native chooser opened, select a folder or cancel it on the backend computer.</p>}
      <p className="muted">Requires --enable-project-picker on the local API. Saved locally across restarts. Search limits: 100 projects, 10,000 entries, depth 8. Symbolic links and Git worktrees are excluded.</p>
      <div className="project-actions"><button type="button" className="outline-button" disabled={busy} onClick={()=>dialog.current?.close()}>Cancel</button><button type="button" className="outline-button" disabled={busy||!selected.length||!approved} onClick={()=>void run('add')}>Add selected projects</button></div>
    </dialog>
  </>;
}
