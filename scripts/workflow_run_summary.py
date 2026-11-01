"""Read-only workflow status projection for console and diagnostics."""
from workflow_orchestrator import WorkflowStore

def summarize(directory,identifier):
 state=WorkflowStore(directory).load(identifier)
 stage=state["stage"]
 return {"id":state["id"],"repository":state["repository"],
         "stage":stage,"version":state["version"],"attempts":state["attempts"],
         "requires_operator":stage in ("tests_running","publication_approved"),
         "terminal":stage=="published","can_auto_publish":False}
