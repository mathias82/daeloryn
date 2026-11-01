/** Safely render model output as conversational prose and isolated code blocks.
 * Never execute Markdown, HTML or scripts from untrusted model replies.
 */
export type ReplyPart={kind:'prose'|'code';text:string;language?:string;closed?:boolean};
export function readableProse(raw:string):string{
  return raw
    .replace(/^\s{0,3}#{1,6}\s+/gm,'')
    .replace(/(?<!\w)\*\*([^*\n]+)\*\*(?!\w)/g,'$1')
    .replace(/(?<!\w)__([^_\n]+)__(?!\w)/g,'$1')
    .replace(/(?<!\w)\*([^*\n]+)\*(?!\w)/g,'$1')
    .replace(/(?<!\w)_([^_\n]+)_(?!\w)/g,'$1')
    .replace(/`([^`\n]+)`/g,'$1')
    .replace(/\[([^\]\n]+)\]\((https?:\/\/[^)\s]+)\)/g,'$1 ($2)')
    .replace(/^\s*[-*]\s+/gm,'• ')
    .replace(/^\s*>\s?/gm,'')
    .replace(/^\s*(?:-{3,}|\*{3,}|_{3,})\s*$/gm,'')
    .trim();
}
/** Partially streamed unfinished fenced blocks stay code, not prose. */
export function splitReply(raw:string):ReplyPart[]{
  const parts:ReplyPart[]=[];
  const lines=raw.replace(/\r\n/g,'\n').split('\n');
  let state:'prose'|'code'='prose';
  let language='';
  let buffer:string[]=[];
  const flush=(closed=true)=>{
    const text=buffer.join('\n').trimEnd();
    if(text.trim())parts.push(state==='prose'?
      {kind:'prose',text:readableProse(text)}:
      {kind:'code',text,language,closed});
    buffer=[];
  };
  for(const line of lines){
    const fence=line.match(/^\s{0,3}`{3,}\s*([a-zA-Z0-9+._#-]*)\s*$/);
    if(fence){
      if(state==='prose'){flush();state='code';language=fence[1]||'code';}
      else{flush(true);state='prose';language='';}
    }else buffer.push(line);
  }
  flush(state==='prose');
  return parts;
}
