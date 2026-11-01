import {test} from 'node:test';
import assert from 'node:assert/strict';
import {routeContext} from '../.test-build/smartContext.js';

test('greetings and general questions never request repository files',()=>{
  for (const text of ['Hello','hello!', 'γειά σου', 'Καλημέρα', 'Thanks',
    'Explain dependency injection','Explain Kafka','What is observability?','What time is it?','Tell me a joke','Thanks for the project advice']) {
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
  assert.equal(routeContext('Hello','docs'), 'none');
  assert.equal(routeContext('Explain project structure','docs'), 'docs');
  assert.equal(routeContext('Review the entire project','docs'), 'docs');
});


test('build-file follow-ups use focused approved project context',()=>{
  for(const task of ['check pom does it has bugs or deprecated libraries?',
    'Review pom.xml dependencies and versions', 'Inspect build.gradle.kts plugins']) {
      assert.equal(routeContext(task),'focused',task);
  }
  assert.equal(routeContext('Explain Maven generally'),'none');
});

test('code reviews are focused unless whole-project wording is explicit',()=>{
 for(const task of ['Can you analyze for bugs?', 'Review my Java project for bugs',
   'check pom does it has bugs or deprecated libraries?', 'Inspect a Spring service']) {
   assert.equal(routeContext(task),'focused',task);
 }
 assert.equal(routeContext('Perform a full scan of the entire project'),'full');
 assert.equal(routeContext('What is Java?'),'none');
});

test('Greek requests to inspect code or identify classes prepare project context',()=>{
 for(const task of ['χρησιμοποιησε εργαλεια να δεις τον κωδικα και πες μου ποιες ειναι','ποιες είναι οι κλάσεις του project;','διάβασε τον κώδικα','δείξε τις κλάσεις'])assert.equal(routeContext(task),'focused');
 assert.equal(routeContext('διάβασε τον κώδικα','text-only'),'none');
 assert.equal(routeContext('χρησιμοποίησε εργαλεία να δεις τον κώδικα','docs'),'docs');
});


test('read and list project classes never fall through to plain chat',()=>{
 for(const task of ['read the project class and send me the classes','list the project classes','read my code','list classes in the project','list classes','show methods'])assert.equal(routeContext(task),'focused');
 assert.equal(routeContext('read the project class and send me the classes','text-only'),'none');
});
