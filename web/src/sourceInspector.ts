/** Only references to lines found in the approved source manifest are navigable. */
export type SourceBlock={file:string;line:number;column:number;end_line:number;source:string};
export type SourceReference={file:string;line:number;endLine:number;batch:number;excerpt:string;verified:boolean;kind:'bug'|'change'|'reference';suggestionText?:string;citationText?:string;contextText?:string};
export type InspectorSnapshot={repository:string;sha256:string;model?:string;sources:SourceBlock[];references:SourceReference[];completed:number;total:number;status:string};
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
  const escape=(value:string)=>value.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
  const aliasesFor=(path:string)=>{
    const parts=path.split('/');
    const suffixes=parts.map((_,i)=>parts.slice(i).join('/'));
    const stem=parts[parts.length-1].replace(/\.(?:java|kt|tsx?|jsx?)$/,'');
    return [...new Set([...suffixes,...suffixes.filter(v=>v.includes('/')).flatMap(v=>['…/'+v,'.../'+v]),
      ...(/^[A-Z][A-Za-z0-9_$]*$/.test(stem)?[stem]:[])])];
  };
  const allAliases=paths.map(path=>({path,aliases:aliasesFor(path)}));
  function append(path:string,at:number,citationText:string,line:number,endLine:number,contextText?:string){
    if(found.length>=max||found.some(r=>r.file===path&&r.line===line&&r.endLine===endLine))return;
    const present=endLine>=line&&endLine-line<=80&&Array.from({length:endLine-line+1},(_,i)=>line+i).every(n=>sources.some(s=>s.file===path&&n>=s.line&&n<=s.end_line));
    const paragraphStart=reply.lastIndexOf('\n\n',at);
    const paragraphEnd=reply.indexOf('\n\n',at);
    const start=Math.max(paragraphStart<0?0:paragraphStart+2,at-1000);
    const end=Math.min(paragraphEnd<0?reply.length:paragraphEnd,at+1500);
    const excerpt=reply.slice(start,end).replace(/\s+/g,' ');
    const kind=/(?:bug|defect|vulnerab|exception|unsafe|leak|race|NPE|null dereference|error|σφάλμ)/iu.test(excerpt)?'bug':
      /(?:fix|change|modify|replace|refactor|update|should|must|διορθ|αλλαγ)/iu.test(excerpt)?'change':'reference';
    let suggestionText:string|undefined;
    if(present&&/(?:fix|replace|change|suggest|proposed|refactor|patch|διορθ|αλλαγ)/iu.test(excerpt)){
      const fence=reply.indexOf(String.fromCharCode(96).repeat(3),at+citationText.length);
      if(fence>=0&&fence-(at+citationText.length)<500){
        const firstLine=reply.indexOf('\n',fence);
        const close=firstLine>=0?reply.indexOf(String.fromCharCode(96).repeat(3),firstLine+1):-1;
        if(firstLine>=0&&firstLine-fence<45&&close>firstLine&&close-firstLine<=8000){
          const candidate=reply.slice(firstLine+1,close).trimEnd();
          if(candidate)suggestionText=candidate;
        }
      }
    }
    found.push({file:path,line,endLine,batch,verified:present,kind,excerpt,suggestionText,citationText,contextText});
  }
  for(const {path,aliases} of allAliases){
    const unique=aliases.filter(alias=>allAliases.filter(entry=>entry.aliases.includes(alias)).length===1);
    const escaped=unique.sort((a,b)=>b.length-a.length).map(escape).join('|');
    const expression=new RegExp('(?<![\\p{L}\\p{N}_$./-])(?:'+escaped+')[`*]*(?:[:#]L?|[,，]?\\s+(?:[Ll]ines?|γραμμ(?:ή|ές|η|ες))\\s+)(\\d{1,6})(?:\\s*[-–—]\\s*(\\d{1,6}))?','gu');
    let match:RegExpExecArray|null;
    while((match=expression.exec(reply))!==null&&found.length<max){
      append(path,match.index,match[0],Number(match[1]),Number(match[2]||match[1]));
    }
  }
  // Natural-language reviews often name a type once, then cite several ranges
  // in the same paragraph. Resolve only one unambiguous approved file; never
  // carry the context into another paragraph or infer a path from an exception.
  for(const paragraph of reply.matchAll(/[^\n]+(?:\n(?!\n)[^\n]+)*/g)){
    const text=paragraph[0];
    const mentioned=allAliases.filter(entry=>entry.aliases.some(alias=>
      new RegExp('(?<![\\p{L}\\p{N}_$./-])'+escape(alias)+'(?![\\p{L}\\p{N}_$/-]|\\.[\\p{L}\\p{N}_$])','u').test(text)));
    if(mentioned.length!==1)continue;
    const path=mentioned[0].path;
    const explicitFiles=[...text.matchAll(/[\w./-]+\.(?:java|kt|tsx?|jsx?)(?![\w])/g)];
    if(explicitFiles.some(token=>!allAliases.some(entry=>entry.aliases.includes(token[0]))))continue;
    for(const citation of text.matchAll(/(?:[Ll]ines?|γραμμ(?:ή|ές|η|ες))\s+(\d{1,6})(?:\s*[-–—]\s*(\d{1,6}))?/gu)){
      append(path,paragraph.index!+citation.index!,citation[0],Number(citation[1]),Number(citation[2]||citation[1]),text);
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
