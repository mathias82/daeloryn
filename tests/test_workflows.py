import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("workflows", ROOT / "scripts/workflows.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class WorkflowTests(unittest.TestCase):
    def test_all_workflows(self):
        for path in (ROOT / "workflows").glob("*.json"):
            with self.subTest(path=path.name):
                result = mod.plan(json.loads(path.read_text()))
                self.assertTrue(result["waves"])
                self.assertTrue(result["requires_approval"])

    def test_parallel_dependency_waves(self):
        data = {"schema_version":1,"steps":[
            {"id":"a","agent":"a","depends_on":[]},
            {"id":"b","agent":"b","depends_on":["a"]},
            {"id":"c","agent":"c","depends_on":["a"]},
            {"id":"gate","type":"approval","depends_on":["b","c"]}]}
        self.assertEqual(mod.plan(data, {"a","b","c"})["waves"],[["a"],["b","c"],["gate"]])

    def test_cycles_and_unknown_agents_rejected(self):
        cyclic = {"schema_version":1,"steps":[
            {"id":"a","agent":"a","depends_on":["b"]},
            {"id":"b","agent":"a","depends_on":["a"]}]}
        with self.assertRaises(ValueError):
            mod.plan(cyclic, {"a"})
        with self.assertRaises(ValueError):
            mod.plan({"schema_version":1,"steps":[{"id":"a","agent":"missing","depends_on":[]}]}, {"known"})
