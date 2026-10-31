import sys
from pathlib import Path
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from local_chat import chat, installed_models

class LocalChatTests(unittest.TestCase):
    def test_catalog(self):
        with patch("local_chat.fetch_json",return_value={"models":[{"name":"llama3.2:latest"},{"name":"bad name"}]}):
            self.assertEqual(["llama3.2:latest"],installed_models())

    def test_valid_chat_no_tools(self):
        with patch("local_chat.installed_models",return_value=["test:latest"]),patch(
            "local_chat.fetch_json",return_value={"message":{"content":"Hello"}}) as send:
            result=chat({"model":"test:latest","messages":[{"role":"user","content":"Hi"}]})
            self.assertEqual("Hello",result["reply"])
            self.assertFalse(result["tools_executed"])
            payload=send.call_args.args[1]
            self.assertEqual(False,payload["stream"])
            self.assertNotIn("tools",payload)

    def test_reject_unknown_model(self):
        with patch("local_chat.installed_models",return_value=["installed"]):
            with self.assertRaises(ValueError):
                chat({"model":"other","messages":[{"role":"user","content":"Hi"}]})

    def test_reject_system_message(self):
        with patch("local_chat.installed_models",return_value=["test"]):
            with self.assertRaises(ValueError):
                chat({"model":"test","messages":[{"role":"system","content":"unsafe"}]})

    def test_reject_large_prompt(self):
        with patch("local_chat.installed_models",return_value=["test"]):
            with self.assertRaises(ValueError):
                chat({"model":"test","messages":[{"role":"user","content":"x"*4001}]})

if __name__=="__main__":
    unittest.main()
