export type ChatMessage = {role:'user'|'assistant';content:string};
export type ReviewSelection = {repository:string;task:string;model:string;agent?:string;scope?:'focused'|'full'|'docs'};

// The preview recommendation does not silently activate a specialist.
export function selectedAgent(agent:string):string|undefined {
  return agent==='Automatic (preview)'?undefined:agent;
}

export function chatRequest(model:string,messages:ChatMessage[],agent?:string) {
  return {model,messages,...(agent?{agent}:{})};
}

export function reviewRequest(selection:ReviewSelection,approvedDigest?:string) {
  if (!selection.model)
    throw new Error('Choose a Copilot model before preparing source review.');
  return {...selection,...(approvedDigest?{approved_sha256:approvedDigest}:{})};
}

export function reviewSelectionKey(selection:ReviewSelection):string {
  return JSON.stringify(selection);
}


// /api/copilot/chat rejects HTTP bodies larger than 24,576 bytes. Provider
// validation also limits each chat message to 3,000 characters. Previous full
// reviews can be much larger than that; never replay their transcripts through
// an ordinary text-only follow-up. Keep complete local chat history untouched.
const MAX_CHAT_WIRE_BYTES=20_000;
const MAX_CHAT_MESSAGE_CHARS=3_000;
const MAX_CHAT_HISTORY_MESSAGES=10;
const textBytes=(value:string)=>new TextEncoder().encode(value).byteLength;

export function boundedChatRequest(model:string,previous:ChatMessage[],latest:string,agent?:string) {
  if(!latest.trim()||latest.length>MAX_CHAT_MESSAGE_CHARS)
    throw new Error('Message must contain 1–3000 characters. Use approved project context for large source files.');
  const last={role:'user' as const,content:latest};
  const window=previous.slice(-MAX_CHAT_HISTORY_MESSAGES);
  const included:ChatMessage[]=[];
  let omitted=previous.length-window.length;
  // Prioritize recent context. Reject oversized past messages *entirely*; do
  // not create misleading partial quotations or copy source review batches.
  for(let i=window.length-1;i>=0;i--){
    const item=window[i];
    if(!['user','assistant'].includes(item.role)||!item.content.trim()||
       item.content.length>MAX_CHAT_MESSAGE_CHARS){omitted++;continue;}
    const candidate=chatRequest(model,[item,...included,last],agent);
    if(textBytes(JSON.stringify(candidate))>MAX_CHAT_WIRE_BYTES){omitted++;continue;}
    included.unshift(item);
  }
  const request=chatRequest(model,[...included,last],agent);
  const bytes=textBytes(JSON.stringify(request));
  if(bytes>MAX_CHAT_WIRE_BYTES)throw new Error('Message exceeds the safe Copilot request limit.');
  return {request,omitted,included:included.length,requestBytes:bytes};
}
