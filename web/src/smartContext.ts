/**
 * Context-routing hints run without a provider call. The browser never grants
 * source access: the server still requires exact snapshot/digest approval.
 */
export type ContextScope='none'|'docs'|'focused'|'full';
export type ContextPreference='smart'|'docs'|'text-only';

const SMALL_TALK=/^(?:hi|hello|hey|good\s+(?:morning|evening)|thanks?|thank\s+you|ok(?:ay)?|yes|no|γει[άα](?:\s+σου)?|καλημ[έε]ρα|καλησπ[έε]ρα|ευχαριστ[ώω]|ναι|[όο]χι|[έε]γινε|τι\s+κ[άα]νεις)[!?.\s]*$/iu;
const FULL=/(?:\b(?:full|complete|entire|whole|all)\b.{0,55}\b(?:project|repository|repo|codebase|source\s+files?|java\s+files?|files)\b|\b(?:review|scan|inspect|audit|analy[sz]e)\b.{0,55}\b(?:entire|whole|full|all)\b.{0,30}\b(?:project|repo|source|files)\b|\b(?:inspect|review)\s+all\s+source\s+files?\b|[όο]λο\s+το\s+(?:project|έργο|repository)|[όο]λα\s+τα\s+αρχε[ίι]α|σ[άα]ρωσε\s+τα\s+π[άα]ντα|ολ[όο]κληρ[\p{L}]*\s+το\s+(?:project|έργο)|πλ[ήη]ρ[\p{L}]*\s+(?:[έε]λεγχο|αν[άα]λυση)\s+.{0,30}(?:έργου|project))/iu;
const EXPLICIT_PROJECT=/(?:\b(?:project|repository|repo|codebase|source\s+code|source\s+files?|my\s+code|our\s+code|service|controller|endpoint|pom(?:\.xml)?|build\.gradle(?:\.kts)?|gradle\.properties|application\.ya?ml|class|module|package)\b|κ[ώω]δικ[\p{L}]*|έργ[\p{L}]*|εφαρμογ[\p{L}]*|κλ[άα]σ[\p{L}]*|αρχε[ίι][\p{L}]*)/iu;
const CODE_INTENT=/(?:\b(?:review|scan|inspect|audit|analy[sz]e|check|find|fix|show|where|how\s+does|what\s+does)\b.{0,65}\b(?:bugs?|defects?|code|class|method|function|spring|controller|endpoint|security|vulnerabilit(?:y|ies)|observability|tracing|logging|architecture|implementation)\b|\b(?:bugs?|code\s+review|security\s+audit)\b|βρ[εέ]σ[\p{L}]*.{0,45}(?:bug|σφ[άα]λμα|κ[ώω]δικ)|κ[άα]νε.{0,45}(?:[έε]λεγχο|αναλ[υύ]ση)|[έε]λεγξ[\p{L}]*)/iu;
const PROJECT_QUESTION=/(?:\b(?:how|what|where|explain|show|review|check|inspect|analy[sz]e|find|does)\b|π[ώω]ς|πο[ύυ]|πο[ιί][εέ]ς|πο[ιί]α|δε[ίι]ξε|δ(?:ες|εις)|δι[άα]βασ[\p{L}]*|χρησιμοπο[ιί][\p{L}]*|τι\s+κ[άα]νει|αν[άα]λυσ[\p{L}]*)/iu;
const BUILD_FILE=/\b(?:pom(?:\.xml)?|build\.gradle(?:\.kts)?|gradle\.properties|settings\.gradle(?:\.kts)?)\b/iu;
const BUILD_ACTION=/\b(?:check|review|inspect|analy[sz]e|find|deprecated|dependencies|dependency|bugs?|versions?|plugins?|upgrade|outdated)\b/iu;
const GENERIC_HOWTO=/^(?:how\s+(?:do|can|should)\s+(?:i|we)|how\s+to|what\s+is|explain\s+how\s+to|πώς\s+μπορώ\s+να|πώς\s+να)\b/iu;

/** Only explicit whole-project language produces full source coverage. */
export function routeContext(task:string,preference:ContextPreference='smart'):ContextScope{
  if(preference==='text-only')return 'none';
  const query=task.trim().slice(0,3000);
  if(!query||SMALL_TALK.test(query))return 'none';
  if(preference==='docs')return 'docs';
  if(FULL.test(query))return 'full';
  if(BUILD_FILE.test(query)&&BUILD_ACTION.test(query))return 'focused';
  if(GENERIC_HOWTO.test(query)&&!EXPLICIT_PROJECT.test(query))return 'none';
  if(EXPLICIT_PROJECT.test(query)&&PROJECT_QUESTION.test(query))return 'focused';
  if(CODE_INTENT.test(query))return 'focused';
  return 'none';
}
