import {sourcePreview} from './sourceInspector';
import type {SourceBlock} from './sourceInspector';

/** A local, uncommitted suggestion against one verified line/range in an approved snapshot. */
export type SuggestionDraft={
  file:string;start:number;end:number;original:string;replacement:string;
  snapshotSha256:string;origin:'manual'|'model-excerpt';
};
const MAX_LINES=80;
const MAX_REPLACEMENT=12000;

/** Never invent missing source: every original line must exist in the approved snapshot. */
export function exactOriginal(sources:SourceBlock[],file:string,start:number,end:number):string|null{
  if(!Number.isSafeInteger(start)||!Number.isSafeInteger(end)||start<1||end<start||
      end-start>=MAX_LINES||!file||!sources.some(s=>s.file===file))return null;
  const lines=sourcePreview(sources,file,start,3000);
  const selected=lines.filter(line=>line.line>=start&&line.line<=end);
  if(selected.length!==end-start+1||selected.some((line,i)=>line.line!==start+i))return null;
  return selected.map(line=>line.text).join('\n');
}
export function startSuggestion(
  sources:SourceBlock[],file:string,start:number,end:number,snapshotSha256:string
):SuggestionDraft|null{
  const original=exactOriginal(sources,file,start,end);
  if(original===null)return null;
  return {file,start,end,original,replacement:original,snapshotSha256,origin:'manual'};
}
export function draftPatch(draft:SuggestionDraft):string|null{
  if(draft.replacement===draft.original||draft.replacement.length>MAX_REPLACEMENT||
     /[\r\n]/.test(draft.file)||draft.file.startsWith('/')||draft.file.includes('..'))return null;
  const removed=draft.original.split('\n');
  const added=draft.replacement.split('\n');
  const safeFile=draft.file;
  return [
    '--- a/'+safeFile,'+++ b/'+safeFile,
    '` -'+draft.start+','+removed.length+' +'+draft.start+','+added.length+' `',
    ...removed.map(line=>'-'+line),...added.map(line=>'+'+line),
  ].join('\n')+'\n';
}
