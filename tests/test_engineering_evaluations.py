import json
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from evaluate_engineering import reference,prompt_for
from score_agents import score

class EngineeringEvaluationTests(unittest.TestCase):
    def test_reference_cases(self):
        data=reference()
        self.assertEqual(len(data["cases"]),4)
        self.assertEqual(sum(len(c["expected"]) for c in data["cases"]),8)

    def test_prompts_hide_gold_labels(self):
        data=reference()
        for case in data["cases"]:
            with self.subTest(case=case["id"]):
                prompt=prompt_for(case["id"])
                self.assertIn(case["agent"],prompt)
                for label in case["expected"]:
                    self.assertNotIn(label,prompt)

    def test_perfect_synthetic_submission(self):
        data=reference()
        submission={"run_id":"offline-reference","tool":"synthetic","model":"none",
            "cases":[{"case_id":c["id"],
                      "findings":[{"id":fid,"evidence":"synthetic nonempty evidence"} for fid in c["expected"]]}
                     for c in data["cases"]]}
        result=score(submission,data)
        self.assertEqual((result["tp"],result["fp"],result["fn"]),(8,0,0))
        self.assertEqual(result["f1"],1.0)

    def test_missing_and_extra_finding_affect_metrics(self):
        data=reference()
        submission={"cases":[{"case_id":data["cases"][0]["id"],
                              "findings":[{"id":"incorrect.finding","evidence":"synthetic"}]}]}
        result=score(submission,data)
        self.assertEqual(result["tp"],0)
        self.assertEqual(result["fp"],1)
        self.assertEqual(result["fn"],8)
