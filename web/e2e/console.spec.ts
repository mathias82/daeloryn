import {test,expect} from '@playwright/test';

// Browser integration fixtures: never an authenticated Copilot session.
const models=['claude-sonnet-4','claude-haiku-4'];
const trials=[{run_id:'fixture-run',agent:'java-reviewer',provider:'copilot',arm:'daeloryn',outcome:'tie_all_gates_passed',baseline_model:models[0],daeloryn_model:models[0],model_identity_verified:false,agent_selection_verified:false,independent_checks_executed:true,comparable:true}];
test.beforeEach(async({page})=>{
  await page.route('**/api/**',async route=>{
    const path=new URL(route.request().url()).pathname;
    const data:Record<string,unknown>={
      '/api/health':{execution_enabled:false},
      '/api/agents':{agents:[{name:'java-reviewer',scope:'java',description:'Fixture reviewer'}]},
      '/api/benchmarks':{agent_count:1,expected_cells:8,observed_cells:1,verified_trial_count:0,coverage_percent:12.5,warning:'Fixture data; identities unverified',trials},
      '/api/benchmark/runs':{runs:[],persistence:'local-private-disk',verified_trial:false},
      '/api/models':{models:[],chat_enabled:false},
      '/api/copilot/status':{enabled:true},
      '/api/copilot/models':{models},
      '/api/repositories':{repositories:[{name:'demo',path:'/fixture/demo',technologies:['java']}]},
    };
    if(path==='/api/copilot/review/prepare'){
      const body=route.request().postDataJSON();
      await route.fulfill({json:{...body,prompt:'Fixture excerpts',sha256:'a'.repeat(64),files:['App.java'],warning:'Test fixture only',agent_profile:'Fixture profile',agent_profile_sha256:'b'.repeat(64)}});return;
    }
    if(path==='/api/copilot/chat'){await route.fulfill({json:{reply:'Fixture reply'}});return;}
    await route.fulfill({status:path in data?200:503,json:data[path]||{error:'No fixture for endpoint'}});
  });
  await page.goto('/',{waitUntil:'domcontentloaded'});
  await expect(page.getByText('Loaded from repository',{exact:true})).toBeVisible();
});

test('chat sends chosen model and agent together',async({page})=>{
  await page.getByRole('navigation').getByRole('button',{name:/Chat/}).click();
  await page.getByLabel(/^Agent/).selectOption('java-reviewer');
  await page.getByLabel(/^Copilot model/).selectOption(models[0]);
  await page.getByRole('textbox',{name:'Message',exact:true}).fill('Review Java');
  const request=page.waitForRequest(r=>new URL(r.url()).pathname==='/api/copilot/chat');
  await page.getByRole('button',{name:/Send message/}).click();
  expect((await request).postDataJSON()).toMatchObject({model:models[0],agent:'java-reviewer'});
  await expect(page.getByText(/Fixture reply/)).toBeVisible();
});

test('changing approved model clears source-review approval without executing',async({page})=>{
  let executions=0;page.on('request',r=>{if(r.url().endsWith('/api/copilot/review/execute'))executions++;});
  await page.getByRole('navigation').getByRole('button',{name:/Chat/}).click();
  await page.getByLabel(/^Agent/).selectOption('java-reviewer');
  await page.getByLabel(/^Copilot model/).selectOption(models[0]);
  await page.getByLabel(/^Local repository/).selectOption('demo');
  await page.getByText('Advanced: manual source review').click();
  await page.getByRole('button',{name:'Prepare AI review context',exact:true}).click();
  const approval=page.getByRole('checkbox',{name:/I inspected the context/});
  await approval.check();
  await expect(page.getByRole('button',{name:'Send approved context to Copilot',exact:true})).toBeEnabled();
  await page.getByLabel(/^Copilot model/).selectOption(models[1]);
  await expect(approval).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Send approved context to Copilot',exact:true})).toHaveCount(0);
  expect(executions).toBe(0);
});

test('benchmark row preserves unverified identity and tie outcome',async({page})=>{
  await page.getByRole('navigation').getByRole('button',{name:/Benchmarks/}).click();
  const row=page.getByRole('row').filter({hasText:'fixture-run'});
  await expect(row).toContainText('tie all gates passed');
  await expect(row).toContainText('Model: unverified');
  await expect(row).toContainText('Agent: unverified');
  await expect(row).toContainText('Checks: reported executed');
});

test('project popup registers only explicitly selected paths without AI calls',async({page})=>{
  const posts:string[]=[];
  await page.route('**/api/repositories/manage',async route=>{
    const body=route.request().postDataJSON();posts.push(body.action);
    if(body.action==='preview'){
      await route.fulfill({json:{candidates:[{name:'nested',path:'/fixture/group/nested',technologies:[]},{name:'other',path:'/fixture/group/other',technologies:[]}]}});
    }else if(body.action==='add'){
      expect(body).toEqual({action:'add',paths:['/fixture/group/nested'],approved:true});
      await route.fulfill({json:{repositories:[{name:'nested',path:'/fixture/group/nested',technologies:[]}]}});
    }else await route.fulfill({json:{path:''}});
  });
  let aiCalls=0;page.on('request',r=>{if(r.url().includes('/api/copilot/')&&r.method()==='POST')aiCalls++;});
  await page.getByRole('navigation').getByRole('button',{name:/Chat/}).click();
  await page.getByRole('button',{name:'Add project',exact:true}).click();
  const dialog=page.getByRole('dialog',{name:'Add local projects'});
  await dialog.getByRole('button',{name:'Browse folders (macOS)'}).click();
  await expect(dialog.getByLabel('Absolute folder path')).toHaveValue('');
  await dialog.getByLabel('Absolute folder path').fill('/fixture/group');
  await dialog.getByLabel('Find projects in subfolders').check();
  await dialog.getByRole('button',{name:'Find projects',exact:true}).click();
  await expect(dialog.getByRole('button',{name:'Add selected projects'})).toBeDisabled();
  await dialog.getByRole('checkbox',{name:'nested /fixture/group/nested',exact:true}).check();
  await expect(dialog.getByRole('button',{name:'Add selected projects'})).toBeDisabled();
  await dialog.getByRole('checkbox',{name:/I approve registering/}).check();
  await dialog.getByRole('button',{name:'Add selected projects'}).click();
  await expect(dialog).not.toBeVisible();
  await page.getByLabel(/^Local repository/).selectOption('nested');
  expect(posts).toEqual(['browse','preview','add']);
  expect(aiCalls).toBe(0);
});

test('project popup surfaces disabled API and closes without adding',async({page})=>{
  await page.route('**/api/repositories/manage',route=>route.fulfill({status:405,json:{error:'Restart the local API with --enable-project-picker'}}));
  await page.getByRole('navigation').getByRole('button',{name:/Chat/}).click();
  await page.getByRole('button',{name:'Add project',exact:true}).click();
  const dialog=page.getByRole('dialog');
  await dialog.getByLabel('Absolute folder path').fill('/fixture/demo');
  await dialog.getByRole('button',{name:'Find projects',exact:true}).click();
  await expect(dialog.getByRole('alert')).toContainText('--enable-project-picker');
  await dialog.getByRole('button',{name:'Cancel',exact:true}).click();
  await expect(dialog).not.toBeVisible();
});

test('Enter sends once, Shift+Enter adds a newline and composition never sends',async({page})=>{
  let calls=0;
  page.on('request',r=>{if(r.url().endsWith('/api/copilot/chat'))calls++;});
  await page.getByRole('navigation').getByRole('button',{name:/Chat/}).click();
  await page.getByLabel(/^Copilot model/).selectOption(models[0]);
  const input=page.getByRole('textbox',{name:'Message',exact:true});
  await input.fill('First line');
  await input.press('Shift+Enter');
  await expect(input).toHaveValue('First line\n');
  expect(calls).toBe(0);
  await input.dispatchEvent('keydown',{key:'Enter',code:'Enter',isComposing:true});
  expect(calls).toBe(0);
  await input.press('Enter');
  await expect(page.getByText(/Fixture reply/)).toBeVisible();
  expect(calls).toBe(1);
  await input.press('Enter');
  expect(calls).toBe(1);
  await expect(page.getByText(/Copilot · text-only mode/)).toBeVisible();
});

test('rename and messages persist after reload; clear removes saved content',async({page})=>{
 await page.getByRole('navigation').getByRole('button',{name:/Chat/}).click();
 await page.getByRole('button',{name:'Rename conversation',exact:true}).click();
 await page.getByLabel('Conversation name').fill('Spring review pilot');
 await page.getByRole('button',{name:'Save name',exact:true}).click();
 await page.getByLabel(/^Copilot model/).selectOption(models[0]);
 await page.getByRole('textbox',{name:'Message',exact:true}).fill('Explain Spring dependency injection');
 await page.getByRole('textbox',{name:'Message',exact:true}).press('Enter');
 await expect(page.getByText(/Fixture reply/)).toBeVisible();
 await page.reload();
 await page.getByRole('navigation').getByRole('button',{name:/Chat/}).click();
 await expect(page.locator('.chat-toolbar strong')).toHaveText('Spring review pilot');
 await expect(page.getByText(/Fixture reply/)).toBeVisible();
 await page.getByRole('navigation').getByRole('button',{name:/Settings/}).click();
 await page.getByRole('button',{name:'Clear local conversation history',exact:true}).click();
 await expect(page.getByText(/Fixture reply/)).toHaveCount(0);
 await page.reload();
 await page.getByRole('navigation').getByRole('button',{name:/Chat/}).click();
 await expect(page.locator('.chat-toolbar strong')).toHaveText('New conversation');
});

test('completed long answer is revealed progressively with a show-all option',async({page})=>{
 await page.route('**/api/copilot/chat',route=>route.fulfill({json:{reply:Array.from({length:100},(_,i)=>'Review line '+i).join('\n')}}));
 await page.getByRole('navigation').getByRole('button',{name:/Chat/}).click();
 await page.getByLabel(/^Copilot model/).selectOption(models[0]);
 await page.getByRole('textbox',{name:'Message',exact:true}).fill('Review');
 await page.getByRole('textbox',{name:'Message',exact:true}).press('Enter');
 await expect(page.getByText('Displaying completed provider response…',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Show full reply',exact:true}).click();
 await expect(page.getByText(/Review line 99/)).toBeVisible();
});

test('source review shows coverage and call count and saves its result in chat',async({page})=>{
 await page.route('**/api/copilot/review/prepare',async route=>{
  const body=route.request().postDataJSON();
  await route.fulfill({json:{...body,prompt:'All fixture source batches',sha256:'a'.repeat(64),files:['One.java','Two.java'],warning:'Two model calls; fixture only',model:models[0],agent:'java-reviewer',agent_profile:null,agent_profile_sha256:null,batch_count:2,coverage:{all_eligible_files_included:true,omitted:[],excluded:[{path:'node_modules',reason:'dependency directory'}],scope:'Supported source files'}}});
 });
 await page.route('**/api/copilot/review/execute',route=>route.fulfill({json:{status:'completed',completed_batches:2,total_batches:2,coverage:{all_eligible_files_included:true},review:{reply:'Project review fixture completed'}}}));
 await page.getByRole('navigation').getByRole('button',{name:/Chat/}).click();
 await page.getByLabel(/^Agent/).selectOption('java-reviewer');
 await page.getByLabel(/^Copilot model/).selectOption(models[0]);
 await page.getByLabel(/^Local repository/).selectOption('demo');
 await page.getByText('Advanced: manual source review').click();
  await page.getByRole('button',{name:'Prepare AI review context',exact:true}).click();
 await expect(page.getByText('2 files · 2 model calls (potentially billable).',{exact:true})).toBeVisible();
 await page.getByRole('checkbox',{name:/I inspected the context/}).check();
 await page.getByRole('button',{name:'Send approved context to Copilot',exact:true}).click();
 await expect(page.locator('.bubble.assistant')).toContainText('Project review fixture completed');
 await page.reload();
 await page.getByRole('navigation').getByRole('button',{name:/Chat/}).click();
 await expect(page.locator('.bubble.assistant')).toContainText('Project review fixture completed');
});


test('streamed source review reports batch progress before final result',async({page})=>{
 await page.route('**/api/copilot/review/execute',route=>route.fulfill({contentType:'application/x-ndjson',body:[
  {type:'progress',phase:'running',completed:0,total:2,batch:1},
  {type:'progress',phase:'completed_batch',completed:1,total:2,batch:1},
  {type:'result',result:{status:'partial',completed_batches:1,total_batches:2,failure:'Fixture budget exhausted',review:{reply:'Streamed finding'}}}
 ].map(x=>JSON.stringify(x)).join('\n')+'\n'}));
 await page.getByRole('navigation').getByRole('button',{name:/Chat/}).click();
 await page.getByLabel(/^Agent/).selectOption('java-reviewer');
 await page.getByLabel(/^Copilot model/).selectOption(models[0]);
 await page.getByLabel(/^Local repository/).selectOption('demo');
 await page.getByText('Advanced: manual source review').click();
  await page.getByRole('button',{name:'Prepare AI review context',exact:true}).click();
 await page.getByRole('checkbox',{name:/I inspected the context/}).check();
 await page.getByRole('button',{name:'Send approved context to Copilot',exact:true}).click();
 await expect(page.locator('.bubble.assistant')).toContainText('Streamed finding');
 await expect(page.locator('.bubble.assistant')).toContainText('1/2 batches');
 await expect(page.getByRole('button',{name:'Prepare AI review context',exact:true})).toBeEnabled();
});


test('Send prepares project context in chat, waits for approval, then runs batches',async({page})=>{
  const requests:string[]=[];
  await page.route('**/api/copilot/review/prepare',async route=>{
    requests.push('prepare');
    const body=route.request().postDataJSON();
    expect(body).toMatchObject({repository:'demo',task:'Review the entire project',model:'auto',scope:'full'});
    await route.fulfill({json:{repository:'demo',model:models[0],agent:body.agent||null,scope:'full',
      prompt:'Fixture source snapshot',sha256:'a'.repeat(64),files:['App.java'],
      batch_count:2,warning:'Fixture review has 2 potentially billable calls',
      approval_required:true,agent_profile:null,agent_profile_sha256:null,
      coverage:{all_eligible_files_included:true,scope:'Fixture source',omitted:[],excluded:[]}}});
  });
  await page.route('**/api/copilot/review/execute',async route=>{
    requests.push('execute');
    expect(route.request().postDataJSON()).toMatchObject({
      repository:'demo',task:'Review the entire project',model:models[0],scope:'full',approved_sha256:'a'.repeat(64)});
    await route.fulfill({contentType:'application/x-ndjson',body:[
      {type:'progress',phase:'running',completed:0,total:2,batch:1},
      {type:'progress',phase:'completed_batch',completed:1,total:2,batch:1},
      {type:'batch_reply',batch:1,reply:'Found first issue'},
      {type:'progress',phase:'completed_batch',completed:2,total:2,batch:2},
      {type:'batch_reply',batch:2,reply:'Found second issue'},
      {type:'result',result:{status:'completed',completed_batches:2,total_batches:2,
        coverage:{all_eligible_files_included:true},review:{reply:'Batch 1:\nFound first issue\n\nBatch 2:\nFound second issue'}}}
    ].map(x=>JSON.stringify(x)).join('\n')+'\n'});
  });
  await page.getByRole('navigation').getByRole('button',{name:/Chat/}).click();
  await page.getByLabel(/^Local repository/).selectOption('demo');
  await page.getByRole('textbox',{name:'Message',exact:true}).fill('Review the entire project');
  await page.getByRole('button',{name:/Send message/}).click();
  await expect(page.getByRole('region',{name:'Chat project context approval'})).toBeVisible();
  await expect(page.getByText('1 source files · 2 potentially billable model calls')).toBeVisible();
  expect(requests).toEqual(['prepare']);
  await page.getByRole('checkbox',{name:/I inspected the exact source context/}).check();
  await page.getByRole('button',{name:'Approve and analyze project'}).click();
  await expect(page.locator('.bubble.assistant')).toContainText('Found second issue');
  expect(requests).toEqual(['prepare','execute']);
});

test('Changing the model invalidates pending in-chat source approval',async({page})=>{
  let executed=0;
  await page.route('**/api/copilot/review/prepare',route=>route.fulfill({json:{
    repository:'demo',model:models[0],agent:route.request().postDataJSON().agent||null,scope:'focused',prompt:'Fixture snapshot',sha256:'a'.repeat(64),
    files:['App.java'],batch_count:1,warning:'One provider call',approval_required:true,
    agent_profile:null,agent_profile_sha256:null}}));
  page.on('request',r=>{if(r.url().endsWith('/api/copilot/review/execute'))executed++;});
  await page.getByRole('navigation').getByRole('button',{name:/Chat/}).click();
  await page.getByLabel(/^Copilot model/).selectOption(models[0]);
  await page.getByLabel(/^Local repository/).selectOption('demo');
  await page.getByRole('textbox',{name:'Message',exact:true}).fill('Analyze my project');
  await page.getByRole('button',{name:/Send message/}).click();
  await expect(page.getByRole('checkbox',{name:/I inspected the exact source context/})).toBeVisible();
  await page.getByRole('button',{name:'Toggle session details'}).click();
  await page.getByLabel(/^Copilot model/).selectOption(models[1]);
  await expect(page.getByRole('region',{name:'Chat project context approval'})).toHaveCount(0);
  expect(executed).toBe(0);
});


test('Benchmarks runs approved paired read-only Copilot A/B and never invents a winner',async({page})=>{
  const calls:string[]=[];
  await page.route('**/api/benchmark/prepare',async route=>{
    calls.push('prepare');
    expect(route.request().postDataJSON()).toMatchObject({
      repository:'demo',mode:'review',model:models[0],agent:'java-reviewer'});
    await route.fulfill({json:{
      repository:'demo',mode:'review',model:models[0],agent:'java-reviewer',
      task:'Read-only code review',sha256:'a'.repeat(64),source_sha256:'b'.repeat(64),
      approval_required:true,source_transmitted:false,total_model_calls:2,
      warning:'Fixture; two potentially billable calls',
      baseline:{sha256:'c'.repeat(64),prompt:'Baseline fixture source',files:['App.java'],
        batch_count:1,agent:null,agent_profile:null,
        coverage:{scope:'fixture',all_eligible_files_included:true,omitted:[],excluded:[]}},
      daeloryn:{sha256:'d'.repeat(64),prompt:'Agent fixture source',files:['App.java'],
        batch_count:1,agent:'java-reviewer',agent_profile:'trusted fixture agent',
        coverage:{scope:'fixture',all_eligible_files_included:true,omitted:[],excluded:[]}}
    }});
  });
  await page.route('**/api/benchmark/start',async route=>{
    calls.push('start');
    expect(route.request().postDataJSON()).toMatchObject({
      repository:'demo',model:models[0],agent:'java-reviewer',approved_sha256:'a'.repeat(64)});
    await route.fulfill({status:202,json:{
      run_id:'f'.repeat(32),status:'running',created_at:'2026-11-01T18:00:00+00:00'}});
  });
  await page.route('**/api/benchmark/runs',route=>route.fulfill({json:{runs:[{
    run_id:'f'.repeat(32),status:'completed',repository:'demo',mode:'review',
    model:models[0],agent:'java-reviewer',created_at:'2026-11-01T18:00:00+00:00',
    updated_at:'2026-11-01T18:01:00+00:00'}]}}));
  await page.route('**/api/benchmark/runs/*',route=>route.fulfill({json:{
    run_id:'f'.repeat(32),status:'completed',repository:'demo',mode:'review',
    model:models[0],agent:'java-reviewer',created_at:'2026-11-01T18:00:00+00:00',
    updated_at:'2026-11-01T18:01:00+00:00',
    arms:{
      baseline:{status:'completed',completed_batches:1,total_batches:1,reply:'Baseline found A',failure:null},
      daeloryn:{status:'completed',completed_batches:1,total_batches:1,reply:'Daeloryn found A and B',failure:null}
    },
    result:{kind:'paired-source-review-observation',status:'completed',
      model:models[0],agent:'java-reviewer',source_sha256:'b'.repeat(64),
      winner:'not_determined',independent_checks_executed:false,
      model_identity_verified:false,agent_selection_verified:false,
      warning:'Requires human review.',
      arms:{baseline:{status:'completed',completed_batches:1,total_batches:1,review:{reply:''}},
        daeloryn:{status:'completed',completed_batches:1,total_batches:1,review:{reply:''}}}}
  }}));

  await page.getByRole('navigation').getByRole('button',{name:/Benchmarks/}).click();
  const runner=page.getByRole('region',{name:'Paired benchmark runner'});
  await runner.getByLabel('Benchmark project').selectOption('demo');
  await runner.getByRole('button',{name:'Prepare A/B benchmark'}).click();
  await expect(runner.getByText(/2 potentially billable model calls/)).toBeVisible();
  expect(calls).toEqual(['prepare']);
  await runner.getByRole('checkbox',{name:/I inspected both exact prompts/}).check();
  await runner.getByRole('button',{name:'Approve & run A/B'}).click();
  await expect(runner.getByText('Winner: Not determined')).toBeVisible();
  await expect(runner.getByText('Daeloryn found A and B')).toBeVisible();
  await page.getByRole('navigation').getByRole('button',{name:/Overview/}).click();
  await page.getByRole('navigation').getByRole('button',{name:/Benchmarks/}).click();
  await expect(page.getByRole('region',{name:'Saved benchmark runs'}).getByLabel('Saved benchmark run')).toHaveValue('f'.repeat(32));
  await expect(page.getByText('Daeloryn found A and B')).toBeVisible();
  await expect(runner.getByText('Baseline found A')).toBeVisible();
  expect(calls).toEqual(['prepare','start']);
  await expect(runner.getByText('No reviewed result yet')).toBeVisible();
  await runner.getByLabel('baseline confirmed defects').fill('1');
  await runner.getByLabel('baseline false positives').fill('2');
  await runner.getByLabel('baseline evidence references').fill('App.java:1 baseline reviewed');
  await runner.getByLabel('daeloryn confirmed defects').fill('2');
  await runner.getByLabel('daeloryn false positives').fill('1');
  await runner.getByLabel('daeloryn evidence references').fill('App.java:1 specialist reviewed');
  await runner.getByRole('checkbox',{name:/I manually checked source evidence/}).check();
  await expect(runner.getByText(/Human-assessed pilot advantage: Daeloryn/)).toBeVisible();
  await expect(runner.getByText('Winner: Not determined')).toBeVisible();
});

test('Benchmarks cannot call Copilot before explicit approval',async({page})=>{
  let executions=0;
  page.on('request',request=>{if(request.url().endsWith('/api/benchmark/start'))executions++;});
  await page.getByRole('navigation').getByRole('button',{name:/Benchmarks/}).click();
  const runner=page.getByRole('region',{name:'Paired benchmark runner'});
  await expect(runner.getByRole('button',{name:'Prepare A/B benchmark'})).toBeDisabled();
  await runner.getByLabel('Benchmark project').selectOption('demo');
  await runner.getByLabel('Benchmark type').selectOption('fix-plan');
  await expect(runner.getByText(/Patches, builds and regression tests are not executed/)).toBeVisible();
  expect(executions).toBe(0);
});


test('Smart Context keeps greetings text-only with local per-message timestamps',async({page})=>{
  let prepared=0,chats=0;
  page.on('request',r=>{
    if(r.url().endsWith('/api/copilot/review/prepare'))prepared++;
    if(r.url().endsWith('/api/copilot/chat'))chats++;
  });
  await page.getByRole('navigation').getByRole('button',{name:/Chat/}).click();
  await page.getByLabel(/^Local repository/).selectOption('demo');
  await page.getByLabel(/^Context behavior/).selectOption('smart');
  await page.getByRole('textbox',{name:'Message',exact:true}).fill('Hello');
  await page.getByRole('button',{name:/Send message/}).click();
  await expect(page.locator('.bubble.assistant')).toContainText('Fixture reply');
  expect(chats).toBe(1);
  expect(prepared).toBe(0);
  const userTime=page.locator('.bubble.user time').last();
  const assistantTime=page.locator('.bubble.assistant time').last();
  await expect(userTime).toHaveAttribute('datetime',/^\d{4}-\d{2}-\d{2}T/);
  await expect(assistantTime).toHaveAttribute('datetime',/^\d{4}-\d{2}-\d{2}T/);
  const timestamp=await assistantTime.getAttribute('datetime');
  await page.reload();
  await page.getByRole('navigation').getByRole('button',{name:/Chat/}).click();
  await expect(page.locator('.bubble.assistant time').last()).toHaveAttribute('datetime',timestamp!);
});

test('Smart Context prepares focused project excerpts for scoped questions',async({page})=>{
  const requests:string[]=[];
  await page.route('**/api/copilot/review/prepare',route=>{
    const selection=route.request().postDataJSON();
    requests.push(selection.scope);
    expect(selection).toMatchObject({repository:'demo',scope:'focused',task:'What observability does this project have?'});
    return route.fulfill({json:{...selection,model:models[0],
      prompt:'Only README + TelemetryService',sha256:'a'.repeat(64),
      agent:selection.agent||null,agent_profile:null,agent_profile_sha256:null,
      files:['README.md','TelemetryService.java'],batch_count:1,
      approval_required:true,warning:'One model call',
      verified_usage_credits:null,coverage:{scope:'Focused context only',all_eligible_files_included:false,omitted:[],excluded:[]}}});
  });
  await page.getByRole('navigation').getByRole('button',{name:/Chat/}).click();
  await page.getByLabel(/^Local repository/).selectOption('demo');
  await page.getByRole('textbox',{name:'Message',exact:true}).fill('What observability does this project have?');
  await page.getByRole('button',{name:/Send message/}).click();
  await expect(page.getByRole('heading',{name:/Focused project context/})).toBeVisible();
  await expect(page.getByText('Estimated AI Credit charge: unavailable', {exact:false})).toBeVisible();
  expect(requests).toEqual(['focused']);
});

test('Progressive answers auto-scroll while near bottom but respect manual scroll up',async({page})=>{
  await page.route('**/api/copilot/chat',route=>route.fulfill({json:{
    reply:Array.from({length:230},(_,i)=>'Long response line '+i+' · testing line by line scrolling').join('\n')
  }}));
  await page.getByRole('navigation').getByRole('button',{name:/Chat/}).click();
  await page.getByLabel(/^Copilot model/).selectOption(models[0]);
  await page.getByRole('textbox',{name:'Message',exact:true}).fill('Explain the Java collections API');
  await page.getByRole('button',{name:/Send message/}).click();
  const scroll=page.locator('.chat-messages');
  await expect(page.getByText('Displaying completed provider response…')).toBeVisible();
  await expect.poll(async()=>scroll.evaluate(el=>el.scrollHeight-el.clientHeight)).toBeGreaterThan(100);
  await expect.poll(async()=>scroll.evaluate(el=>el.scrollHeight-el.scrollTop-el.clientHeight)).toBeLessThan(110);
  await scroll.evaluate(el=>{el.scrollTop=0;el.dispatchEvent(new Event('scroll'));});
  await page.waitForTimeout(250);
  const afterManual=await scroll.evaluate(el=>el.scrollTop);
  expect(afterManual).toBeLessThan(30);
  await scroll.evaluate(el=>{el.scrollTop=el.scrollHeight;el.dispatchEvent(new Event('scroll'));});
  await expect.poll(async()=>scroll.evaluate(el=>el.scrollHeight-el.scrollTop-el.clientHeight)).toBeLessThan(110);
});


test('delete exactly one selected chat with confirmation; preserve other conversations',async({page})=>{
  await page.getByRole('navigation').getByRole('button',{name:/Chat/}).click();
  await page.getByRole('button',{name:/New chat/i}).click();
  await page.getByRole('button',{name:/New chat/i}).click();
  const before=await page.locator('.history-row').count();
  expect(before).toBeGreaterThan(2);
  await page.locator('.history-row').first().getByRole('button',{name:/Delete chat/}).click();
  await expect(page.getByText(/Delete this chat permanently/)).toBeVisible();
  await page.locator('.history-row').first().getByRole('button',{name:'Cancel'}).click();
  expect(await page.locator('.history-row').count()).toBe(before);
  await page.locator('.history-row').first().getByRole('button',{name:/Delete chat/}).click();
  await page.locator('.history-row').first().getByRole('button',{name:'Confirm delete'}).click();
  expect(await page.locator('.history-row').count()).toBe(before-1);
  await page.reload();
  expect(await page.locator('.history-row').count()).toBe(before-1);
  await expect(page.getByRole('navigation').getByRole('button',{name:/Benchmarks/})).toBeVisible();
});

test('Overview uses discovered models, never hardcodes connected sessions',async({page})=>{
  await expect(page.getByText('Discovered models',{exact:true})).toBeVisible();
  const metric=page.locator('.metric').filter({hasText:'Discovered models'});
  await expect(metric).toContainText('2');
  await expect(metric).toContainText('Copilot: 2');
  await page.getByRole('navigation').getByRole('button',{name:/Models/}).click();
  await expect(page.getByText('Discovered model catalogs')).toBeVisible();
  await expect(page.getByText(models.join(', '))).toBeVisible();
});

test('Workflow shows real recorded batches and never checks off unsupported patch/publish stages',async({page})=>{
  const run='e'.repeat(32);
  await page.route('**/api/benchmark/runs',route=>route.fulfill({json:{runs:[{
    run_id:run,status:'partial',repository:'demo',mode:'review',model:models[0],agent:'java-reviewer',
    created_at:'2026-11-01T18:00:00+00:00',updated_at:'2026-11-01T18:01:00+00:00'}]}}));
  await page.route('**/api/benchmark/runs/*',route=>route.fulfill({json:{
    run_id:run,status:'partial',repository:'demo',mode:'review',model:models[0],agent:'java-reviewer',
    source_sha256:'a'.repeat(64),approved_sha256:'b'.repeat(64),
    created_at:'2026-11-01T18:00:00+00:00',updated_at:'2026-11-01T18:01:00+00:00',
    error:'Partial benchmark, pending manual investigation',
    arms:{baseline:{status:'completed',completed_batches:2,total_batches:2,reply:'baseline',failure:null},
      daeloryn:{status:'partial',completed_batches:1,total_batches:2,reply:'partial',
        failure:'Provider call failed, no retry'}},
    result:{status:'partial',independent_checks_executed:false}
  }}));
  await page.getByRole('navigation').getByRole('button',{name:/Workflows/}).click();
  const guide=page.getByRole('region',{name:'Engineering workflow',exact:true});
  await expect(guide.getByText('Completed 2/2 batches')).toBeVisible();
  await expect(guide.getByText('Partial / failed 1/2 batches')).toBeVisible();
  await expect(guide.getByText('Not available in read-only pilot')).toBeVisible();
  await expect(guide.getByText('Not executed by this workflow')).toBeVisible();
  await expect(guide.getByRole('checkbox')).toHaveCount(0);
  await expect(guide.getByRole('list',{name:'Workflow execution stages'}).getByRole('listitem')).toHaveCount(6);
  await expect(guide.getByRole('progressbar',{name:'Verified source review stages'})).toHaveAttribute('aria-valuenow','2');
  // New layout is a compact timeline, rather than six tall 3-column boxes.
  const desktopRows=await guide.locator('.workflow-step').first().boundingBox();
  expect(desktopRows).not.toBeNull();
  expect(desktopRows!.height).toBeLessThan(110);
  await page.setViewportSize({width:760,height:900});
  await expect(guide.getByRole('list',{name:'Workflow execution stages'}).getByRole('listitem')).toHaveCount(6);
  const layout=await guide.locator('.workflow-timeline').evaluate(element=>{
    const style=getComputedStyle(element);
    return {columns:style.gridTemplateColumns,
      overflowing:element.scrollWidth>element.clientWidth+1};
  });
  expect(layout.overflowing).toBe(false);
  expect(layout.columns.trim().split(/\s+/).length).toBe(1);
});


test('Stop benchmark requests backend cancellation without deleting the run',async({page})=>{
  const id='d'.repeat(32);
  const calls:string[]=[];
  let state='running';
  await page.route('**/api/benchmark/runs',route=>route.fulfill({json:{runs:[{
    run_id:id,status:state,repository:'demo',mode:'review',model:models[0],
    agent:'java-reviewer',created_at:'2026-11-01T18:00:00+00:00',
    updated_at:'2026-11-01T18:01:00+00:00'}]}}));
  await page.route('**/api/benchmark/runs/*/stop',route=>{
    calls.push('stop');
    expect(route.request().postDataJSON()).toEqual({});
    state='stopping';
    return route.fulfill({json:{run_id:id,status:state}});
  });
  await page.route('**/api/benchmark/runs/*',route=>route.fulfill({json:{
    run_id:id,status:state,repository:'demo',mode:'review',model:models[0],
    agent:'java-reviewer',created_at:'2026-11-01T18:00:00+00:00',
    updated_at:'2026-11-01T18:01:00+00:00',
    error:null,arms:{baseline:{status:'running',completed_batches:1,total_batches:52,reply:'Batch 1: finding'},
      daeloryn:{status:'pending',completed_batches:0,total_batches:52,reply:''}}
  }}));
  await page.getByRole('navigation').getByRole('button',{name:/Benchmarks/}).click();
  const runner=page.getByRole('region',{name:'Paired benchmark runner'});
  await expect(runner.getByRole('button',{name:'Stop run'})).toBeVisible();
  await expect(runner.getByText('running · 1/52 batches',{exact:true})).toBeVisible();
  await runner.getByRole('button',{name:'Stop run'}).click();
  await expect(runner.getByText(/Stopping: in-flight provider calls/)).toBeVisible();
  expect(calls).toEqual(['stop']);
  await expect(runner.getByRole('button',{name:'Delete run'})).toHaveCount(0);
});

test('Delete benchmark requires confirmation and removes only selected completed receipt',async({page})=>{
  const run='c'.repeat(32);
  let deleted=false;
  const posts:string[]=[];
  await page.route('**/api/benchmark/runs',route=>route.fulfill({json:{runs:deleted?[]:[{
    run_id:run,status:'partial',repository:'demo',mode:'review',
    model:models[0],agent:'java-reviewer',created_at:'2026-11-01T18:00:00+00:00',
    updated_at:'2026-11-01T18:01:00+00:00'}]}}));
  await page.route('**/api/benchmark/runs/*/delete',route=>{
    posts.push('delete');
    expect(route.request().postDataJSON()).toEqual({});
    deleted=true;
    return route.fulfill({json:{run_id:run,deleted:true}});
  });
  await page.route('**/api/benchmark/runs/*',route=>route.fulfill({json:{
    run_id:run,status:'partial',repository:'demo',mode:'review',model:models[0],
    agent:'java-reviewer',created_at:'2026-11-01T18:00:00+00:00',
    updated_at:'2026-11-01T18:01:00+00:00',
    error:'Provider time budget reached',
    arms:{baseline:{status:'partial',completed_batches:4,total_batches:52,reply:'Some findings'},
      daeloryn:{status:'pending',completed_batches:0,total_batches:52,reply:''}}
  }}));
  await page.getByRole('navigation').getByRole('button',{name:/Benchmarks/}).click();
  const runner=page.getByRole('region',{name:'Paired benchmark runner'});
  await runner.getByRole('button',{name:'Delete run'}).click();
  const confirmation=runner.getByRole('group',{name:'Confirm delete benchmark run'});
  await expect(confirmation).toBeVisible();
  await confirmation.getByRole('button',{name:'Cancel'}).click();
  expect(posts).toEqual([]);
  await runner.getByRole('button',{name:'Delete run'}).click();
  await confirmation.getByRole('button',{name:'Confirm delete run'}).click();
  await expect(runner.getByText(/No saved runs yet/)).toBeVisible();
  expect(posts).toEqual(['delete']);
});


test('follow-up after large full review is bounded below HTTP 413 and keeps local history',async({page})=>{
  let count=0;
  const bodies:any[]=[];
  const huge='Batch 1: source finding\n'+('Source reference and rationale. '.repeat(2000));
  await page.route('**/api/copilot/chat',async route=>{
    bodies.push(route.request().postDataJSON());
    count++;
    await route.fulfill({json:{reply:count===1?huge:'Focused follow-up answer'}});
  });
  await page.getByRole('navigation').getByRole('button',{name:/Chat/}).click();
  await page.getByRole('textbox',{name:'Message',exact:true}).fill('Explain a Java collection');
  await page.getByRole('button',{name:/Send message/}).click();
  await expect.poll(()=>page.locator('.bubble.assistant').count()).toBeGreaterThan(0);
  const input=page.getByRole('textbox',{name:'Message',exact:true});
  await input.fill('Explain Java Optional');
  await page.getByRole('button',{name:/Send message/}).click();
  await expect(page.getByText('Focused follow-up answer')).toBeVisible();
  expect(bodies).toHaveLength(2);
  expect(bodies[1].messages).toEqual([
    {role:'user',content:'Explain a Java collection'},
    {role:'user',content:'Explain Java Optional'}
  ]);
  expect(new TextEncoder().encode(JSON.stringify(bodies[1])).byteLength).toBeLessThan(24576);
  await expect(page.getByText(/older\/oversized messages omitted from Copilot request/)).toBeVisible();
  await expect(page.locator('.bubble.assistant')).toHaveCount(2);
});

test('pom version question with selected checkout requires focused source approval',async({page})=>{
  let plainChatRequests=0;
  page.on('request',request=>{if(request.url().endsWith('/api/copilot/chat'))plainChatRequests++;});
  let scope='';
  await page.route('**/api/copilot/review/prepare',route=>{
    scope=route.request().postDataJSON().scope;
    expect(route.request().postDataJSON()).toMatchObject({
      repository:'demo',scope:'focused',task:'check pom does it has bugs or deprecated libraries?'});
    return route.fulfill({json:{...route.request().postDataJSON(),model:models[0],
      prompt:'pom.xml only',sha256:'a'.repeat(64),
      files:['pom.xml'],batch_count:1,approval_required:true,
      agent_profile:null,agent_profile_sha256:null,source_transmitted:false,
      coverage:{scope:'focused file selection',all_eligible_files_included:false,omitted:[],excluded:[]}}});
  });
  await page.getByRole('navigation').getByRole('button',{name:/Chat/}).click();
  await page.getByLabel(/^Local repository/).selectOption('demo');
  await page.getByLabel('Context behavior').selectOption('smart');
  await page.getByRole('textbox',{name:'Message',exact:true}).fill('check pom does it has bugs or deprecated libraries?');
  await page.getByRole('button',{name:/Send message/}).click();
  await expect(page.getByRole('region',{name:'Chat project context approval'})).toBeVisible();
  await expect(page.getByRole('heading',{name:/Focused project context/})).toBeVisible();
  expect(scope).toBe('focused');
  expect(plainChatRequests).toBe(0);
});


test('Chat presents natural prose with code only inside a copyable code box',async({page})=>{
  await page.route('**/api/copilot/chat',route=>route.fulfill({json:{
    reply:'## Explanation\n\n**Use this code** in Java:\n\n`'.replace('`','`'.repeat(3))+
      'java\nclass Example {}\n'+ '`'.repeat(3)+'\n\nThat is all.'
  }}));
  await page.getByRole('navigation').getByRole('button',{name:/Chat/}).click();
  await page.getByRole('textbox',{name:'Message',exact:true}).fill('Explain a simple example');
  await page.getByRole('button',{name:/Send message/}).click();
  const reply=page.locator('.bubble.assistant').last();
  await expect(reply.getByText('Explanation')).toBeVisible();
  await expect(reply.getByRole('region',{name:'Code snippet'})).toBeVisible();
  await expect(reply.locator('pre code')).toContainText('class Example {}');
  await expect(reply.getByRole('button',{name:'Copy code'})).toBeEnabled();
  await expect(reply).not.toContainText('## Explanation');
  await expect(reply).not.toContainText('**Use this code**');
});

test('Smart code review selects Java Reviewer and Inspector receives safe links by batch',async({page})=>{
  const approvedBlock=JSON.stringify({
    file:'App.java',line:1,column:1,end_line:4,
    source:'class App {\n  String x;\n  String read(){ return x.toString(); }\n}\n'
  });
  let requestedAgent='';
  await page.route('**/api/copilot/review/prepare',route=>{
    const selection=route.request().postDataJSON();
    requestedAgent=selection.agent;
    expect(selection).toMatchObject({repository:'demo',scope:'focused',agent:'java-reviewer'});
    return route.fulfill({json:{...selection,model:models[0],prompt:approvedBlock,
      sha256:'a'.repeat(64),files:['App.java'],batch_count:1,warning:'One review call',
      agent_profile:'trusted agent',agent_profile_sha256:'b'.repeat(64),
      approval_required:true,coverage:{scope:'focused',all_eligible_files_included:false,omitted:[],excluded:[]}}});
  });
  await page.route('**/api/copilot/review/execute',route=>route.fulfill({
    contentType:'application/x-ndjson',body:[
      {type:'progress',phase:'completed_batch',completed:1,total:1,batch:1},
      {type:'batch_reply',batch:1,reply:'Possible null dereference at App.java:3 (verify preconditions).'},
      {type:'result',result:{status:'completed',completed_batches:1,total_batches:1,
        review:{reply:'Possible null dereference at App.java:3 (verify preconditions).'},
        coverage:{all_eligible_files_included:false}}}
    ].map(x=>JSON.stringify(x)).join('\n')+'\n'
  }));
  await page.getByRole('navigation').getByRole('button',{name:/Chat/}).click();
  await page.getByLabel(/^Local repository/).selectOption('demo');
  await page.getByRole('textbox',{name:'Message',exact:true}).fill('Review Java class for bugs');
  await page.getByRole('button',{name:/Send message/}).click();
  await expect(page.getByRole('region',{name:'Chat project context approval'})).toBeVisible();
  await expect(page.getByRole('complementary',{name:'Code Inspector'})).toBeVisible();
  expect(requestedAgent).toBe('java-reviewer');
  await page.getByRole('checkbox',{name:/I inspected the exact source context/}).check();
  await page.getByRole('button',{name:'Approve and analyze project'}).click();
  const inspector=page.getByRole('complementary',{name:'Code Inspector'});
  const link=inspector.getByRole('button',{name:/App.java:3/});
  await expect(link).toBeVisible();
  await link.click();
  await expect(inspector.locator('.inspector-code-target')).toContainText('x.toString()');
  await expect(inspector.locator('.inspector-code-bug')).toContainText('x.toString()');
  await expect(inspector.getByText(/Highlighted: possible bug/)).toBeVisible();
  await inspector.getByRole('button',{name:'Full screen Code Inspector'}).click();
  await expect(page.getByRole('dialog',{name:'Code Inspector'})).toBeVisible();
  await expect(page.locator('.code-inspector-fullscreen .inspector-code-bug')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('complementary',{name:'Code Inspector'})).toBeVisible();
  await inspector.getByRole('button',{name:'Full screen Code Inspector'}).click();
  await inspector.getByRole('button',{name:'Exit full screen Code Inspector'}).click();
  await expect(page.locator('.code-inspector-fullscreen')).toHaveCount(0);
  await page.getByRole('button',{name:'Toggle session details'}).click();
  await expect(page.getByLabel(/^Agent/)).toHaveValue('java-reviewer');
});

test('Docs only prepares only docs and never requests a full source scan',async({page})=>{
  const requests:string[]=[];
  await page.route('**/api/copilot/review/prepare',route=>{
    const body=route.request().postDataJSON();
    requests.push(body.scope);
    expect(body).toMatchObject({repository:'demo',scope:'docs'});
    return route.fulfill({json:{...body,model:models[0],sha256:'a'.repeat(64),
      prompt:JSON.stringify({file:'README.md',line:1,column:1,end_line:1,source:'# Documentation'}),
      files:['README.md'],batch_count:1,warning:'Docs only',approval_required:true,
      agent_profile:null,agent_profile_sha256:null,
      coverage:{scope:'Markdown only',all_eligible_files_included:false,omitted:[],excluded:[]}}});
  });
  await page.getByRole('navigation').getByRole('button',{name:/Chat/}).click();
  await page.getByLabel(/^Local repository/).selectOption('demo');
  await page.getByLabel('Context behavior').selectOption('docs');
  await page.getByRole('textbox',{name:'Message',exact:true}).fill('Explain project documentation');
  await page.getByRole('button',{name:/Send message/}).click();
  await expect(page.getByRole('heading',{name:/Docs-only project context/})).toBeVisible();
  expect(requests).toEqual(['docs']);
  await expect(page.getByText(/No source code inspected/)).toBeVisible();
});


test('Benchmarks resume same partial run ID and require explicit approval of unknown batch',async({page})=>{
  const runId='d'.repeat(32);
  let resumes=0;
  await page.route('**/api/benchmark/runs',route=>route.fulfill({json:{runs:[{
    run_id:runId,status:'partial',repository:'demo',mode:'review',model:models[0],agent:'java-reviewer',
    created_at:'2026-11-01T18:00:00+00:00',updated_at:'2026-11-01T18:01:00+00:00'}]}}));
  await page.route('**/api/benchmark/runs/*',route=>{
    if(route.request().method()!=='GET')return route.fallback();
    return route.fulfill({json:{
      run_id:runId,status:'partial',repository:'demo',mode:'review',model:models[0],agent:'java-reviewer',
      source_sha256:'a'.repeat(64),approved_sha256:'b'.repeat(64),
      created_at:'2026-11-01T18:00:00+00:00',updated_at:'2026-11-01T18:01:00+00:00',
      error:'Partial. Unknown batch 2.',
      arms:{
        baseline:{status:'partial',completed_batches:1,total_batches:3,reply:'Completed first result',
          failure:'Unknown batch 2',batches:{'1':{status:'completed',reply:'Completed first result'},
            '2':{status:'unknown',reply:''}}},
        daeloryn:{status:'pending',completed_batches:0,total_batches:3,reply:'',
          failure:null,batches:{}}
      },result:null
    }});
  });
  await page.route('**/api/benchmark/runs/*/resume',route=>{
    resumes++;
    expect(route.request().postDataJSON()).toEqual({
      approved_sha256:'b'.repeat(64),acknowledge_unknown:true
    });
    return route.fulfill({status:202,json:{run_id:runId,status:'running'}});
  });
  await page.getByRole('navigation').getByRole('button',{name:/Benchmarks/}).click();
  const runner=page.getByRole('region',{name:'Paired benchmark runner'});
  await expect(runner.getByRole('button',{name:'Resume remaining batches'})).toBeVisible();
  await runner.getByRole('button',{name:'Resume remaining batches'}).click();
  await expect(runner.getByRole('group',{name:'Confirm resume benchmark run'})).toBeVisible();
  await expect(runner.getByRole('button',{name:'Approve & resume saved run'})).toBeDisabled();
  await runner.getByRole('checkbox',{name:/UNKNOWN attempts/}).check();
  await runner.getByRole('button',{name:'Approve & resume saved run'}).click();
  await expect.poll(()=>resumes).toBe(1);
  await expect(runner.getByText(/Resuming dddddddd/)).toBeVisible();
});

test('Comparison results shows persisted evidence scores and no fabricated verified winner',async({page})=>{
  const rows=[{run_id:'c'.repeat(32),repository:'demo',mode:'review',model:models[0],
    agent:'java-reviewer',status:'completed',evaluation_status:'provisional_traceability',
    provisional_evidence_lead:'daeloryn',baseline_score:0,daeloryn_score:36,verified_winner:null}];
  await page.route('**/api/benchmarks',route=>route.fulfill({json:{
    agent_count:22,expected_cells:176,observed_cells:0,verified_trial_count:0,
    coverage_percent:0,warning:'No independently certified trials',trials:[],
    paired_comparisons:rows
  }}));
  await page.getByRole('navigation').getByRole('button',{name:/Benchmarks/}).click();
  const table=page.getByRole('region',{name:'Comparison results'});
  await expect(table.getByText('36/100')).toBeVisible();
  await expect(table.getByText('0/100')).toBeVisible();
  await expect(table.getByText(/Not verified · no independent defect/)).toBeVisible();
  await expect(table.getByText('daeloryn')).toBeVisible();
});
