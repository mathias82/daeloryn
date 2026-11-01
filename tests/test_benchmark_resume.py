"""Same-run resumption uses completed batch receipts and explicit unknown-attempt consent."""
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from benchmark_run_store import RunStore

class ResumeJournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store=RunStore(Path(self.tmp.name)/"private"/"runs")
        self.addCleanup(self.wait_for_worker)
        self.prepared={
            "repository":"demo","mode":"review","model":"test","agent":"java-reviewer",
            "source_sha256":"a"*64,"sha256":"b"*64,"total_model_calls":5,
            "baseline":{"batch_count":3},"daeloryn":{"batch_count":2}}
    def wait_for_worker(self):
        deadline=time.monotonic()+5
        while self.store.active is not None and time.monotonic()<deadline:
            time.sleep(0.02)
        self.assertIsNone(self.store.active)
    def await_state(self,id,expected):
        for _ in range(150):
            receipt=self.store.get(id)
            if receipt["status"]==expected:return receipt
            time.sleep(0.02)
        self.fail("Run never reached "+expected+": "+str(receipt))
    def partial_worker(self,_prepared,_digest,*,progress,cancel_event,parallelism):
        progress({"type":"arm_started","arm":"baseline","total_batches":3})
        progress({"type":"batch_started","arm":"baseline","batch":1})
        progress({"type":"batch_reply","arm":"baseline","batch":1,"reply":"Finding from completed batch 1"})
        progress({"type":"batch_started","arm":"baseline","batch":2})
        progress({"type":"batch_failed","arm":"baseline","batch":2})
        progress({"type":"arm_finished","arm":"baseline","status":"partial"})
        return {"status":"partial","arms":{"baseline":{
            "status":"partial","completed_batches":1,"total_batches":3,
            "failure":"unknown provider result",
            "review":{"reply":"Finding from completed batch 1"}}}}
    def test_resume_same_id_skips_completed_and_requires_unknown_ack(self):
        first=self.store.start(self.prepared,"b"*64,self.partial_worker)
        id=first["run_id"]
        old=self.await_state(id,"partial")
        self.assertEqual({"1":"completed","2":"unknown"},
            {k:v["status"] for k,v in old["arms"]["baseline"]["batches"].items()})
        with self.assertRaises(PermissionError):
            self.store.resume(id,self.prepared,"b"*64,lambda *a,**k:self.fail("must not call provider"))
        with self.assertRaises(PermissionError):
            self.store.resume(id,{**self.prepared,"source_sha256":"changed"},"b"*64,
                              lambda *a,**k:self.fail("different source"))
        resumed=threading.Event()
        def worker(_prepared,_digest,*,progress,cancel_event,parallelism,resume_completed):
            self.assertEqual({1:"Finding from completed batch 1"},resume_completed["baseline"])
            self.assertEqual({},resume_completed["daeloryn"])
            # Exact batch 1 must never be dispatched twice.
            for number in (2,3):
                progress({"type":"batch_started","arm":"baseline","batch":number})
                progress({"type":"batch_reply","arm":"baseline","batch":number,
                          "reply":"Result "+str(number)})
            progress({"type":"arm_finished","arm":"baseline","status":"completed"})
            for number in (1,2):
                progress({"type":"batch_started","arm":"daeloryn","batch":number})
                progress({"type":"batch_reply","arm":"daeloryn","batch":number,
                          "reply":"Specialist "+str(number)})
            progress({"type":"arm_finished","arm":"daeloryn","status":"completed"})
            resumed.set()
            return {"status":"completed","arms":{
                "baseline":{"status":"completed","completed_batches":3,"total_batches":3,
                    "failure":None,"review":{"reply":"Finding from completed batch 1\nResult 2\nResult 3"}},
                "daeloryn":{"status":"completed","completed_batches":2,"total_batches":2,
                    "failure":None,"review":{"reply":"Specialist 1\nSpecialist 2"}}}}
        accepted=self.store.resume(id,self.prepared,"b"*64,worker,acknowledge_unknown=True)
        self.assertEqual(id,accepted["run_id"])
        self.assertTrue(resumed.wait(3))
        final=self.await_state(id,"completed")
        self.assertEqual(1,final["resume_attempts"])
        self.assertEqual(3,len(final["arms"]["baseline"]["batches"]))
        self.assertEqual(2,len(final["arms"]["daeloryn"]["batches"]))
        self.assertEqual("Finding from completed batch 1",final["arms"]["baseline"]["batches"]["1"]["reply"])
        self.assertEqual(1,len(self.store.list()))
    def test_legacy_run_fails_closed_without_batch_receipts(self):
        run=self.store.start(self.prepared,"b"*64,self.partial_worker)
        id=run["run_id"]
        self.await_state(id,"partial")
        with self.store.guard:
            value=self.store.get(id)
            value["arms"]["baseline"].pop("batches")
            self.store._save(value)
        with self.assertRaises(ValueError):
            self.store.resume(id,self.prepared,"b"*64,lambda *args,**kwargs:None,True)

if __name__=="__main__":unittest.main()
