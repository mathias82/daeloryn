"""Durable approved benchmark runner tests, independent of provider/network."""
import http.client
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from benchmark_run_store import RunStore
from console_api import make_handler
from paired_review_benchmark import execute as real_execute


class BenchmarkRunStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory=Path(self.tmp.name)/"private"/"runs"
        self.store=RunStore(self.directory)
        # Worker completion must precede TemporaryDirectory cleanup. Under
        # Python 3.12/macOS, async atomic replaces may otherwise race rmtree.
        self.addCleanup(self.await_worker_completion)
        self.prepared={
            "repository":"demo","mode":"review","model":"test","agent":"java-reviewer",
            "source_sha256":"a"*64,"sha256":"b"*64,"total_model_calls":2,
            "baseline":{"batch_count":1},"daeloryn":{"batch_count":1}}
    def await_worker_completion(self):
        deadline=time.monotonic()+5
        while self.store.active is not None and time.monotonic()<deadline:
            time.sleep(0.02)
        self.assertIsNone(self.store.active, "benchmark worker must stop before fixture teardown")

    def test_persists_across_new_instances_and_preserves_partial_results(self):
        released=threading.Event()
        started=threading.Event()
        def worker(_prepared,_digest,*,progress,cancel_event,parallelism):
            progress({"type":"arm_started","arm":"baseline","total_batches":1})
            progress({"type":"batch_reply","arm":"baseline","batch":1,"reply":"A source finding"})
            started.set()
            released.wait(2)
            progress({"type":"arm_finished","arm":"baseline","status":"completed"})
            return {"status":"partial","arms":{"baseline":{
                "status":"completed","completed_batches":1,"total_batches":1,
                "failure":None,"review":{"reply":"A source finding"}}},
                "warning":"Specialist not reached"}
        receipt=self.store.start(self.prepared,"b"*64,worker)
        self.assertTrue(started.wait(2))
        store_after_reload=RunStore(self.directory)
        # A second process cannot know whether a previous worker survived; it marks
        # the old run interrupted, never automatically issues any model calls.
        recovered=store_after_reload.get(receipt["run_id"])
        self.assertEqual("interrupted",recovered["status"])
        self.assertIn("A source finding",recovered["arms"]["baseline"]["reply"])
        released.set()
        for _ in range(40):
            if self.store.get(receipt["run_id"])["status"]=="partial":break
            time.sleep(0.025)
        final=self.store.get(receipt["run_id"])
        self.assertEqual("partial",final["status"])
        self.assertEqual(1,final["arms"]["baseline"]["completed_batches"])
        self.assertEqual("completed",final["arms"]["baseline"]["status"])
        self.assertNotIn("source",final)
        self.assertEqual(["demo"],[r["repository"] for r in self.store.list()])
    def test_lock_prevents_overlapping_runs(self):
        waiting=threading.Event()
        release=threading.Event()
        def worker(*_args,**_kw):
            waiting.set()
            release.wait(2)
            return {"status":"completed","arms":{}}
        self.store.start(self.prepared,"b"*64,worker)
        self.assertTrue(waiting.wait(2))
        with self.assertRaises(RuntimeError):
            self.store.start(self.prepared,"b"*64,worker)
        release.set()
    def test_bad_approval_never_launches(self):
        with self.assertRaises(PermissionError):
            self.store.start(self.prepared,"c"*64,lambda *_args: self.fail("provider started"))
        self.assertEqual([],self.store.list())


    def test_stop_preserves_completed_batches_and_requires_terminal_state_for_deletion(self):
        started=threading.Event()
        def worker(_prepared,_digest,*,progress,cancel_event,parallelism):
            self.assertEqual(2,parallelism)
            progress({"type":"arm_started","arm":"baseline","total_batches":4})
            progress({"type":"progress","arm":"baseline","completed":1,"total":4})
            progress({"type":"batch_reply","arm":"baseline","batch":1,"reply":"Verified partial reply"})
            started.set()
            cancel_event.wait(2)
            return {"status":"stopped","arms":{"baseline":{
                "status":"stopped","completed_batches":1,"total_batches":4,
                "failure":"Cancelled","review":{"reply":"Verified partial reply"}}}}
        run=self.store.start(self.prepared,"b"*64,worker)
        self.assertTrue(started.wait(3))
        with self.assertRaises(RuntimeError):
            self.store.delete(run["run_id"])
        response=self.store.stop(run["run_id"])
        self.assertEqual("stopping",response["status"])
        self.assertEqual("stopping",self.store.get(run["run_id"])["status"])
        for _ in range(100):
            if self.store.get(run["run_id"])["status"]=="stopped":break
            time.sleep(0.02)
        receipt=self.store.get(run["run_id"])
        self.assertEqual("stopped",receipt["status"])
        self.assertIn("Verified partial reply",receipt["arms"]["baseline"]["reply"])
        self.assertEqual(1,receipt["arms"]["baseline"]["completed_batches"])
        self.assertEqual(True,self.store.delete(run["run_id"])["deleted"])
        self.assertEqual([],self.store.list())
        with self.assertRaises(FileNotFoundError):
            self.store.get(run["run_id"])

    def test_stopping_wont_launch_more_workers_or_allow_wrong_id(self):
        with self.assertRaises(ValueError):
            self.store.stop("../wrong")
        with self.assertRaises(ValueError):
            self.store.delete("../wrong")


class BenchmarkRunApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.repo=self.root/"demo"
        self.repo.mkdir()
        (self.repo/".git").mkdir()
        (self.repo/"App.java").write_text("class App {}")
        self.directory=self.root/"history"
        self.server=ThreadingHTTPServer(("127.0.0.1",0),
            make_handler(enable_copilot=True,repository_roots=[self.root],benchmark_runs_dir=self.directory))
        thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        thread.start()
        self.addCleanup(thread.join,2)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
    def request(self,method,path,body=None):
        connection=http.client.HTTPConnection("127.0.0.1",self.server.server_port,timeout=5)
        self.addCleanup(connection.close)
        kwargs={"headers":{"Origin":"http://127.0.0.1:5173"}}
        if body is not None:
            kwargs["body"]=json.dumps(body)
            kwargs["headers"]["Content-Type"]="application/json"
        connection.request(method,path,**kwargs)
        response=connection.getresponse()
        return response.status,json.loads(response.read())
    def test_approved_job_starts_and_gets_persisted(self):
        selection={"repository":"demo","mode":"review","model":"test","agent":"java-reviewer"}
        code,manifest=self.request("POST","/api/benchmark/prepare",selection)
        self.assertEqual(200,code)
        calls=[]
        def fake(request,**kwargs):
            calls.append(request)
            return {"reply":"Provider response"}
        def runner(prepared,digest,**kwargs):
            return real_execute(prepared,digest,transport=fake,**kwargs)
        with patch("console_api.execute_pair",side_effect=runner):
            code,run=self.request("POST","/api/benchmark/start",
                {**selection,"approved_sha256":manifest["sha256"]})
            self.assertEqual(202,code)
            for _ in range(80):
                code,detail=self.request("GET","/api/benchmark/runs/"+run["run_id"])
                if detail["status"]!="running":break
                time.sleep(0.025)
        self.assertEqual(200,code)
        self.assertEqual("completed",detail["status"])
        self.assertEqual(2,len(calls))
        self.assertEqual("not_determined",detail["result"]["winner"])
        self.assertEqual("Provider response",detail["arms"]["baseline"]["reply"])
        code,rows=self.request("GET","/api/benchmark/runs")
        self.assertEqual(200,code)
        self.assertEqual(run["run_id"],rows["runs"][0]["run_id"])

    def test_stop_and_delete_run_from_loopback_api(self):
        selection={"repository":"demo","mode":"review","model":"test","agent":"java-reviewer"}
        _,manifest=self.request("POST","/api/benchmark/prepare",selection)
        started=threading.Event()
        def worker(prepared,digest,*,progress,cancel_event,parallelism):
            progress({"type":"arm_started","arm":"baseline","total_batches":1})
            started.set()
            cancel_event.wait(4)
            return {"status":"stopped","arms":{}}
        with patch("console_api.execute_pair",side_effect=worker):
            code,run=self.request("POST","/api/benchmark/start",
                 {**selection,"approved_sha256":manifest["sha256"]})
            self.assertEqual(202,code)
            self.assertTrue(started.wait(2))
            rid=run["run_id"]
            code,error=self.request("POST","/api/benchmark/runs/"+rid+"/delete",{})
            self.assertEqual(409,code)
            code,stop=self.request("POST","/api/benchmark/runs/"+rid+"/stop",{})
            self.assertEqual(200,code)
            self.assertEqual("stopping",stop["status"])
            for _ in range(80):
                code,detail=self.request("GET","/api/benchmark/runs/"+rid)
                if detail["status"]=="stopped":break
                time.sleep(0.025)
            self.assertEqual("stopped",detail["status"])
            code,deleted=self.request("POST","/api/benchmark/runs/"+rid+"/delete",{})
            self.assertEqual(200,code)
            self.assertTrue(deleted["deleted"])
            code,_=self.request("GET","/api/benchmark/runs/"+rid)
            self.assertEqual(404,code)
            self.assertEqual([],(self.request("GET","/api/benchmark/runs"))[1]["runs"])

    def test_unapproved_or_changed_source_cannot_start_run(self):
        selection={"repository":"demo","mode":"review","model":"test","agent":"java-reviewer"}
        _,manifest=self.request("POST","/api/benchmark/prepare",selection)
        (self.repo/"App.java").write_text("class Modified {}")
        with patch("console_api.execute_pair") as provider:
            code,error=self.request("POST","/api/benchmark/start",
                {**selection,"approved_sha256":manifest["sha256"]})
            self.assertEqual(400,code)
            provider.assert_not_called()
        self.assertEqual([],(self.request("GET","/api/benchmark/runs"))[1]["runs"])

if __name__=="__main__":
    unittest.main()
