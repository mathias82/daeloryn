"""Publish an approved workflow as a Draft PR with explicit one-use authorization.

The publisher must be operator-provided. A failure leaves publication_approved
for manual reconciliation: a push may have happened before an exception.
"""
from execution_authorization import authorize
from approved_pr_publish import publish as default_publish
from workflow_evidence import publication_subject, test_subject

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
 subject=publication_subject(store,workflow_id,expected_version,registry,
                             title,body,expected_commit)
 if digest!=subject["digest"]:
  raise PermissionError("approval does not cover this publication")
 # Invalid/expired approvals must not poison a publishable workflow. Consumption
 # precedes the versioned reservation; a concurrent loser may lose its token,
 # but cannot invoke the publisher or repeat a network side effect.
 approval_gate.consume(approval_token,"publish_pr",repository,subject["digest"])
 # Reserve the workflow state before any network side effect.
 reserved=store.transition(workflow_id,"approve_publication",
                           expected_version=expected_version,approved=True,
                           evidence={"verified":True,"subject":subject})
 # Recheck after the reservation; mutation now leaves a reconciliation state.
 publication_subject_state=store.load(workflow_id)
 if publication_subject_state.get("test_evidence")!=state.get("test_evidence"):
  raise PermissionError("test evidence changed during approval")
 if test_subject(registry,repository,state["test_evidence"]["suite"])!=state["test_evidence"]["subject"]:
  raise PermissionError("checkout changed during approval")
 result=publisher(checkout,title,body,expected_commit,approved=True,
                  expected_repository=repository,
                  expected_push_url=state["test_evidence"]["subject"]["snapshot"]["push_url"])
 if (not isinstance(result,dict) or result.get("published") is not True
     or result.get("draft_pr_created") is not True
     or result.get("commit")!=expected_commit
     or result.get("branch")!=state["test_evidence"]["subject"]["snapshot"]["branch"]):
  raise RuntimeError("publication unverified; reconcile before retry")
 final=store.transition(workflow_id,"published",expected_version=reserved["version"],
                        approved=True,evidence={"verified":True})
 return {"workflow":final,"publication":result}
