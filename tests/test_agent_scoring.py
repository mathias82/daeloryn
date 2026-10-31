import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
scorer = load("score_agents")
prompts = load("prepare_agent_cases")
REFERENCE = json.loads((ROOT / "evaluations/platform/cases.json").read_text())

class AgentScoringTests(unittest.TestCase):
    def test_perfect_result(self):
        cases = [{"case_id": c["id"], "findings": [{"id": fid, "evidence": "observed"} for fid in c["expected"]]} for c in REFERENCE["cases"]]
        outcome = scorer.score({"cases": cases}, REFERENCE)
        self.assertEqual((outcome["tp"], outcome["fp"], outcome["fn"]), (7, 0, 0))
        self.assertEqual(outcome["f1"], 1.0)

    def test_missing_cases_count_as_false_negatives(self):
        outcome = scorer.score({"cases": []}, REFERENCE)
        self.assertEqual((outcome["tp"], outcome["fp"], outcome["fn"]), (0, 0, 7))
        self.assertEqual(outcome["recall"], 0.0)

    def test_unknown_prediction_counts_as_false_positive(self):
        outcome = scorer.score({"cases": [{"case_id": "docker-root", "findings": [
            {"id": "docker.not-a-real-defect", "evidence": "line 1"}]}]}, REFERENCE)
        self.assertEqual(outcome["fp"], 1)
        self.assertEqual(outcome["fn"], 7)

    def test_reject_duplicate_and_unsubstantiated_findings(self):
        with self.assertRaises(ValueError):
            scorer.score({"cases": [{"case_id": "docker-root", "findings": [
                {"id": "docker.root-user", "evidence": ""}]}]}, REFERENCE)
        with self.assertRaises(ValueError):
            scorer.score({"cases": [{"case_id": "docker-root"}, {"case_id": "docker-root"}]}, REFERENCE)

    def test_prompt_hides_reference_labels(self):
        p = prompts.prompt_for("docker-root")
        self.assertIn("FROM ubuntu:latest", p)
        self.assertNotIn("docker.root-user", p)
        self.assertNotIn('"expected"', p)
