import {useEffect,useState} from 'react';
import {splitReply} from './chatPresentation';
import {sourceLinkSegments} from './sourceLinks';
import type {SourceLink} from './sourceLinks';

export function ProgressiveReply({text,animate,onProgress,approvedFiles,onSourceSelect}:{
 text:string;animate:boolean;onProgress?:()=>void;
 approvedFiles?:string[];onSourceSelect?:(reference:SourceLink,focus?:{line:number;endLine:number})=>void;
}){
 const [visible,setVisible]=useState(animate?0:text.length);
 const [copied,setCopied]=useState<number|null>(null);
 useEffect(()=>{
  if(!animate||window.matchMedia('(prefers-reduced-motion: reduce)').matches){setVisible(text.length);return;}
  setVisible(0);
  const step=Math.max(120,Math.ceil(text.length/80));
  const timer=window.setInterval(()=>setVisible(current=>{
   const newline=text.indexOf('\n',current);
   const next=newline>=current&&newline-current<step*2?newline+1:current+step;
   if(next>=text.length)window.clearInterval(timer);
   return Math.min(next,text.length);
  }),30);
  return()=>window.clearInterval(timer);
 },[text,animate]);
 useEffect(()=>{if(animate)onProgress?.();},[visible,animate,onProgress]);
 const parts=splitReply(text.slice(0,visible));
 return <div className="conversational-reply">
  {parts.map((part,i)=>part.kind==='code'?
    <section className="chat-code-block" key={i} aria-label="Code snippet">
      <div className="chat-code-bar">
        <span>{part.language||'code'}</span>
        <button type="button" disabled={!part.closed} onClick={()=>{
          if(navigator.clipboard?.writeText)
            void navigator.clipboard.writeText(part.text).then(()=>setCopied(i)).catch(()=>setCopied(null));
        }}>{copied===i?'Copied':'Copy code'}</button>
      </div>
      <pre><code>{part.text}</code></pre>
    </section>:
    <p className="chat-prose" key={i}>
      {approvedFiles?.length&&onSourceSelect?
        sourceLinkSegments(part.text,approvedFiles).map((segment,k)=>segment.reference?
          <button type="button" className="chat-source-link" key={k}
            aria-label={'Open '+segment.reference.file+
              (segment.range?' lines '+segment.range.line+'–'+segment.range.endLine:
               segment.reference.ranges.length?' cited lines':' entire file')+' in Code Inspector'}
            title={'View '+segment.reference.file+' locally in Code Inspector (no provider call)'}
            onClick={()=>onSourceSelect(segment.reference,segment.range)}>
            {segment.text}</button>:
          <span key={k}>{segment.text}</span>)
        :part.text}
    </p>)}
  {visible<text.length&&<div className="reply-progress"><small>Displaying completed provider response…</small><button type="button" className="text-action" onClick={()=>setVisible(text.length)}>Show full reply</button></div>}
 </div>;
}
