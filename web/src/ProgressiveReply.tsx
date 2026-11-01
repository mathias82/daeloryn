import {useEffect,useState} from 'react';
export function ProgressiveReply({text,animate,onProgress}:{text:string;animate:boolean;onProgress?:()=>void}){
 const [visible,setVisible]=useState(animate?0:text.length);
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
 return <><p>{text.slice(0,visible)}</p>{visible<text.length&&<div className="reply-progress"><small>Displaying completed provider response…</small><button type="button" className="text-action" onClick={()=>setVisible(text.length)}>Show full reply</button></div>}</>;
}
