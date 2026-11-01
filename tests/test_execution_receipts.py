import json
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from execution_receipts import append_receipt

class ReceiptTests(unittest.TestCase):
 def test_private_append_and_valid_json_lines(self):
  with TemporaryDirectory() as d:
   path=Path(d)/"receipts.jsonl"
   for outcome in ("started","succeeded"):
    append_receipt(path,subject="dev",repository="repo",action="run_tests",digest="a"*64,outcome=outcome)
   self.assertEqual(["started","succeeded"],[json.loads(line)["outcome"] for line in path.read_text().splitlines()])
   self.assertEqual(0,os.stat(path).st_mode & 0o077)
 def test_symlink_rejected(self):
  with TemporaryDirectory() as d:
   target=Path(d)/"target"
   target.write_text("")
   link=Path(d)/"link"
   link.symlink_to(target)
   with self.assertRaises(ValueError):
    append_receipt(link,subject="dev",repository="repo",action="run_tests",digest="a"*64,outcome="started")
if __name__=="__main__":unittest.main()
