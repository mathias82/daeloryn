import sys
import unittest
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from reliable_container_tests import run,ContainerTestTimeout

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
   self.assertIn("/workspace:rw,nosuid,size=1024m,mode=1777",args)
   self.assertTrue(result["verified"])
 def test_timeout_removes_only_owned_container(self):
  with TemporaryDirectory() as tmp:
   root=Path(tmp);(root/".git").mkdir()
   runner=Mock(side_effect=subprocess.TimeoutExpired("docker",1))
   with patch("reliable_container_tests.shutil.which",return_value="docker"):
    with patch("reliable_container_tests.subprocess.run",return_value=Mock(returncode=0)) as cleanup:
     with self.assertRaises(ContainerTestTimeout) as caught:run(root,"python",approved=True,timeout=1,runner=runner)
   name=runner.call_args.args[0][runner.call_args.args[0].index("--name")+1]
   self.assertTrue(caught.exception.cleanup_verified)
   self.assertEqual(["docker","rm","--force",name],cleanup.call_args.args[0])
 def test_failed_cleanup_is_never_reported_verified(self):
  with TemporaryDirectory() as tmp:
   root=Path(tmp);(root/".git").mkdir()
   for error in (Mock(returncode=1),subprocess.TimeoutExpired("cleanup",20)):
    with self.subTest(error=type(error).__name__):
     with patch("reliable_container_tests.shutil.which",return_value="docker"):
      with patch("reliable_container_tests.subprocess.run") as cleanup:
       if isinstance(error,Exception):cleanup.side_effect=error
       else:cleanup.return_value=error
       with self.assertRaises(ContainerTestTimeout) as caught:
        run(root,"python",approved=True,timeout=1,runner=Mock(side_effect=subprocess.TimeoutExpired("docker",1)))
     self.assertFalse(caught.exception.cleanup_verified)
if __name__=="__main__":unittest.main()
