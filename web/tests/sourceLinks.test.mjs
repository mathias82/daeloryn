import {test} from 'node:test';
import assert from 'node:assert/strict';
import {sourceLinkSegments} from '../.test-build/sourceLinks.js';
import {extractSourceReferences} from '../.test-build/sourceInspector.js';

const paths=[
  'src/main/java/gr/pwc/MailConfiguration.java',
  'src/main/java/gr/pwc/ControllerAdvisor.java'
];
test('natural-language Java citation resolves approved path and all line ranges',()=>{
 const text='The strongest finding is in MailConfiguration.java, lines 14-16 and 17-18 (imports) and 51-56. '+ 
  'ControllerAdvisor.java lines 38-45 and 47-60 can leak messages.';
 const pieces=sourceLinkSegments(text,paths);
 const classLink=pieces.find(p=>p.text==='MailConfiguration.java');
 assert.equal(classLink.reference?.file,paths[0]);
 assert.deepEqual(classLink.reference?.ranges,[
  {line:14,endLine:16},{line:17,endLine:18},{line:51,endLine:56}
 ]);
 assert.equal(pieces.filter(p=>p.reference?.file===paths[0]&&p.range).length,3);
 const controller=pieces.find(p=>p.text==='ControllerAdvisor.java');
 assert.deepEqual(controller.reference?.ranges,[
  {line:38,endLine:45},{line:47,endLine:60}
 ]);
 assert.deepEqual(pieces.filter(p=>p.reference?.file===paths[1]&&p.range).map(x=>x.range),[
  {line:38,endLine:45},{line:47,endLine:60}
 ]);
});
test('source citations never create links to unapproved or ambiguous files',()=>{
 const text='NoReference.java:1 and MailConfiguration.java:12';
 const segments=sourceLinkSegments(text,[
  'src/a/MailConfiguration.java','src/b/MailConfiguration.java']);
 assert.equal(segments.filter(s=>s.reference).length,0);
 assert.equal(segments.map(s=>s.text).join(''),text);
});
test('do not invent huge or impossible line ranges',()=>{
 const items=sourceLinkSegments('MailConfiguration.java lines 500-99999',paths);
 const clicked=items.find(x=>x.text==='MailConfiguration.java');
 assert.ok(clicked.reference);
 assert.deepEqual(clicked.reference.ranges,[]);
 assert.equal(items.filter(x=>x.range).length,0);
});
test('model findings and code suggestions can be detected from natural citations',()=>{
 const sources=[{
  file:paths[0],line:14,column:1,end_line:60,
  source:Array.from({length:47},(_,i)=>'line '+(i+14)+'\n').join('')
 }];
 const results=extractSourceReferences(
  'Possible bug in MailConfiguration.java, lines 14–16 and 17–18 (imports) and 51–56.',1,sources);
 assert.ok(results.some(x=>x.file===paths[0]&&x.line===14&&x.endLine===16&&x.verified));
 assert.ok(results.some(x=>x.file===paths[0]&&x.line===17&&x.endLine===18&&x.verified));
 assert.ok(results.some(x=>x.file===paths[0]&&x.line===51&&x.endLine===56&&x.verified));
});
