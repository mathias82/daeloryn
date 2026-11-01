import assert from 'node:assert/strict';
import test from 'node:test';
import {HISTORY_KEY,parseHistory,readHistory,saveHistory,formatMessageTime} from '../.test-build/chatHistory.js';
const sessions=[{id:1,name:'My Java review',renamed:true,messages:[{id:2,role:'user',text:'Review Java'},{id:3,role:'assistant',text:'First line\nSecond line'}]}];
function memory(){const values=new Map();return{getItem:k=>values.get(k)??null,setItem:(k,v)=>values.set(k,v),removeItem:k=>values.delete(k)};}
test('names, active selection and multiline messages survive storage round trip',()=>{const storage=memory();saveHistory(storage,sessions,1);assert.deepEqual(readHistory(storage),{version:1,activeId:1,sessions});storage.removeItem(HISTORY_KEY);assert.equal(readHistory(storage),null);});
test('invalid structure, duplicate IDs, unknown active session and oversized input fail',()=>{for(const raw of ['bad',JSON.stringify({version:2,activeId:1,sessions}),JSON.stringify({version:1,activeId:2,sessions}),JSON.stringify({version:1,activeId:1,sessions:[...sessions,...sessions]}),' '.repeat(2*1024*1024+1)])assert.throws(()=>parseHistory(raw));});
test('storage failures surface rather than claiming successful persistence',()=>{assert.throws(()=>saveHistory({setItem(){throw new Error('quota');}},sessions,1),/quota/);assert.throws(()=>readHistory({getItem(){throw new Error('disabled');}}),/disabled/);});


test('new message timestamp persists and displays local date and time',()=>{
 const timestamp='2026-11-01T17:30:05.000Z';
 const updated=structuredClone(sessions);
 updated[0].messages[0].createdAt=timestamp;
 const storage=memory();
 saveHistory(storage,updated,1);
 assert.equal(readHistory(storage).sessions[0].messages[0].createdAt,timestamp);
 assert.match(formatMessageTime(timestamp,'el-GR'),/2026/);
 assert.notEqual(formatMessageTime(timestamp,'el-GR'),formatMessageTime(undefined,'el-GR'));
});
test('older messages remain valid without fabricated timestamps; malformed times are rejected',()=>{
 assert.match(formatMessageTime(undefined),/unavailable/);
 const broken=structuredClone(sessions);
 broken[0].messages[0].createdAt='yesterday';
 assert.throws(()=>parseHistory(JSON.stringify({version:1,activeId:1,sessions:broken})));
});
