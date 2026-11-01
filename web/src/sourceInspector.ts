/** Only references to lines found in the approved source manifest are navigable. */
export type SourceBlock={file:string;line:number;column:number;end_line:number;source:string};
export type SourceReference={file:string;line:number;endLine:number;batch:number;excerpt:string;verified:boolean;kind:'bug'|'change'|'reference'};
export type InspectorSnapshot={repository:string;sha256:string;sources:SourceBlock[];references:SourceReference[];completed:number;total:number;status:string};
export function manifestSources(prompt:string,files:string[]):SourceBlock[]{
  const allow=new Set(files);
  const out:SourceBlock[]=[];
  for(const line of prompt.split('\n')){
    if(!line.startsWith('{"file":'))continue;
    try{
      const v:unknown=JSON.parse(line);
      if(!v||typeof v!=='object')continue;
      const b=v as Partial<SourceBlock>;
      if(typeof b.file!=='string'||!allow.has(b.file)||typeof b.source!=='string'||
          !Number.isSafeInteger(b.line)||!Number.isSafeInteger(b.end_line)||
          !Number.isSafeInteger(b.column)||b.line!<1||b.end_line!<b.line!||b.column!<1)continue;
      out.push(b as SourceBlock);
    }catch{/* malformed metadata cannot create trusted navigable references */}
  }
  return out;
}
export function extractSourceReferences(reply:string,batch:number,sources:SourceBlock[],max=60):SourceReference[]{
  const found:SourceReference[]=[];
  const paths=[...new Set(sources.map(s=>s.file))].sort((a,b)=>b.length-a.length);
  for(const path of paths){
    const escaped=path.replace(/[.*+?^$()|[\]\\{}]/g,'\\$&');
    const expression=new RegExp(escaped+'(?:[:#]L?|\\s+[Ll]ines?\\s+)(\\d{1,6})(?:\\s*[-–]\\s*(\\d{1,6}))?','g');
    let match:RegExpExecArray|null;
    while((match=expression.exec(reply))!==null&&found.length<max){
      const line=Number(match[1]);
      const endLine=match[2]?Number(match[2]):line;
      const present=endLine>=line&&endLine-line<=80&&sources.some(s=>s.file===path&&line>=s.line&&endLine<=s.end_line);
      const excerpt=reply.slice(Math.max(0,match.index-120),Math.min(reply.length,match.index+170)).replace(/\s+/g,' ');
      const kind=/\b(?:bug|defect|vulnerab|exception|unsafe|leak|race|NPE|null dereference|error|σφάλμ)\w*/i.test(excerpt)?'bug':
        /\b(?:fix|change|modify|replace|refactor|update|should|must|διορθ|αλλαγ)\w*/i.test(excerpt)?'change':'reference';
      found.push({file:path,line,endLine,batch,verified:present,kind,excerpt});
    }
  }
  return found.sort((a,b)=>a.batch-b.batch||a.file.localeCompare(b.file)||a.line-b.line);
}
export function sourcePreview(sources:SourceBlock[],file:string,target:number,windowSize=42){
  const blocks=sources.filter(s=>s.file===file).sort((a,b)=>a.line-b.line||a.column-b.column);
  const list:{line:number;text:string}[]=[];
  for(const block of blocks){
    const pieces=block.source.split('\n');
    for(let i=0;i<pieces.length;i++){
      if(i===pieces.length-1&&pieces[i]==='')continue;
      const n=block.line+i;
      const previous=list[list.length-1];
      if(previous?.line===n)previous.text+=pieces[i];
      else list.push({line:n,text:pieces[i]});
    }
  }
  const index=list.findIndex(l=>l.line>=target);
  const start=Math.max(0,(index<0?0:index)-Math.min(12,Math.floor(windowSize/3)));
  return list.slice(start,start+windowSize);
}


/** Method/class context is a lexical hint only, never verified semantic parsing. */
export function nearbyDeclaration(sources:SourceBlock[],file:string,target:number):string|null {
  const before=sourcePreview(sources,file,Math.max(1,target-12)).filter(l=>l.line<=target);
  for(let i=before.length-1;i>=0;i--){
    const line=before[i].text.trim();
    const klass=line.match(/\b(?:class|interface|enum|record)\s+([A-Za-z_$][\w$]*)/);
    const method=line.match(/\b([A-Za-z_$][\w$]*)\s*\([^;{}]*\)\s*(?:throws\b[^{}]*)?\{?\s*$/);
    if(method&&!/^(if|while|for|switch|catch|return|new|try|synchronized)$/.test(method[1]))return method[1]+'(…) · approximate declaration';
    if(klass)return klass[1]+' · approximate type declaration';
  }
  return null;
}
