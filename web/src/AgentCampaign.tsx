import {useEffect,useMemo,useState} from 'react';

type Mode='review'|'architecture'|'fix-plan';
type Project={name:string;path:string;technologies:string[]};
export type CampaignSelection={agent:string;mode:Mode;repository:string;revision:number};
type AgentEntry={
  order:number;agent:string;scope:string;benchmark_mode:Mode;domain_scenario:string;
  state:string;latest_run_id:string|null;latest_run_status:string|null;
  traceability_scores:{baseline:number;daeloryn:number}|null;
  provisional_evidence_lead:string;verified_winner:null;candidate_rule_improvements:string[];
};
type Campaign={
  kind:string;schema_version:number;generated_at:string;total_agents:number;
  provisionally_assessed:number;next_agent:string|null;weaker_traceability_agents:number;
  provider_calls_started:boolean;rules_modified:boolean;independently_verified_winners:number;
  warning:string;entries:AgentEntry[];
};

function supportedProject(scope:string,project:Project){
  const tech=project.technologies.join(' ').toLowerCase();
  if(scope==='java')return /java|maven|gradle/.test(tech);
  if(scope==='spring')return /spring|java|maven|gradle/.test(tech);
  if(scope==='react')return /react|typescript|javascript|node|frontend/.test(tech);
  if(scope==='platform')return /docker|kubernetes|helm|gitops|ci|devops|cloud|platform/.test(tech);
  return true; // shared security and integration tasks can inspect any stack
}
function reportMarkdown(report:Campaign){
  const lines=[
    '# Daeloryn agent A/B campaign — offline observation report',
    '',
    'Generated: '+report.generated_at,
    'Agents: '+report.total_agents+' · Provisionally assessed: '+report.provisionally_assessed+
      ' · Traceability-behind cases: '+report.weaker_traceability_agents,
    '',
    '**Verification:** 0 independently verified winners. No automated code changes or provider calls from export.',
    '',
    report.warning,'',
  ];
  for(const row of report.entries){
    lines.push('## '+row.order+'. '+row.agent+' ('+row.scope+')','',
      'Domain: '+row.domain_scenario,
      'Suggested mode: '+row.benchmark_mode,
      'Run state: '+row.state,
      'Run ID: '+(row.latest_run_id||'not started'),
      'Evidence lead: '+row.provisional_evidence_lead,
      'Traceability: '+(row.traceability_scores?
        'Plain Copilot '+row.traceability_scores.baseline+
        '/100; Copilot + Daeloryn '+row.traceability_scores.daeloryn+'/100':'not available'),
      'Verified winner: none','');
    if(row.candidate_rule_improvements.length){
      lines.push('### Candidate rule improvements (not applied)','',
        ...row.candidate_rule_improvements.map(x=>'- '+x),'');
    }
  }
  return lines.join('\n');
}
function exportReport(report:Campaign,kind:'json'|'md'){
  const value=kind==='json'?JSON.stringify(report,null,2):reportMarkdown(report);
  const blob=new Blob([value],{type:kind==='json'?'application/json':'text/markdown'});
  const url=URL.createObjectURL(blob);
  const link=document.createElement('a');
  link.href=url;link.download='daeloryn-agent-evaluation-report.'+kind;
  document.body.append(link);
  link.click();link.remove();
  window.setTimeout(()=>URL.revokeObjectURL(url),1000);
}

/** A one-at-a-time queue. This component never runs providers or edits rules. */
export function AgentCampaign({projects,onSelect}:{
  projects:Project[];onSelect:(value:Omit<CampaignSelection,'revision'>)=>void;
}){
  const [report,setReport]=useState<Campaign|null>(null);
  const [error,setError]=useState('');
  const [chosenRepository,setChosenRepository]=useState('');
  useEffect(()=>{
    let mounted=true;
    async function poll(){
      try{
        const response=await fetch('/api/benchmark/campaign',{cache:'no-store'});
        if(!response.ok)throw new Error('Campaign API unavailable ('+response.status+')');
        const data:unknown=await response.json();
        if(!data||typeof data!=='object'||!('entries' in data)||!Array.isArray(data.entries)||
          !('total_agents' in data)||data.total_agents!==data.entries.length||
          !data.entries.every((row:unknown)=>row&&typeof row==='object'&&
            'agent' in row&&typeof row.agent==='string'&&
            'state' in row&&typeof row.state==='string'))
          throw new Error('Invalid campaign report');
        if(mounted){setReport(data as Campaign);setError('');}
      }catch(e){if(mounted)setError(e instanceof Error?e.message:'Campaign status unavailable');}
    }
    void poll();
    const timer=window.setInterval(()=>void poll(),3500);
    return()=>{mounted=false;window.clearInterval(timer);};
  },[]);
  const next=report?.entries.find(e=>e.agent===report.next_agent);
  const matching=useMemo(()=>next?projects.filter(p=>supportedProject(next.scope,p)):[],[next,projects]);
  const repository=matching.some(p=>p.name===chosenRepository)?chosenRepository:matching[0]?.name||'';
  return <section className="surface agent-campaign" aria-label="22-agent evaluation campaign">
    <div className="surface-head">
      <div><h2>Sequential agent evaluation · 22 specialists</h2>
        <p className="muted">A/B review per expertise, one approved agent at a time. Separate review cases and evidence before modifying any agent rules.</p>
      </div>
      <span className="subtle-tag">{report?report.provisionally_assessed+'/'+report.total_agents+' assessed':'LOADING'}</span>
    </div>
    {error&&<p role="alert">{error}</p>}
    {report&&<>
      <p className="muted">{report.warning}</p>
      <div className="benchmark-actions">
        <button type="button" className="outline-button" onClick={()=>exportReport(report,'md')}>
          Export evaluation report (Markdown)
        </button>
        <button type="button" className="outline-button" onClick={()=>exportReport(report,'json')}>
          Export structured JSON
        </button>
      </div>
      {next?<div className="campaign-next">
        <h3>Next: {next.order}/{report.total_agents} · {next.agent}</h3>
        <p>{next.domain_scenario}</p>
        <p className="muted">Scope: {next.scope} · Mode: {next.benchmark_mode} · Status: {next.state}</p>
        {next.state==='incomplete'&&<p role="status">
          This agent has an incomplete run. Open the saved run and use Resume where available before starting a fresh comparison.
        </p>}
        {next.state==='needs_evaluation'&&<p role="status">
          A completed run exists. Open it and select Evaluate saved run (offline) before requesting another paid comparison.
        </p>}
        <label>Project appropriate for this specialist
          <select aria-label="Campaign project" value={repository} onChange={event=>setChosenRepository(event.target.value)}>
            {matching.length?matching.map(p=><option key={p.path} value={p.name}>{p.name}</option>):
              <option value="">No eligible registered local project</option>}
          </select>
        </label>
        <button type="button" disabled={!repository||next.state!=='not_started'}
          onClick={()=>onSelect({agent:next.agent,mode:next.benchmark_mode,repository})}>
          Set up next A/B benchmark · {next.agent}
        </button>
        <p className="muted">This only fills in the benchmark form. Inspect the prepared snapshot and approve each billable paired run explicitly.</p>
      </div>:<p role="status">All agent entries have a provisional traceability assessment. This is not independent proof of superiority.</p>}
      <details className="campaign-matrix">
        <summary>View all {report.total_agents} specialist scenarios and improvement recommendations</summary>
        <div className="table-wrap"><table>
          <thead><tr><th>Order</th><th>Agent / scope</th><th>Scenario</th><th>Run</th><th>Evidence comparison</th></tr></thead>
          <tbody>{report.entries.map(row=><tr key={row.agent}>
            <td>{row.order}</td>
            <td>{row.agent}<br/><small>{row.scope}</small></td>
            <td>{row.domain_scenario}</td>
            <td>{row.state.replace(/_/g,' ')}</td>
            <td>{row.traceability_scores?<>
              Plain {row.traceability_scores.baseline}/100 · Daeloryn {row.traceability_scores.daeloryn}/100
              <br/><small>{row.provisional_evidence_lead} · traceability only</small>
              {row.candidate_rule_improvements.length>0&&<details>
                <summary>Review proposed rule improvements</summary>
                {row.candidate_rule_improvements.map((text,i)=><p key={i}>{text}</p>)}
              </details>}
            </>:<small>Not yet comparable</small>}</td>
          </tr>)}</tbody>
        </table></div>
      </details>
    </>}
  </section>;
}
