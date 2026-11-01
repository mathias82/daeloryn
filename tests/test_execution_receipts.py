import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from execution_receipts import append_receipt

class ReceiptTests(unittest.TestCase):
 def test_existing_public_file_rejected_without_writing(self):
  with TemporaryDirectory() as d:
   path=Path(d)/"receipts.jsonl"
   path.write_text("original",encoding="utf-8")
   if os.name=="nt":
    subprocess.run(["icacls",str(path),"/grant","*S-1-1-0:(F)"],
                   capture_output=True,check=True)
   else:
    path.chmod(0o644)
   with self.assertRaises(PermissionError):
    append_receipt(path,subject="dev",repository="repo",action="run_tests",digest="a"*64,outcome="started")
   self.assertEqual("original",path.read_text(encoding="utf-8"))
 def test_private_append_and_valid_json_lines(self):
  with TemporaryDirectory() as d:
   path=Path(d)/"receipts.jsonl"
   for outcome in ("started","succeeded"):
    append_receipt(path,subject="dev",repository="repo",action="run_tests",digest="a"*64,outcome=outcome)
   self.assertEqual(["started","succeeded"],[json.loads(line)["outcome"] for line in path.read_text().splitlines()])
   if os.name=="nt":
    # Reopening verifies the protected DACL on the existing file's handle.
    from windows_private_file import open_private_append
    os.close(open_private_append(path))
   else:
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
