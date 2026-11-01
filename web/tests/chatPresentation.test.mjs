import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readableProse,splitReply} from '../.test-build/chatPresentation.js';
import {recommendSpecialist} from '../.test-build/agentSelector.js';

test('models render normal readable paragraphs instead of literal Markdown formatting',()=>{
 const blocks=splitReply('## Finding\n\n**This bug** happens in `Service.java`.\n\n- Missing validation\n- Unsafe default');
 assert.equal(blocks.length,1);
 assert.equal(blocks[0].kind,'prose');
 assert.equal(blocks[0].text,'Finding\n\nThis bug happens in Service.java.\n\n• Missing validation\n• Unsafe default');
 assert.equal(readableProse('A [source](https://example.com/src) is **useful**.'),'A source (https://example.com/src) is useful.');
});
test('only fenced source code becomes a dedicated copyable code block',()=>{
 const blocks=splitReply('You can use this small snippet:\n\n`'+'`'.repeat(2)+'java\nclass Hello {}\n'+ '`'.repeat(3)+'\n\nThis fixes the example.');
 assert.deepEqual(blocks.map(b=>b.kind),['prose','code','prose']);
 assert.equal(blocks[1].language,'java');
 assert.equal(blocks[1].text,'class Hello {}');
 assert.equal(blocks[1].closed,true);
});
test('unfinished progressive code fence remains inert, never parsed as HTML',()=>{
 const blocks=splitReply('Example:\n'+'`'.repeat(3)+'ts\n<script>alert(1)</script>');
 assert.equal(blocks[1].kind,'code');
 assert.equal(blocks[1].closed,false);
 assert.match(blocks[1].text,/<script>/);
});
test('trusted specialists reflect task intent without invented agent names',()=>{
 const names=['java-reviewer','spring-framework-expert','react-reviewer','java-architect','security-reviewer'];
 assert.equal(recommendSpecialist('Find Java concurrency bugs',['java'],names).agent,'java-reviewer');
 assert.equal(recommendSpecialist('Check React hooks for bugs',['react'],names).agent,'react-reviewer');
 assert.equal(recommendSpecialist('Review OAuth security',['java'],names).agent,'security-reviewer');
 assert.equal(recommendSpecialist('Fix Java bugs',['java'],[]),null);
});

test('explicit implementations select trusted developer while bug analysis stays reviewer',()=>{
 const trusted=['java-reviewer','java-developer','spring-boot-engineer','react-reviewer','react-developer'];
 assert.equal(recommendSpecialist('Find Java bugs',['java'],trusted).agent,'java-reviewer');
 assert.equal(recommendSpecialist('Implement the Java fix',['java'],trusted).agent,'java-developer');
 assert.equal(recommendSpecialist('Υλοποίησε τη διόρθωση στον κώδικα',['java'],trusted).agent,'java-developer');
 assert.equal(recommendSpecialist('Apply the patch',['react','typescript'],trusted).agent,'react-developer');
 assert.equal(recommendSpecialist('Implement Spring configuration fix',['java','spring'],trusted).agent,'spring-boot-engineer');
 assert.equal(recommendSpecialist('Implement Java fix',['java'],['java-reviewer']),null);
});
