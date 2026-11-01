import {useEffect,useMemo,useState} from 'react';

type Mode='review'|'architecture'|'fix-plan';
type Project={name:string;path:string;technologies:string[]};
export type CampaignSelection={agent:string;mode:Mode;repository:string;revision:number};
type AgentEntry={
  order:number;agent:string;scope:string;benchmark_mode:Mode;domain_scenario:string;
  state:string;latest_run_id:string|null;latest_run_status:string|null;
  traceability_scores:{baseline:number;daeloryn:number}|null;
  provisional_evidence_lead:string;verified_winner:null;candidate_rule_improvements:string[];
  applicable?:boolean;inapplicable_reason?:string;
};
type ProjectCampaign={
  repository:string;technologies:string[];total_agents:number;applicable_agents:number;
  provisionally_assessed:number;next_agent:string|null;entries:AgentEntry[];
};
type Campaign={
  kind:string;schema_version:number;generated_at:string;total_agents:number;
  provisionally_assessed:number;next_agent:string|null;weaker_traceability_agents:number;
  provider_calls_started:boolean;rules_modified:boolean;independently_verified_winners:number;
  warning:string;entries:AgentEntry[];project_campaigns:ProjectCampaign[];
  project_name?:string;
};

/** Applicable agents come from the local API's bounded manifest detection.
 * The browser does not guess that any Node project is React or any Maven
 * project is Spring, and never selects agents from a different project.
 */
function reportMarkdown(report:Campaign){
  const lines=[
    '# Daeloryn agent A/B campaign — offline observation report',
    '',
    'Generated: '+report.generated_at,
    'Project: '+(report.project_name||'not selected'),
    'Stack: '+(report.project_campaigns[0]?.technologies.join(', ')||'unknown'),
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
      'Applicable for chosen project: '+(row.applicable===false?'No':'Yes'),
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
function exportReport(report:Campaign,project:ProjectCampaign,kind:'json'|'md'){
  const scopedReport:Campaign={
    ...report,
    project_name:project.repository,
    project_campaigns:[project],
    entries:project.entries,
    provisionally_assessed:project.provisionally_assessed,
    next_agent:project.next_agent,
    weaker_traceability_agents:project.entries.filter(row=>row.candidate_rule_improvements.length>0).length
  };
  const value=kind==='json'?JSON.stringify(scopedReport,null,2):reportMarkdown(scopedReport);
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
          !('project_campaigns' in data)||!Array.isArray(data.project_campaigns)||
          !('total_agents' in data)||data.total_agents!==data.entries.length||
          !data.project_campaigns.every((project:unknown)=>project&&typeof project==='object'&&
            'repository' in project&&typeof project.repository==='string'&&
            'entries' in project&&Array.isArray(project.entries)&&
            'applicable_agents' in project&&typeof project.applicable_agents==='number'&&
            project.entries.every((row:unknown)=>row&&typeof row==='object'&&
              'agent' in row&&typeof row.agent==='string'&&
              'state' in row&&typeof row.state==='string'&&
              'applicable' in row&&typeof row.applicable==='boolean')))
          throw new Error('Invalid project-aware campaign report; restart the local API');
        if(mounted){setReport(data as Campaign);setError('');}
      }catch(e){if(mounted)setError(e instanceof Error?e.message:'Campaign status unavailable');}
    }
    void poll();
    const timer=window.setInterval(()=>void poll(),3500);
    return()=>{mounted=false;window.clearInterval(timer);};
  },[]);
  const repository=projects.some(p=>p.name===chosenRepository)?chosenRepository:projects[0]?.name||'';
  const activeProject=useMemo(()=>report?.project_campaigns.find(p=>p.repository===repository),
    [report,repository]);
  const next=activeProject?.entries.find(e=>e.agent===activeProject.next_agent);
  const nextProjectPosition=activeProject&&next?
    activeProject.entries.filter(e=>e.applicable).findIndex(e=>e.agent===next.agent)+1:0;
  return <section className="surface agent-campaign" aria-label="22-agent evaluation campaign">
    <div className="surface-head">
      <div><h2>Project-aware sequential agent evaluation</h2>
        <p className="muted">Select a project first. Its detected Java, Spring, React or platform stack determines which specialists are relevant; each paired review still needs explicit approval.</p>
      </div>
      <span className="subtle-tag">{activeProject?activeProject.provisionally_assessed+'/'+activeProject.applicable_agents+' applicable assessed':'SELECT PROJECT'}</span>
    </div>
    {error&&<p role="alert">{error}</p>}
    {report&&<>
      <label>Project to evaluate
        <select aria-label="Campaign project" value={repository} onChange={event=>setChosenRepository(event.target.value)}>
          {projects.length?projects.map(p=><option key={p.path} value={p.name}>{p.name}</option>):
            <option value="">No registered local checkout</option>}
        </select>
      </label>
      {activeProject?<p role="status">Detected stack: {activeProject.technologies.join(', ')||'unknown'} · {activeProject.applicable_agents} matching agents · {activeProject.total_agents-activeProject.applicable_agents} not applicable to this project</p>:
        <p role="status">No matching campaign for this registered project. Refresh after starting the API with project discovery enabled.</p>}
      <p className="muted">{report.warning}</p>
      <div className="benchmark-actions">
        <button type="button" className="outline-button" disabled={!activeProject} onClick={()=>{if(activeProject)exportReport(report,activeProject,'md');}}>
          Export evaluation report (Markdown)
        </button>
        <button type="button" className="outline-button" disabled={!activeProject} onClick={()=>{if(activeProject)exportReport(report,activeProject,'json');}}>
          Export structured JSON
        </button>
      </div>
      {next?<div className="campaign-next">
        <h3>Next: {nextProjectPosition}/{activeProject?.applicable_agents} · {next.agent}</h3>
        <p>{next.domain_scenario}</p>
        <p className="muted">Scope: {next.scope} · Mode: {next.benchmark_mode} · Status: {next.state}</p>
        {next.state==='incomplete'&&<p role="status">
          This agent has an incomplete run. Open the saved run and use Resume where available before starting a fresh comparison.
        </p>}
        {next.state==='needs_evaluation'&&<p role="status">
          A completed run exists. Open it and select Evaluate saved run (offline) before requesting another paid comparison.
        </p>}
         <button type="button" disabled={!repository||next.state!=='not_started'}
          onClick={()=>onSelect({agent:next.agent,mode:next.benchmark_mode,repository})}>
          Set up next A/B benchmark · {next.agent}
        </button>
        <p className="muted">This only fills in the benchmark form. Inspect the prepared snapshot and approve each billable paired run explicitly.</p>
      </div>:activeProject?<p role="status">{activeProject.applicable_agents===0?
        'No relevant specialist can be confirmed from the project manifests. Select another project or add its actual build files.':
        'All applicable specialists have a provisional traceability assessment. This is not independent proof of superiority.'}</p>:
        <p role="status">Select a registered project to begin.</p>}
      <details className="campaign-matrix">
        <summary>View all {activeProject?.total_agents||report.total_agents} specialist scenarios and improvement recommendations</summary>
        <div className="table-wrap"><table>
          <thead><tr><th>Order</th><th>Agent / scope</th><th>Scenario</th><th>Run</th><th>Evidence comparison</th></tr></thead>
          <tbody>{(activeProject?.entries||[]).map(row=><tr key={row.agent}>
            <td>{row.order}</td>
            <td>{row.agent}<br/><small>{row.scope}</small></td>
            <td>{row.domain_scenario}</td>
            <td>{row.state.replace(/_/g,' ')}{row.applicable===false&&<small> · different stack</small>}</td>
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
