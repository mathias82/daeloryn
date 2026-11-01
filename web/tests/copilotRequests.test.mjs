import {test} from 'node:test';
import assert from 'node:assert/strict';
import {chatRequest,boundedChatRequest,reviewRequest,reviewSelectionKey,selectedAgent} from '../.test-build/copilotRequests.js';

test('Copilot chat sends selected Sonnet and java-reviewer together',()=>{
  assert.deepEqual(chatRequest('claude-sonnet-4',[{role:'user',content:'Review Java'}],selectedAgent('java-reviewer')),
    {model:'claude-sonnet-4',messages:[{role:'user',content:'Review Java'}],agent:'java-reviewer'});
});
test('generic chat and automatic recommendation do not select an agent',()=>{
  assert.equal('agent' in chatRequest('auto',[],selectedAgent('Automatic (preview)')),false);
});
test('source-review prepare and execute bind identical selection',()=>{
  const selection={repository:'demo',task:'Review',model:'claude-sonnet-4',agent:'java-reviewer'};
  assert.deepEqual(reviewRequest(selection),selection);
  assert.deepEqual(reviewRequest(selection,'digest'),{...selection,approved_sha256:'digest'});
  assert.throws(()=>reviewRequest({...selection,model:''}));
  assert.equal(reviewRequest({...selection,model:'auto'}).model,'auto'); // resolved to a concrete model at preparation time
});
test('every source-review selection change resets approval component identity',()=>{
  const selection={repository:'demo',task:'Review',model:'claude-sonnet-4',agent:'java-reviewer'};
  const key=reviewSelectionKey(selection);
  for (const [field,value] of Object.entries({repository:'other',task:'New',model:'claude-haiku-4',agent:'java-developer'}))
    assert.notEqual(reviewSelectionKey({...selection,[field]:value}),key);
});


test('large prior full-review transcript does not produce HTTP 413',()=>{
  const huge='Batch 1:\n'+'Confirmed bug with source evidence. '.repeat(4000);
  const prior=[{role:'user',content:'Review entire repository'},
    {role:'assistant',content:huge},
    {role:'user',content:'Check one dependency'}];
  const original=structuredClone(prior);
  const result=boundedChatRequest('claude-sonnet-4',prior,'Explain Maven version resolution','java-reviewer');
  assert.equal(result.omitted,1);
  assert.equal(result.included,2);
  assert.deepEqual(prior,original,'local history is never modified');
  assert.deepEqual(result.request.messages.map(m=>m.content),
    ['Review entire repository','Check one dependency','Explain Maven version resolution']);
  assert.ok(result.requestBytes<=20000);
  assert.ok(result.requestBytes<24576);
});

test('UTF-8 size is bounded, and most recent context is prioritized',()=>{
  const prior=Array.from({length:15},(_,i)=>({role:i%2?'assistant':'user',
    content:('α'.repeat(2500))+' turn '+i}));
  const result=boundedChatRequest('auto',prior,'Does this compile?');
  assert.ok(result.requestBytes<=20000);
  assert.ok(result.request.messages.length<=11);
  assert.equal(result.omitted+result.included,15);
  assert.equal(result.request.messages.at(-1).content,'Does this compile?');
  assert.equal(result.request.messages.at(-2).content,prior.at(-1).content);
});
test('current oversized request fails locally rather than sending incomplete source',()=>{
  assert.throws(()=>boundedChatRequest('auto',[],'x'.repeat(3001)),/3000/);
  assert.throws(()=>boundedChatRequest('auto',[],'  '),/3000/);
});
