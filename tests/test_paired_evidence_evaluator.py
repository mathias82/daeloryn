"""No-cost paired review evidence scoring tests; no provider, edits or test execution."""
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from paired_evidence_evaluator import evaluate, source_from_prepared, source_from_context, context_digest
from benchmark_run_store import RunStore


def sample():
    context={"files":[{"path":"src/App.java","source":"class App {\n String value;\n String get(){return value.toString();}\n}\n"}],
             "omitted":[],"excluded":[]}
    block={"file":"src/App.java","line":1,"column":1,"end_line":4,
           "source":context["files"][0]["source"]}
    prompt="Review source\n"+json.dumps(block)+"\n"
    prepared={"repository":"demo","mode":"review","model":"test-model","agent":"java-reviewer",
              "sha256":"b"*64,"source_sha256":context_digest(context),"total_model_calls":2,
              "baseline":{"batch_count":1,"prompts":[prompt]},
              "daeloryn":{"batch_count":1,"prompts":[prompt]}}
    record={"status":"completed","source_sha256":prepared["source_sha256"],
            "arms":{
                "baseline":{"status":"completed","completed_batches":1,"total_batches":1,
                   "reply":"Potential bug src/App.java:99; another nonexistent path src/App.java:92"},
                "daeloryn":{"status":"completed","completed_batches":1,"total_batches":1,
                   "reply":"Possible null dereference src/App.java:3. Fix src/App.java:3. Investigate manually."}}}
    return context,prepared,record


class EvidenceEvaluatorTests(unittest.TestCase):
    def test_line_grounding_and_deduplication_do_not_certify_bug(self):
        context,prepared,record=sample()
        comparison=evaluate(record,source_from_prepared(prepared))
        self.assertTrue(comparison["comparable_completed_arms"])
        self.assertEqual("daeloryn",comparison["provisional_evidence_lead"])
        self.assertEqual(0,comparison["arms"]["baseline"]["unique_code_locations"])
        self.assertEqual(1,comparison["arms"]["daeloryn"]["unique_code_locations"])
        self.assertEqual(1,comparison["arms"]["daeloryn"]["duplicate_matched_citations"])
        self.assertEqual(2,comparison["arms"]["baseline"]["unsupported_references"])
        self.assertIsNone(comparison["verified_winner"])
        self.assertFalse(comparison["independent_checks_executed"])
    def test_partial_run_never_gets_comparable_leader(self):
        context,prepared,record=sample()
        record["status"]="partial"
        result=evaluate(record,source_from_context(context))
        self.assertEqual("not_comparable",result["provisional_evidence_lead"])
    def test_ambiguous_basename_never_points_to_random_source(self):
        context,prepared,record=sample()
        names={"src/Foo.java":{1,2,3},"other/Foo.java":{1,2,3}}
        record["arms"]["baseline"]["reply"]="Failure Foo.java:2"
        result=evaluate(record,names)
        self.assertEqual("ambiguous_filename",
                         result["arms"]["baseline"]["references"][0]["status"])
    def test_saved_legacy_evaluation_rejects_different_source_without_provider_calls(self):
        context,prepared,record=sample()
        with TemporaryDirectory() as home:
            store=RunStore(Path(home)/"receipts")
            def worker(_prepared,_digest,*,progress,cancel_event,parallelism):
                for arm in ("baseline","daeloryn"):
                    progress({"type":"arm_started","arm":arm,"total_batches":1})
                    progress({"type":"batch_started","arm":arm,"batch":1})
                    progress({"type":"batch_reply","arm":arm,"batch":1,"reply":record["arms"][arm]["reply"]})
                    progress({"type":"arm_finished","arm":arm,"status":"completed"})
                return {"status":"completed","arms":{
                    a:{"status":"completed","completed_batches":1,"total_batches":1,
                       "failure":None,"review":{"reply":record["arms"][a]["reply"]}}
                    for a in ("baseline","daeloryn")}}
            start=store.start(prepared,prepared["sha256"],worker)
            import time
            for _ in range(150):
                receipt=store.get(start["run_id"])
                if receipt["status"]=="completed" and store.active is None:break
                time.sleep(.01)
            self.assertEqual("completed",receipt["status"])
            self.assertEqual("daeloryn",receipt["comparison"]["provisional_evidence_lead"])
            # Recompute from saved local text only (no Copilot calls).
            receipt.pop("comparison",None)
            with store.guard:store._save(receipt)
            saved=store.evaluate_saved(start["run_id"],context)
            self.assertEqual("daeloryn",saved["comparison"]["provisional_evidence_lead"])
            altered={**context,"files":[{"path":"src/App.java","source":"different code\n"}]}
            with self.assertRaises(PermissionError):
                store.evaluate_saved(start["run_id"],altered)
            self.assertEqual(1,len(store.comparison_summaries()))


if __name__=="__main__":
    unittest.main()
