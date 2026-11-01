export type ChatMessage = {role:'user'|'assistant';content:string};
export type ReviewSelection = {repository:string;task:string;model:string;agent?:string};

// The preview recommendation does not silently activate a specialist.
export function selectedAgent(agent:string):string|undefined {
  return agent==='Automatic (preview)'?undefined:agent;
}

export function chatRequest(model:string,messages:ChatMessage[],agent?:string) {
  return {model,messages,...(agent?{agent}:{})};
}

export function reviewRequest(selection:ReviewSelection,approvedDigest?:string) {
  if (!selection.model)
    throw new Error('Choose a Copilot model before preparing source review.');
  return {...selection,...(approvedDigest?{approved_sha256:approvedDigest}:{})};
}

export function reviewSelectionKey(selection:ReviewSelection):string {
  return JSON.stringify(selection);
}
