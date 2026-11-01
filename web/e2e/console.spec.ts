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
  await expect(page.getByText(/Copilot enabled locally · plain chat/)).toBeVisible();
});
