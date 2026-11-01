import {test} from 'node:test';
import assert from 'node:assert/strict';
import {chatRequest,reviewRequest,reviewSelectionKey,selectedAgent} from '../.test-build/copilotRequests.js';

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
