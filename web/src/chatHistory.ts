export type Message={id:number;role:'user'|'status'|'assistant';text:string;createdAt?:string};
export type Session={id:number;name:string;renamed?:boolean;messages:Message[]};
export type History={version:1;activeId:number;sessions:Session[]};
export const HISTORY_KEY='daeloryn.chat-history.v1';
function record(v:unknown):v is Record<string,unknown>{return v!==null&&typeof v==='object'&&!Array.isArray(v);}
function id(v:unknown):v is number{return typeof v==='number'&&Number.isSafeInteger(v)&&v>0;}
function validMessageTime(v:unknown):v is string{return typeof v==='string'&&/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/.test(v)&&!Number.isNaN(Date.parse(v))&&new Date(v).toISOString()===v;}
export function formatMessageTime(createdAt?:string,locale='el-GR'):string{
 if(!validMessageTime(createdAt))return 'Date/time unavailable (older message)';
 return new Intl.DateTimeFormat(locale,{year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'}).format(new Date(createdAt));
}
export function parseHistory(raw:string):History{
 if(new TextEncoder().encode(raw).length>2*1024*1024)throw new Error('Local history exceeds 2 MB.');
 const d:unknown=JSON.parse(raw);
 if(!record(d)||d.version!==1||!id(d.activeId)||!Array.isArray(d.sessions)||d.sessions.length<1||d.sessions.length>50)throw new Error('Invalid history.');
 const seen=new Set<number>();
 for(const s of d.sessions){
  if(!record(s)||!id(s.id)||seen.has(s.id)||typeof s.name!=='string'||!s.name.trim()||s.name.length>100||/[\x00-\x1f]/.test(s.name)||(s.renamed!==undefined&&typeof s.renamed!=='boolean')||!Array.isArray(s.messages)||s.messages.length>200)throw new Error('Invalid conversation.');
  seen.add(s.id);
  for(const m of s.messages)if(!record(m)||!id(m.id)||!['user','assistant','status'].includes(m.role as string)||typeof m.text!=='string'||m.text.length>350000||(m.createdAt!==undefined&&(!validMessageTime(m.createdAt))))throw new Error('Invalid message.');
 }
 if(!seen.has(d.activeId))throw new Error('Missing active conversation.');
 return d as History;
}
export function readHistory(storage:Storage):History|null{const raw=storage.getItem(HISTORY_KEY);return raw===null?null:parseHistory(raw);}
export function saveHistory(storage:Storage,sessions:Session[],activeId:number):void{const raw=JSON.stringify({version:1,activeId,sessions});parseHistory(raw);storage.setItem(HISTORY_KEY,raw);}
