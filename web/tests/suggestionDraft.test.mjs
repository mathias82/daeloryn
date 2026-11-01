import {test} from 'node:test';
import assert from 'node:assert/strict';
import {exactOriginal,startSuggestion,draftPatch} from '../.test-build/suggestionDraft.js';
import {extractSourceReferences,manifestSources} from '../.test-build/sourceInspector.js';

const file='src/main/java/example/App.java';
const source='class App {\n  String x;\n  String read(){ return x.toString(); }\n}\n';
const blocks=[{file,line:1,column:1,end_line:4,source}];

test('draft suggestion is grounded in exact approved source lines and has no side effects',()=>{
 const proposal=startSuggestion(blocks,file,3,3,'a'.repeat(64));
 assert.ok(proposal);
 assert.equal(proposal.original,'  String read(){ return x.toString(); }');
 assert.equal(proposal.replacement,proposal.original);
 assert.equal(draftPatch(proposal),null);
 const replacement='  String read(){ return x == null ? "" : x.toString(); }';
 const patch=draftPatch({...proposal,replacement});
 assert.ok(patch);
 assert.match(patch,/--- a\/src\/main\/java\/example\/App.java/);
 assert.match(patch,/\+  String read\(\)\{ return x == null/);
 assert.match(patch,/-  String read\(\)\{ return x.toString\(\); \}/);
});
test('draft cannot be built from missing source or out of snapshot range',()=>{
 assert.equal(exactOriginal(blocks,file,42,42),null);
 assert.equal(exactOriginal(blocks,file,2,5),null);
 assert.equal(startSuggestion(blocks,'another.java',1,1,'a'.repeat(64)),null);
 const p=startSuggestion(blocks,file,1,1,'a'.repeat(64));
 assert.ok(p);
 assert.equal(draftPatch({...p,replacement:'a'.repeat(12001)}),null);
 assert.equal(draftPatch({...p,file:'../outside.java',replacement:'new content'}),null);
});
test('model-proposed code is not a real patch and requires explicit edit approval',()=>{
 const fenced=String.fromCharCode(96).repeat(3);
 const prompt=JSON.stringify(blocks[0]);
 assert.deepEqual(manifestSources(prompt,[file]),blocks);
 const response='Suggested change at '+file+':3:\n'+fenced+'java\nString read(){return x == null ? "" : x.toString();}\n'+fenced;
 const refs=extractSourceReferences(response,1,blocks);
 assert.equal(refs.length,1);
 assert.equal(refs[0].kind,'change');
 assert.equal(refs[0].verified,true);
 assert.match(refs[0].suggestionText||'',/x == null/);
 const unsupported=extractSourceReferences('Fix '+file+':34\n'+fenced+'java\nbad\n'+fenced,1,blocks);
 assert.equal(unsupported[0].verified,false);
 assert.equal(unsupported[0].suggestionText,undefined);
});
test('escaped source path strings do not become arbitrary regex matches',()=>{
 const refs=extractSourceReferences('Fix '+file+':3',1,blocks);
 assert.equal(refs[0].file,file);
 assert.equal(refs[0].line,3);
});
