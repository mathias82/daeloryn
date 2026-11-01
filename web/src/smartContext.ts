/**
 * Conservative, zero-provider-call routing for local project chat.
 * This is an intent hint, NOT permission to send files. Source is always
 * separately previewed and approved by the user before Copilot receives it.
 */
export type ContextScope='none'|'focused'|'full';
export type ContextPreference='smart'|'text-only'|'full';

const WHOLE=/(?:\b(?:full|complete|entire|whole|all)\b.{0,40}\b(?:project|repo(?:sitory)?|codebase|source|files|review|scan|audit)\b|\b(?:review|scan|audit|analy[sz]e|inspect)\b.{0,40}\b(?:entire|whole|full|all)\b|\b(?:every|all)\s+(?:source|java|code|repository)\s+files?\b|ολ[όο]κληρ\w*|πλ[ήη]ρ\w*\s+(?:αν[άα]λυσ\w*|[έε]λεγχ\w*)|[όο]λα\s+τα\s+αρχε[ίι]α|[όο]λο\s+το\s+(?:project|έργο|repository)|σ[άα]ρωσε\s+τα\s+π[άα]ντα)/iu;

const PROJECT=/(?:\b(?:project|repository|repo|codebase|source\s+code|source\s+files?|my\s+code|our\s+code|service|controller|endpoint|spring\s+boot|architecture|observability|logging|metrics|trace|telemetry|kafka|docker|kubernetes|pom\.xml|build\.gradle|application\.ya?ml|class|module|package)\b|(?:[οό]?\s*(?:κ[ώω]δικ\w*|έργ\w*|αρχιτεκτονικ\w*|αρχε[ίι]\w*|κλ[άα]σ\w*|μ[έε]τρικ\w*|παρατηρησιμ\w*|καταγραφ\w*|ιχνηλ[άα]τ\w*|εφαρμογ\w*|π[ώω]ς\s+υλοποι\w*)))/iu;

const CURIOSITY=/(?:\b(?:what|how\s+(?:does|is)|where\s+(?:is|are)|explain|find|show|inspect|review|check|analy[sz]e|what\s+does)\b|π[ώω]ς|πο[ύυ]|εξ[ήη]γησ\w*|δείξε|δες|[έε]λεγξ\w*|αν[άα]λυσ\w*|τι\s+κ[άα]νει)/iu;

const SMALL_TALK=/^(?:hi|hello|hey|good\s+(?:morning|evening)|thanks?|thank\s+you|ok(?:ay)?|yes|no|γει[άα](?:\s+σου)?|καλημ[έε]ρα|καλησπ[έε]ρα|ευχαριστ[ώω]|ναι|[όο]χι|[έε]γινε|τι\s+κ[άα]νεις)[!?.\s]*$/iu;

/**
 * Ambiguity resolves to no repository access. Explicit "full" is accepted
 * only for a repository-related task; a focused task needs a project signal.
 */
export function routeContext(task:string, preference:ContextPreference='smart'):ContextScope {
  if(preference==='text-only')return 'none';
  if(preference==='full')return 'full';
  const query=task.trim().slice(0,3000);
  if(!query||SMALL_TALK.test(query))return 'none';
  if(WHOLE.test(query)&&PROJECT.test(query))return 'full';
  if(PROJECT.test(query)&&CURIOSITY.test(query))return 'focused';
  return 'none';
}
