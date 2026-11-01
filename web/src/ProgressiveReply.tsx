import type {SourceReference} from './sourceInspector';
import {useEffect,useState} from 'react';
import {splitReply,readableProse} from './chatPresentation';

export function ProgressiveReply({text,animate,onProgress,references=[],onReference}:{text:string;animate:boolean;onProgress?:()=>void;references?:SourceReference[];onReference?:(ref:SourceReference)=>void}){
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
 function linked(prose:string){
  const nodes:React.ReactNode[]=[];let remaining=prose,key=0;
  while(remaining){
   const hits=references.filter(r=>r.verified&&r.citationText).map(r=>({r,index:remaining.indexOf(readableProse(r.citationText!))})).filter(h=>h.index>=0).sort((a,b)=>a.index-b.index);
   const hit=hits[0];if(!hit){nodes.push(remaining);break;}
   nodes.push(remaining.slice(0,hit.index));
   nodes.push(<button type="button" className="text-action source-citation" key={key++} onClick={()=>onReference?.(hit.r)}>{readableProse(hit.r.citationText!)}</button>);
   remaining=remaining.slice(hit.index+readableProse(hit.r.citationText!).length);
  }return nodes;
 }
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
    <p className="chat-prose" key={i}>{linked(part.text)}</p>)}
  {visible<text.length&&<div className="reply-progress"><small>Displaying completed provider response…</small><button type="button" className="text-action" onClick={()=>setVisible(text.length)}>Show full reply</button></div>}
 </div>;
}
