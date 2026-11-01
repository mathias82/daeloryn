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

test('Greek basename citations resolve only uniquely approved files and exact ranges',()=>{
 const refs=extractSourceReferences('Στο App.java, γραμμές 2–3, προτείνω αλλαγή.',1,blocks);
 assert.equal(refs.length,1);assert.equal(refs[0].file,file);assert.equal(refs[0].line,2);assert.equal(refs[0].endLine,3);assert.equal(refs[0].verified,true);
 assert.equal(extractSourceReferences('App.java, γραμμή 2',1,[...blocks,{...blocks[0],file:'other/App.java'}]).length,0);
 assert.equal(extractSourceReferences('evil/App.java, γραμμή 2',1,blocks).length,0);
 assert.equal(extractSourceReferences('App.java, γραμμές 2–999',1,blocks)[0].verified,false);
});


test('abbreviated unique paths and contiguous blocks resolve all cited lines',()=>{
 const src=[{file:'src/demo/config/App.java',line:1,column:1,end_line:2,source:'one\ntwo\n'},{file:'src/demo/config/App.java',line:3,column:1,end_line:4,source:'three\nfour\n'}];
 const refs=extractSourceReferences('…/demo/config/App.java, γραμμές 2–4',1,src);
 assert.equal(refs.length,1);assert.equal(refs[0].verified,true);assert.equal(refs[0].file,src[0].file);
 const missing=[src[0],{...src[1],line:4}];
 assert.equal(extractSourceReferences('…/demo/config/App.java, γραμμές 2–4',1,missing)[0].verified,false);
});


test('natural Greek class paragraphs resolve multiple source ranges without file extensions',()=>{
 const file='src/advice/ControllerAdvisor.java';
 const sources=[{file,line:37,column:1,end_line:45,source:'approved generic handler'},
   {file,line:96,column:1,end_line:104,source:'approved specific handler'}];
 const reply='Η κλάση που χρειάζεται προσοχή είναι η ControllerAdvisor. Στις γραμμές 37–45 επιστρέφει το e.getMessage(). Η διόρθωση είναι ένα σταθερό μήνυμα προς τον client. Το ίδιο ισχύει για NoResultException (γραμμές 96–104).';
 const refs=extractSourceReferences(reply,1,sources);
 assert.equal(refs.length,2);assert.ok(refs.every(r=>r.verified&&r.file===file));
 assert.deepEqual(refs.map(r=>r.line),[37,96]);
 assert.ok(refs.every(r=>r.excerpt.includes('σταθερό μήνυμα')));
 assert.equal(refs[0].contextText,reply);
 assert.equal(extractSourceReferences('ControllerAdvisor, lines 37–45',1,sources)[0].verified,true);
 assert.equal(extractSourceReferences('ControllerAdvisor (γραμμές 37–45)',1,sources)[0].verified,true);
});

test('natural citations refuse ambiguous, unknown, cross-paragraph and unavailable source',()=>{
 const src={file:'src/ControllerAdvisor.java',line:37,column:1,end_line:45,source:'approved'};
 const reply='ControllerAdvisor. Στις γραμμές 37–45 προτείνω αλλαγή.';
 assert.equal(extractSourceReferences(reply,1,[src,{...src,file:'other/ControllerAdvisor.java'}]).length,0);
 assert.equal(extractSourceReferences('OtherControllerAdvisor. Στις γραμμές 37–45.',1,[src]).length,0);
 assert.equal(extractSourceReferences('ControllerAdvisor.\n\nΣτις γραμμές 37–45.',1,[src]).length,0);
 assert.equal(extractSourceReferences('ControllerAdvisor και Missing.java. Στις γραμμές 37–45.',1,[src]).length,0);
 assert.equal(extractSourceReferences('ControllerAdvisor και App. Στις γραμμές 37–45.',1,[src,{...src,file:'src/App.java'}]).length,0);
 assert.equal(extractSourceReferences('ControllerAdvisor. Στις γραμμές 37–46.',1,[src])[0].verified,false);
 assert.equal(extractSourceReferences('ControllerAdvisor. Στις γραμμές 37–999999.',1,[src])[0].verified,false);
 assert.equal(extractSourceReferences('ControllerAdvisor. Στις γραμμές 37–45.',1,[src],0).length,0);
});
