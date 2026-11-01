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

test('Greek full-project bug review enters explicit source approval, not text-only chat',()=>{
  for(const task of [
    'Θέλω να διαβάσεις όλο το project, να βρεις bugs και να προτείνεις λύσεις',
    'Δες όλο το έργο για σφάλματα στον κώδικα',
    'Θέλω να βρεις όλα τα σφάλματα στον κώδικα σε όλο το έργο',
    'Σάρωσε όλο το project για bugs'
  ]) assert.equal(routeContext(task),'full',task);
});
test('Greek class bug questions stay focused; approval and docs override still apply',()=>{
  for(const task of [
    'Θέλω να βρεις σφάλματα στον κώδικα.',
    'Βρες bugs στην κλάση MailConfiguration.java',
    'Έλεγξε την κλάση και εντόπισε σφάλματα.',
    'Πες μου τα προβλήματα στον κώδικα.'
  ]) assert.equal(routeContext(task),'focused',task);
  assert.equal(routeContext('Βρες bugs στον κώδικα','text-only'),'none');
  assert.equal(routeContext('Σάρωσε όλο το έργο','docs'),'docs');
});
