import {test} from 'node:test';
import assert from 'node:assert/strict';
import {routeContext} from '../.test-build/smartContext.js';

test('greetings and general questions never request repository files',()=>{
  for (const text of ['Hello','hello!', 'γειά σου', 'Καλημέρα', 'Thanks',
    'Explain dependency injection','What time is it?','Tell me a joke','Thanks for the project advice']) {
    assert.equal(routeContext(text), 'none', text);
  }
});
test('repository questions choose focused context by default',()=>{
  for (const text of ['What observability does this project have?',
    'Explain the tracing in the service','Where is kafka configured in the project?',
    'Τι κάνει το project;', 'Πώς υλοποιείται η παρατηρησιμότητα στην εφαρμογή;']) {
    assert.equal(routeContext(text), 'focused', text);
  }
});
test('explicitly complete scans require full context approval',()=>{
  for (const text of ['Review the entire project','Full code review of my repository',
    'Inspect all source files','Κάνε πλήρη ανάλυση της αρχιτεκτονικής του έργου',
    'Σάρωσε τα πάντα στο project']) {
    assert.equal(routeContext(text), 'full', text);
  }
});
test('manual overrides are explicit',()=>{
  assert.equal(routeContext('Hello','text-only'), 'none');
  assert.equal(routeContext('What observability does my project have?','text-only'), 'none');
  assert.equal(routeContext('Hello','full'), 'full');
});
