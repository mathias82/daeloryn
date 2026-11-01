/** Link only uniquely identified filenames from the approved context.
 * Never turn arbitrary model output into an external URL or local file path.
 */
export type SourceRange={line:number;endLine:number};
export type SourceLink={file:string;ranges:SourceRange[]};
export type LinkedSegment={text:string;reference?:SourceLink;range?:SourceRange};
const FILE_PATTERN=/(?:[\w.$-]+\/)*[\w.$-]+\.(?:java|kt|ts|tsx|js|jsx|py|go|xml|yaml|yml|properties|md)\b/g;
const LINE_CLAIM=/\b(?:lines?|around lines?)\s+(\d{1,6})(?:\s*[-–]\s*(\d{1,6}))?/gi;
const OTHER_RANGE=/(?:\s*(?:,|and|or|\(imports?\)))+\s*(\d{1,6})(?:\s*[-–]\s*(\d{1,6}))?/gi;

function resolvedFilename(name:string,files:string[]):string|null{
 const exact=files.filter(file=>file===name);
 if(exact.length===1)return exact[0];
 const candidates=files.filter(file=>file.split('/').at(-1)===name);
 return candidates.length===1?candidates[0]:null;
}
function uniqueRanges(ranges:SourceRange[]):SourceRange[]{
 return ranges.filter((r,i)=>r.line>0&&r.endLine>=r.line&&r.endLine-r.line<=100&&
   ranges.findIndex(x=>x.line===r.line&&x.endLine===r.endLine)===i).slice(0,15);
}
type Token={start:number;end:number;reference:SourceLink;range?:SourceRange};
export function sourceLinkSegments(text:string,files:string[]):LinkedSegment[]{
 if(!text||!files.length)return [{text}];
 const occurrences=[...text.matchAll(FILE_PATTERN)].map(m=>({
  start:m.index,end:m.index+m[0].length,file:resolvedFilename(m[0],files)
 }));
 const tokens:Token[]=[];
 for(let i=0;i<occurrences.length;i++){
  const current=occurrences[i];
  if(!current.file)continue;
  const next=occurrences[i+1]?.start??text.length;
  const paragraph=text.indexOf('\n\n',current.end);
  const limit=Math.min(next,paragraph<0?text.length:paragraph,current.end+205);
  const tail=text.slice(current.end,limit);
  const spans:{start:number;end:number;range:SourceRange}[]=[];
  LINE_CLAIM.lastIndex=0;
  let claim:RegExpExecArray|null;
  while((claim=LINE_CLAIM.exec(tail))!==null){
   const first={line:Number(claim[1]),endLine:Number(claim[2]||claim[1])};
   spans.push({start:current.end+claim.index,end:current.end+claim.index+claim[0].length,range:first});
   // Further ranges separated by commas/"and" are part of the same claim.
   const rest=tail.slice(claim.index+claim[0].length);
   OTHER_RANGE.lastIndex=0;
   let continued:RegExpExecArray|null;
   let consumed=0;
   while((continued=OTHER_RANGE.exec(rest))!==null &&
       continued.index===consumed && spans.length<16){
    const start=current.end+claim.index+claim[0].length+continued.index;
    const range={line:Number(continued[1]),endLine:Number(continued[2]||continued[1])};
    spans.push({start,end:start+continued[0].length,range});
    consumed=continued.index+continued[0].length;
   }
   LINE_CLAIM.lastIndex=claim.index+claim[0].length+consumed;
  }
  const ranges=uniqueRanges(spans.map(x=>x.range));
  const reference={file:current.file,ranges};
  tokens.push({start:current.start,end:current.end,reference});
  for(const item of spans){
   if(ranges.some(r=>r.line===item.range.line&&r.endLine===item.range.endLine))
    tokens.push({start:item.start,end:item.end,reference,range:item.range});
  }
 }
 tokens.sort((a,b)=>a.start-b.start||b.end-a.end);
 const parts:LinkedSegment[]=[];
 let cursor=0;
 for(const token of tokens){
  if(token.start<cursor)continue;
  if(token.start>cursor)parts.push({text:text.slice(cursor,token.start)});
  parts.push({text:text.slice(token.start,token.end),reference:token.reference,range:token.range});
  cursor=token.end;
 }
 if(cursor<text.length)parts.push({text:text.slice(cursor)});
 return parts.length?parts:[{text}];
}
