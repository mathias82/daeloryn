import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from reliable_container_tests import run

class TestRunner(unittest.TestCase):
 def test_rejects_unapproved(self):
  with self.assertRaises(PermissionError):run("/missing","maven")
 def test_isolated_workspace_and_no_network(self):
  with TemporaryDirectory() as tmp:
   root=Path(tmp);(root/".git").mkdir()
   mock=Mock(return_value=Mock(returncode=0,stdout="ok",stderr=""))
   with patch("reliable_container_tests.shutil.which",return_value="/usr/bin/docker"):
    result=run(root,"gradle",approved=True,runner=mock)
   args=mock.call_args.args[0]
   self.assertIn("--network",args)
   self.assertIn("none",args)
   self.assertIn("/workspace:rw,nosuid,size=1024m",args)
   self.assertTrue(result["verified"])
if __name__=="__main__":unittest.main()
