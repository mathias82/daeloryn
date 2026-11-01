"""Publish an approved workflow as a Draft PR with explicit one-use authorization.

The publisher must be operator-provided. A failure leaves publication_approved
for manual reconciliation: a push may have happened before an exception.
"""
from execution_authorization import authorize
from approved_pr_publish import publish as default_publish

def publish_workflow_draft(store,workflow_id,expected_version,principal,registry,
                           digest,approval_token,approval_gate,title,body,
                           expected_commit,*,publisher=default_publish):
 state=store.load(workflow_id)
 if state["version"]!=expected_version or state["stage"]!="tests_passed":
  raise RuntimeError("verified tests required before publication")
 repository=state["repository"]
 authorize(principal,repository,"publish_pr")
 checkout=registry.resolve(repository)
 if not callable(publisher):
  raise TypeError("trusted publisher required")
 # Reserve the workflow state before any network side effect.
 reserved=store.transition(workflow_id,"approve_publication",
                           expected_version=expected_version,approved=True)
 approval_gate.consume(approval_token,"publish_pr",repository,digest)
 result=publisher(checkout,title,body,expected_commit,approved=True)
 if not isinstance(result,dict) or result.get("published") is not True or result.get("draft_pr_created") is not True:
  raise RuntimeError("publication unverified; reconcile before retry")
 final=store.transition(workflow_id,"published",expected_version=reserved["version"],
                        approved=True,evidence={"verified":True})
 return {"workflow":final,"publication":result}
