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
 await page.getByRole('textbox',{name:'Message',exact:true}).fill('Review my Spring starter');
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
    expect(body).toMatchObject({repository:'demo',task:'Review the project',model:'auto'});
    await route.fulfill({json:{repository:'demo',model:models[0],agent:null,
      prompt:'Fixture source snapshot',sha256:'a'.repeat(64),files:['App.java'],
      batch_count:2,warning:'Fixture review has 2 potentially billable calls',
      approval_required:true,agent_profile:null,agent_profile_sha256:null,
      coverage:{all_eligible_files_included:true,scope:'Fixture source',omitted:[],excluded:[]}}});
  });
  await page.route('**/api/copilot/review/execute',async route=>{
    requests.push('execute');
    expect(route.request().postDataJSON()).toMatchObject({
      repository:'demo',task:'Review the project',model:models[0],approved_sha256:'a'.repeat(64)});
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
  await page.getByRole('textbox',{name:'Message',exact:true}).fill('Review the project');
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
    repository:'demo',model:models[0],agent:null,prompt:'Fixture snapshot',sha256:'a'.repeat(64),
    files:['App.java'],batch_count:1,warning:'One provider call',approval_required:true,
    agent_profile:null,agent_profile_sha256:null}}));
  page.on('request',r=>{if(r.url().endsWith('/api/copilot/review/execute'))executed++;});
  await page.getByRole('navigation').getByRole('button',{name:/Chat/}).click();
  await page.getByLabel(/^Copilot model/).selectOption(models[0]);
  await page.getByLabel(/^Local repository/).selectOption('demo');
  await page.getByRole('textbox',{name:'Message',exact:true}).fill('Analyze my project');
  await page.getByRole('button',{name:/Send message/}).click();
  await expect(page.getByRole('checkbox',{name:/I inspected the exact source context/})).toBeVisible();
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
  await page.route('**/api/benchmark/execute',async route=>{
    calls.push('execute');
    expect(route.request().postDataJSON()).toMatchObject({
      repository:'demo',model:models[0],agent:'java-reviewer',approved_sha256:'a'.repeat(64)});
    await route.fulfill({contentType:'application/x-ndjson',body:[
      {type:'arm_started',arm:'baseline',total_batches:1},
      {type:'progress',arm:'baseline',phase:'completed_batch',completed:1,total:1,batch:1},
      {type:'batch_reply',arm:'baseline',batch:1,reply:'Baseline found A'},
      {type:'arm_finished',arm:'baseline',status:'completed'},
      {type:'arm_started',arm:'daeloryn',total_batches:1},
      {type:'batch_reply',arm:'daeloryn',batch:1,reply:'Daeloryn found A and B'},
      {type:'result',result:{kind:'paired-source-review-observation',
        status:'completed',model:models[0],agent:'java-reviewer',
        source_sha256:'b'.repeat(64),winner:'not_determined',
        independent_checks_executed:false,model_identity_verified:false,
        agent_selection_verified:false,warning:'Requires human review.',
        arms:{baseline:{status:'completed',completed_batches:1,total_batches:1,
          review:{reply:'Baseline found A'}},daeloryn:{status:'completed',
          completed_batches:1,total_batches:1,review:{reply:'Daeloryn found A and B'}}}}}
    ].map(x=>JSON.stringify(x)).join('\n')+'\n'});
  });
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
  await expect(runner.getByText('Baseline found A')).toBeVisible();
  expect(calls).toEqual(['prepare','execute']);
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
  page.on('request',request=>{if(request.url().endsWith('/api/benchmark/execute'))executions++;});
  await page.getByRole('navigation').getByRole('button',{name:/Benchmarks/}).click();
  const runner=page.getByRole('region',{name:'Paired benchmark runner'});
  await expect(runner.getByRole('button',{name:'Prepare A/B benchmark'})).toBeDisabled();
  await runner.getByLabel('Benchmark project').selectOption('demo');
  await runner.getByLabel('Benchmark type').selectOption('fix-plan');
  await expect(runner.getByText(/Patches, builds and regression tests are not executed/)).toBeVisible();
  expect(executions).toBe(0);
});
