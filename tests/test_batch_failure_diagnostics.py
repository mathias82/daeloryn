"""Provider failures are diagnosable without exposing private CLI output."""
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from copilot_chat import copilot_chat, CopilotFailure, safe_failure
from approved_copilot_review import prepare, execute
from benchmark_run_store import RunStore


class BatchDiagnosticsTests(unittest.TestCase):
    def test_untrusted_error_text_is_not_disclosed(self):
        for exc in (RuntimeError("private prompt and credential fixture"),
                    OSError("private local path"), ValueError("private output")):
            detail=safe_failure(exc, 9)
            self.assertNotIn("private", str(detail))
            self.assertEqual(9, detail["batch"])
            self.assertFalse(detail["automatic_retry"])

    @unittest.skipUnless(os.name == "posix", "POSIX transport")
    def test_transport_distinguishes_exit_output_empty_and_timeout(self):
        request={"model":"test","messages":[{"role":"user","content":"Fixture"}]}
        cases=[("cli_exit",3,b"private CLI output",False),
               ("output_limit",0,b"x"*65537,False),
               ("empty_output",0,b"",False),
               ("provider_timeout",0,b"",True)]
        for code,exit_code,output,timed_out in cases:
            with self.subTest(code=code):
                def launch(*args,**kwargs):
                    kwargs["stdout"].write(output)
                    process=Mock(pid=1234)
                    process.wait.side_effect=([subprocess.TimeoutExpired("fixture",90),0]
                                              if timed_out else [exit_code])
                    return process
                with patch("copilot_chat.subprocess.Popen",side_effect=launch), patch("copilot_chat.os.killpg"):
                    with self.assertRaises(CopilotFailure) as caught:
                        copilot_chat(request,executable="/fixture/copilot")
                detail=safe_failure(caught.exception,9)
                self.assertEqual(code,detail["code"])
                self.assertNotIn("private",str(detail))
                if code=="cli_exit":self.assertEqual(3,detail["exit_code"])
                if timed_out:self.assertEqual(90,detail["timeout_seconds"])

    def test_failed_batch_is_exact_and_completed_receipts_are_reused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);project=root/"demo";project.mkdir();(project/".git").mkdir()
            for n in range(5):
                (project/("Service%d.java"%n)).write_text("class Service {}\n"+"// approved batching fixture\n"*700,encoding="utf-8")
            prepared=prepare(root,"demo","Review Java","test")
            self.assertGreater(prepared["batch_count"],2)
            for parallelism in (1,2):
                with self.subTest(parallelism=parallelism):
                    events=[];calls=[]
                    def failing(request,**kwargs):
                        index=prepared["prompts"].index(request["messages"][0]["content"])+1
                        calls.append(index)
                        if index==2:raise CopilotFailure("provider_timeout",timeout_seconds=90)
                        return {"reply":"Completed batch %d"%index}
                    result=execute(prepared,"test",prepared["sha256"],transport=failing,
                                   parallelism=parallelism,resume_batches={1:"Previously saved"},
                                   progress=events.append,stream_replies=True)
                    self.assertEqual("partial",result["status"])
                    self.assertEqual(2,result["failure_details"]["batch"])
                    self.assertEqual("provider_timeout",result["failure_details"]["code"])
                    self.assertIn("Batch 2",result["failure"])
                    self.assertNotIn(1,calls);self.assertEqual(1,calls.count(2))
                    self.assertEqual(2,next(e["batch"] for e in events if e["type"]=="progress" and e["phase"]=="running"))
                    confirmed={1:"Previously saved",**{e["batch"]:e["reply"] for e in events if e["type"]=="batch_reply"}}
                    resumed_calls=[]
                    def resumed(request,**kwargs):
                        index=prepared["prompts"].index(request["messages"][0]["content"])+1
                        resumed_calls.append(index)
                        return {"reply":"Completed after approval"}
                    resumed_result=execute(prepared,"test",prepared["sha256"],transport=resumed,
                                           parallelism=parallelism,resume_batches=confirmed)
                    self.assertEqual("completed",resumed_result["status"])
                    self.assertIsNone(resumed_result["failure_details"])
                    self.assertTrue(set(confirmed).isdisjoint(resumed_calls))
                    self.assertEqual(prepared["batch_count"],resumed_result["completed_batches"])

    def test_failure_details_survive_store_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=RunStore(Path(tmp)/"runs")
            prepared={"repository":"demo","mode":"review","model":"test","agent":"java-reviewer",
                      "source_sha256":"a"*64,"sha256":"b"*64,"total_model_calls":2,
                      "baseline":{"batch_count":1},"daeloryn":{"batch_count":1}}
            detail=safe_failure(CopilotFailure("cli_exit",exit_code=7),1)
            def worker(_prepared,_digest,*,progress,**kwargs):
                progress({"type":"batch_failed","arm":"baseline","batch":1,"diagnostic":detail})
                return {"status":"partial","arms":{"baseline":{"status":"partial",
                        "completed_batches":0,"total_batches":1,"failure":"CLI failed",
                        "failure_details":detail,"review":{"reply":""}}}}
            receipt=store.start(prepared,"b"*64,worker)
            deadline=time.monotonic()+5
            while store.active is not None and time.monotonic()<deadline:time.sleep(0.01)
            self.assertIsNone(store.active)
            row=RunStore(Path(tmp)/"runs").get(receipt["run_id"])["arms"]["baseline"]
            self.assertEqual(detail,row["failure_details"])
            self.assertEqual(detail,row["batches"]["1"]["diagnostic"])
