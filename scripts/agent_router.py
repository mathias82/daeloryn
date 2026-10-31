"""Deterministic Daeloryn specialist recommendation; never executes agent tools."""
import re
from agents import catalog

RULES = (
    ("security", r"security|vulnerab|oauth|jwt|csrf|xss|authenticat|authoriz|credential|secret|ασφαλ|ασφάλ"),
    ("java", r"java|jvm|thread|concurren|deadlock|virtual.thread|maven|gradle|κώδικ"),
    ("spring", r"spring|webflux|hibernate|jpa|bean|transaction|microservice"),
    ("react", r"react|typescript|tsx|frontend|css|javascript|vite|browser|ui\\b"),
    ("platform", r"kubernetes|k8s|docker|helm|terraform|azure|aks|devops|pipeline|istio"),
    ("test", r"test|junit|mockito|regression|coverage|playwright|δοκιμ"),
    ("architecture", r"architect|design|system.design|scalab|hld|αρχιτεκ"),
    ("review", r"review|audit|inspect|analy[sz]e|ελεγ|έλεγ"),
)
def recommend(task, agents=None):
    if not isinstance(task, str) or not task.strip() or len(task) > 3000:
        raise ValueError("task must be nonempty and bounded")
    items = agents if agents is not None else [m for m,_ in catalog()]
    if not isinstance(items,list) or not items:
        raise ValueError("agent catalog required")
    for item in items:
        if not isinstance(item,dict) or not all(isinstance(item.get(k),str) for k in ("name","scope","description")):
            raise ValueError("invalid agent metadata")
    matches=[]
    for label,pattern in RULES:
        if re.search(pattern,task,re.I):
            matches.append(label)
    if not matches:
        return {"agent":None,"reason":"No unambiguous specialist signal","confidence":"none","execution":"not_run"}
    # Use catalog scope/description, not fabricated agent names.
    scored=[]
    for item in items:
        corpus=(item["name"]+" "+item["scope"]+" "+item["description"]).casefold()
        score=sum(3 if label in item["name"].casefold() else 1 if label in corpus else 0 for label in matches)
        if score:
            scored.append((score,item["name"]))
    scored.sort(key=lambda x:(-x[0],x[1]))
    if not scored or (len(scored)>1 and scored[0][0]==scored[1][0]):
        return {"agent":None,"reason":"No unique matching specialist","confidence":"none","execution":"not_run"}
    return {"agent":scored[0][1],"reason":"Matched task signals: "+", ".join(matches),
            "confidence":"heuristic","execution":"not_run"}
