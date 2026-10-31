import sys
from pathlib import Path
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from copilot_chat import validate,copilot_chat

class CopilotChatTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual("gpt-5.4",validate({"model":"gpt-5.4","messages":[{"role":"user","content":"Hello"}]})[0])
    def test_bad_model(self):
        with self.assertRaises(ValueError):
            validate({"model":"a;rm -rf /","messages":[{"role":"user","content":"Hi"}]})
    def test_bad_role(self):
        with self.assertRaises(ValueError):
            validate({"model":"test","messages":[{"role":"system","content":"Hi"}]})
    def test_oversized(self):
        with self.assertRaises(ValueError):
            validate({"model":"test","messages":[{"role":"user","content":"x"*3001}]})
    def test_no_execution_without_cli(self):
        with patch("copilot_chat.shutil.which",return_value=None):
            with self.assertRaises(RuntimeError):
                copilot_chat({"model":"test","messages":[{"role":"user","content":"Hi"}]})
if __name__=="__main__": unittest.main()
