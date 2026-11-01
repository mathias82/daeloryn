"""Deterministic bounds for faster 2-wide read-only review batching."""
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from approved_copilot_review import prepare,execute


class FasterBatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        project=self.root/"demo"
        project.mkdir()
        (project/".git").mkdir()
        # Enough eligible source to require multiple approved model calls.
        for index in range(5):
            (project/("Service%s.java"%index)).write_text(
                "public class Service%s {\n"%index+
                ("  // safe placeholder source for batching verification\n"*440)+
                "}\n",encoding="utf-8")
        self.prepared=prepare(self.root,"demo","Review all Java source defects","test")
        self.assertGreaterEqual(self.prepared["batch_count"],4)

    def test_two_concurrent_calls_max_and_ordered_result(self):
        guard=threading.Lock()
        running=[0]
        high=[0]
        calls=[0]
        def provider(request,**kwargs):
            with guard:
                running[0]+=1
                high[0]=max(high[0],running[0])
                calls[0]+=1
                number=calls[0]
            try:
                # Deliberately make the first response slower than second.
                time.sleep(0.05 if number==1 else 0.012)
                return {"reply":"Result number %d"%number}
            finally:
                with guard:
                    running[0]-=1
        updates=[]
        outcome=execute(self.prepared,"test",self.prepared["sha256"],
                        transport=provider,progress=updates.append,parallelism=2,
                        stream_replies=True)
        self.assertEqual("completed",outcome["status"])
        self.assertEqual(2,high[0])
        self.assertEqual(self.prepared["batch_count"],calls[0])
        self.assertEqual(calls[0],outcome["completed_batches"])
        # Replies are reported by actual batch identity, not completion time.
        batches=[event["batch"] for event in updates if event["type"]=="batch_reply"]
        self.assertEqual(sorted(batches),list(range(1,calls[0]+1)))
        self.assertIn("Batch 1:",outcome["review"]["reply"])
        self.assertIn("Batch 2:",outcome["review"]["reply"])

    def test_stop_prevents_dispatch_after_inflight_pair(self):
        cancel=threading.Event()
        started=threading.Event()
        release=threading.Event()
        guard=threading.Lock()
        count=[0]
        def provider(request,**kwargs):
            with guard:
                count[0]+=1
                if count[0]==2:started.set()
            release.wait(3)
            return {"reply":"Completed in-flight response"}
        result={}
        def run():
            result["outcome"]=execute(self.prepared,"test",self.prepared["sha256"],
                transport=provider,cancel_event=cancel,parallelism=2)
        task=threading.Thread(target=run,daemon=True)
        task.start()
        self.assertTrue(started.wait(3))
        cancel.set()
        release.set()
        task.join(timeout=4)
        self.assertFalse(task.is_alive())
        self.assertEqual(2,count[0])
        self.assertEqual("stopped",result["outcome"]["status"])
        self.assertGreater(result["outcome"]["remaining_not_run"],0)
        self.assertEqual(2,result["outcome"]["completed_batches"])

    def test_old_one_call_execution_is_unchanged(self):
        count=[]
        def provider(request,**kwargs):
            count.append(request)
            return {"reply":"reviewed"}
        result=execute(self.prepared,"test",self.prepared["sha256"],transport=provider)
        self.assertEqual("completed",result["status"])
        self.assertEqual(self.prepared["batch_count"],len(count))
        self.assertEqual(0,result["remaining_not_run"])


if __name__=="__main__":
    unittest.main()
