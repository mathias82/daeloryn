import sys
import subprocess
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from workflow_orchestrator import WorkflowStore

class WorkflowConcurrencyTests(unittest.TestCase):
 def test_concurrent_threads_only_one_transition(self):
  with TemporaryDirectory() as d:
   store=WorkflowStore(d)
   store.create("job","repo","task")
   def attempt(_):
    try:
     WorkflowStore(d).transition("job","prepare",expected_version=0)
     return True
    except RuntimeError:return False
   with ThreadPoolExecutor(max_workers=8) as pool:
    results=list(pool.map(attempt,range(8)))
   self.assertEqual(1,sum(results))
   self.assertEqual(1,store.load("job")["version"])
 def test_concurrent_processes_only_one_transition(self):
  with TemporaryDirectory() as d:
   store=WorkflowStore(d)
   store.create("job","repo","task")
   script="""import sys
sys.path.insert(0,sys.argv[1])
from workflow_orchestrator import WorkflowStore
sys.stdin.read(1)
try:
 WorkflowStore(sys.argv[2]).transition('job','prepare',expected_version=0)
 print('won')
except RuntimeError:
 print('stale')
"""
   processes=[]
   try:
    for _ in range(4):
     processes.append(subprocess.Popen([sys.executable,"-c",script,
                      str(Path(__file__).resolve().parents[1]/"scripts"),d],
                      stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True))
    for process in processes:
     process.stdin.write("x")
     process.stdin.flush()
    results=[]
    for process in processes:
     out,err=process.communicate(timeout=20)
     self.assertEqual(0,process.returncode,err)
     results.append(out.strip())
    self.assertCountEqual(["won","stale","stale","stale"],results)
    self.assertEqual(1,store.load("job")["version"])
   finally:
    for process in processes:
     if process.poll() is None:process.kill()
     process.communicate()
 def test_stale_transition_rejected(self):
  with TemporaryDirectory() as d:
   store=WorkflowStore(d)
   store.create("job","repo","task")
   store.transition("job","prepare",expected_version=0)
   with self.assertRaises(RuntimeError):
    store.transition("job","prepare",expected_version=0)
 def test_last_failure_recorded_and_fourth_attempt_blocked(self):
  with TemporaryDirectory() as d:
   store=WorkflowStore(d)
   store.create("job","repo","task")
   store.transition("job","prepare",expected_version=0)
   store.transition("job","approve_patch",expected_version=1,approved=True)
   for n in range(3):
    store.transition("job","start_tests",expected_version=2+n*2,approved=True)
    store.transition("job","tests_failed",expected_version=3+n*2)
   self.assertEqual(3,store.load("job")["attempts"])
   with self.assertRaises(RuntimeError):
    store.transition("job","start_tests",expected_version=8,approved=True)
if __name__=="__main__":unittest.main()
