/** Deterministic, locally auditable specialist selection. Never invent profiles. */
export function recommendSpecialist(task:string,technologies:string[],agents:string[]):{agent:string;reason:string}|null{
  const text=task.toLowerCase();
  const tech=technologies.join(' ').toLowerCase();
  const has=(name:string)=>agents.includes(name);
  const choose=(name:string,reason:string)=>has(name)?{agent:name,reason}:null;
  if(/oauth|jwt|csrf|xss|vulnerab|security|authentication|authorization|ασφάλ/.test(text))
    return choose('security-reviewer','security review requested')||choose('spring-security-engineer','security review requested');
  if(/kubernetes|k8s|helm|container|deployment|aks|docker/.test(text))
    return choose('kubernetes-engineer','platform/deployment question');
  if(/react|tsx|frontend|typescript|browser|component/.test(text))
    return choose('react-reviewer','React/frontend question');
  if(/spring|transaction|jpa|hibernate|webflux|bean/.test(text))
    return choose('spring-framework-expert','Spring framework question');
  if(/architecture|architect|design|αρχιτεκ/.test(text))
    return choose('java-architect','architecture question');
  if(/test|junit|mockito|regression|δοκιμ/.test(text))
    return choose('java-testing','testing question');
  if(/java|jvm|maven|pom(?:\.xml)?|gradle|class|method|bug|review|defect|κώδικ|σφάλμ/.test(text))
    return choose('java-reviewer','Java/code review question');
  if(/spring|java|maven/.test(tech))
    return choose('java-reviewer','Java detected in selected local project');
  if(/react|typescript/.test(tech))
    return choose('react-reviewer','frontend detected in selected local project');
  return null;
}
