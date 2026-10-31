import sys
from pathlib import Path
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from copilot_auto import route_chat, available_models

def request(text="Summarize this text"):
    return {"model":"auto","messages":[{"role":"user","content":text}]}

class CopilotAutoTests(unittest.TestCase):
    def test_small_task_prefers_available_haiku(self):
        routed, plan = route_chat(request(),lambda:["claude-sonnet-4","claude-haiku-4"])
        self.assertEqual("claude-haiku-4",routed["model"])
        self.assertEqual("small",plan["effective_kind"])
    def test_code_prefers_sonnet(self):
        routed, plan = route_chat(request("Fix Java concurrency bug"),lambda:["claude-haiku-4","claude-sonnet-4"])
        self.assertEqual("claude-sonnet-4",routed["model"])
        self.assertTrue(plan["risk_detected"])
    def test_no_silent_fallback(self):
        with self.assertRaises(ValueError):
            route_chat(request("Fix Java"),lambda:["unrelated-model"])
    def test_invalid_prompt_no_discovery(self):
        called=[]
        with self.assertRaises(ValueError):
            route_chat({"model":"auto","messages":[{"role":"system","content":"Hi"}]},lambda:called.append(1))
        self.assertEqual([],called)
    def test_manual_model_unchanged_without_discovery(self):
        original={"model":"claude-sonnet-4","messages":[{"role":"user","content":"Hi"}]}
        self.assertEqual((original,None),route_chat(original,lambda:1/0))
    def test_missing_cli_fails_closed(self):
        with patch("copilot_auto.shutil.which",return_value=None):
            with self.assertRaises(RuntimeError):
                available_models()
if __name__=="__main__":unittest.main()
