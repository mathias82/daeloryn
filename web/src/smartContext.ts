/**
 * Conservative, zero-provider-call routing for local project chat.
 * This is an intent hint, NOT permission to send files. Source is always
 * separately previewed and approved by the user before Copilot receives it.
 */
export type ContextScope='none'|'focused'|'full';
export type ContextPreference='smart'|'text-only'|'full';

const WHOLE=/(?:\b(?:full|complete|entire|whole|all)\b.{0,40}\b(?:project|repo(?:sitory)?|codebase|source|files|review|scan|audit)\b|\b(?:review|scan|audit|analy[sz]e|inspect)\b.{0,40}\b(?:entire|whole|full|all)\b|\b(?:every|all)\s+(?:source|java|code|repository)\s+files?\b|ολ[όο]κληρ[\p{L}]*|πλ[ήη]ρ[\p{L}]*\s+(?:αν[άα]λυσ[\p{L}]*|[έε]λεγχ[\p{L}]*)|[όο]λα\s+τα\s+αρχε[ίι]α|[όο]λο\s+το\s+(?:project|έργο|repository)|σ[άα]ρωσε\s+τα\s+π[άα]ντα)/iu;

const PROJECT=/(?:\b(?:project|repository|repo|codebase|source\s+code|source\s+files?|my\s+code|our\s+code|service|controller|endpoint|spring\s+boot|architecture|observability|logging|metrics|trace|telemetry|kafka|docker|kubernetes|pom\.xml|build\.gradle|application\.ya?ml|class|module|package)\b|(?:[οό]?\s*(?:κ[ώω]δικ[\p{L}]*|έργ[\p{L}]*|αρχιτεκτονικ[\p{L}]*|αρχε[ίι][\p{L}]*|κλ[άα]σ[\p{L}]*|μ[έε]τρικ[\p{L}]*|παρατηρησιμ[\p{L}]*|καταγραφ[\p{L}]*|ιχνηλ[άα]τ[\p{L}]*|εφαρμογ[\p{L}]*|π[ώω]ς\s+υλοποι[\p{L}]*)))/iu;

const CURIOSITY=/(?:\b(?:what|how\s+(?:does|is)|where\s+(?:is|are)|explain|find|show|inspect|review|check|analy[sz]e|what\s+does)\b|π[ώω]ς|πο[ύυ]|εξ[ήη]γησ[\p{L}]*|δείξε|δες|[έε]λεγξ[\p{L}]*|αν[άα]λυσ[\p{L}]*|τι\s+κ[άα]νει)/iu;

// Merely mentioning a technology ("Explain Kafka") must not cause file reads.
const REPOSITORY_ANCHOR=/(?:\b(?:project|repository|repo|codebase|service|controller|endpoint|source\s+files?|my\s+code|our\s+code|pom\.xml|build\.gradle|application\.ya?ml|class|module|package)\b|κ[ώω]δικ[\p{L}]*|έργ[\p{L}]*|εφαρμογ[\p{L}]*|κλ[άα]σ[\p{L}]*|αρχε[ίι][\p{L}]*)/iu;

// High-confidence repository review requests are actionable even when users
// naturally omit "the project" after selecting a local checkout.
// This only prepares a manifest; model calls still require explicit approval.
const SOURCE_REVIEW_INTENT=/(?:\b(?:can\s+you\s+|please\s+)?(?:analy[sz]e|review|inspect|audit|find|identify|check|look\s+for|fix)\b.{0,75}\b(?:bugs?|defects?|code\s+issues?|vulnerabilit(?:y|ies)|security\s+flaws?|code\s+review)\b|\b(?:code\s+review|bug\s+hunt|find\s+bugs|review\s+(?:my|our|the)\s+code)\b|(?:βρ(?:ε|ες)|βρες|βρ[εέ]στε|κ[άα]νε|[έε]λεγξ|αναλ[υύ]σ)[\p{L}\s]{0,55}(?:bug[s]?|σφ[άα]λμα[\p{L}]*|προβλ[ήη]μα[\p{L}]*|κ[ώω]δικ[\p{L}]*))/iu;
const GENERAL_HOWTO=/^(?:how\s+(?:do|can|should)\s+(?:i|we)|how\s+to|what\s+is|explain\s+how\s+to|πώς\s+μπορώ\s+να|πώς\s+να)\b/iu;

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
  if(!GENERAL_HOWTO.test(query)&&SOURCE_REVIEW_INTENT.test(query))return 'full';
  if(WHOLE.test(query)&&PROJECT.test(query))return 'full';
  if(PROJECT.test(query)&&CURIOSITY.test(query)&&REPOSITORY_ANCHOR.test(query))return 'focused';
  return 'none';
}
