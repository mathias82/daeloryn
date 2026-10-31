import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from agent_router import recommend

CATALOG=[
 {"name":"java-reviewer","scope":"java","description":"Java concurrency correctness"},
 {"name":"react-reviewer","scope":"react","description":"React TypeScript frontend"},
 {"name":"platform-engineer","scope":"platform","description":"Kubernetes Docker Azure"},
]
class AgentRouterTests(unittest.TestCase):
 def test_java(self):
  self.assertEqual("java-reviewer",recommend("Review Java concurrency",CATALOG)["agent"])
 def test_react(self):
  self.assertEqual("react-reviewer",recommend("Fix React TypeScript UI",CATALOG)["agent"])
 def test_platform(self):
  self.assertEqual("platform-engineer",recommend("Fix Kubernetes deployment",CATALOG)["agent"])
 def test_unknown_fails_closed(self):
  self.assertIsNone(recommend("Hello there",CATALOG)["agent"])
 def test_ambiguous_fails_closed(self):
  self.assertIsNone(recommend("Java",[
   {"name":"java-a","scope":"java","description":"Java"},
   {"name":"java-b","scope":"java","description":"Java"}])["agent"])
 def test_bad_input(self):
  with self.assertRaises(ValueError):recommend("",CATALOG)
 def test_never_executes(self):
  self.assertEqual("not_run",recommend("Fix React",CATALOG)["execution"])
if __name__=="__main__":unittest.main()
