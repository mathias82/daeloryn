import {useEffect,useState} from 'react';

type PairedRow={
  run_id:string;repository:string;mode:string;model:string;agent:string;
  status:string;evaluation_status:string;provisional_evidence_lead:string;
  baseline_score:number|null;daeloryn_score:number|null;verified_winner:null;
};

export function LocalComparisons(){
  const [rows,setRows]=useState<PairedRow[]>([]);
  const [error,setError]=useState('');
  const [project,setProject]=useState('');
  useEffect(()=>{
    let active=true;
    async function poll(){
      try{
        const response=await fetch('/api/benchmarks',{cache:'no-store'});
        if(!response.ok)throw new Error('Local comparisons unavailable ('+response.status+')');
        const data:unknown=await response.json();
        if(!data||typeof data!=='object'||!('paired_comparisons' in data)||
          !Array.isArray(data.paired_comparisons))throw new Error('Invalid comparison response');
        const list=data.paired_comparisons as PairedRow[];
        if(!list.every(row=>row&&typeof row.run_id==='string'&&typeof row.repository==='string'&&
          typeof row.agent==='string'&&typeof row.status==='string'&&typeof row.evaluation_status==='string'&&
          typeof row.provisional_evidence_lead==='string'&&
          (row.baseline_score===null||typeof row.baseline_score==='number')&&
          (row.daeloryn_score===null||typeof row.daeloryn_score==='number')))
          throw new Error('Malformed local comparison');
        if(active){setRows(list);setError('');}
      }catch(e){if(active)setError(e instanceof Error?e.message:'No comparisons');}
    }
    void poll();
    const interval=window.setInterval(()=>void poll(),2500);
    return()=>{active=false;window.clearInterval(interval);};
  },[]);
  const projects=[...new Set(rows.map(row=>row.repository))].sort();
  const selected=rows.filter(row=>!project||row.repository===project);
  const scored=selected.filter(row=>row.baseline_score!==null&&row.daeloryn_score!==null);
  const covered=new Set(scored.map(row=>row.agent));
  return <section className="surface" aria-label="Comparison results">
    <div className="surface-head"><div><h2>Comparison results</h2>
      <p className="muted">Automatic local source-citation evidence scoring, updated as approved A/B runs finish. No additional provider calls.</p></div>
      <span className="subtle-tag">{selected.length?selected.length+' LOCAL RUNS':'NO LOCAL RUNS'}</span>
    </div>
    <label>Results project <select value={project} onChange={event=>setProject(event.target.value)}>
      <option value="">All projects</option>
      {projects.map(name=><option key={name} value={name}>{name}</option>)}
    </select></label>
    {error&&<p role="status">{error} · Displayed results may be stale.</p>}
    <div className="metrics compact" aria-label="Local benchmark progress">
      <article className="surface"><h3>Saved local runs</h3><strong>{selected.length}</strong>
        <p>{selected.filter(row=>row.status==='running'||row.status==='stopping').length} running or stopping · {selected.filter(row=>row.status==='partial').length} partial</p></article>
      <article className="surface"><h3>Scored local comparisons</h3><strong>{scored.length}</strong>
        <p>Both arms have citation scores; partial source coverage may remain.</p></article>
      <article className="surface"><h3>Agents with scored runs</h3><strong>{covered.size}</strong>
        <p>{[...covered].sort().join(', ')||'No agents scored yet.'}</p></article>
    </div>
    <p className="muted">Updates every 2.5 seconds from saved local runs. Repeated runs of one agent count once in agent coverage. These counts do not verify bugs, model identity, or a winner.</p>
    <div className="table-wrap">
      <table>
        <thead><tr><th>Run / source</th><th>Plain Copilot</th><th>Copilot + Daeloryn</th><th>Provisional citation lead</th><th>Verified winner</th></tr></thead>
        <tbody>{selected.length?selected.map(row=><tr key={row.run_id}>
          <td>{row.repository}<br/><small>{row.run_id.slice(0,8)} · {row.status}</small></td>
          <td>{row.baseline_score===null?'Not evaluated':row.baseline_score+'/100'}</td><td>{row.daeloryn_score===null?'Not evaluated':row.daeloryn_score+'/100'}</td>
          <td>{row.baseline_score===null?'Pending / unavailable':row.provisional_evidence_lead.replace(/_/g,' ')}<br/><small>{row.evaluation_status.replace(/_/g,' ')}</small></td>
          <td>Not verified · no independent defect or regression-test adjudication</td>
        </tr>):<tr><td colSpan={5} className="table-empty">
          No local evidence comparisons yet. Start and complete an A/B run above, or open a saved run and choose Evaluate saved run.
        </td></tr>}</tbody>
      </table>
    </div>
  </section>;
}
