import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from container_test_runner import run

class ContainerTests(unittest.TestCase):
 def test_requires_approval(self):
  with self.assertRaises(PermissionError):
   run("/missing","python")
 def test_docker_absence_fails_closed(self):
  with TemporaryDirectory() as tmp:
   root=Path(tmp); (root/".git").mkdir()
   with patch("container_test_runner.shutil.which",return_value=None):
    with self.assertRaises(RuntimeError):
     run(root,"python",approved=True)
 def test_command_has_isolation_flags(self):
  with TemporaryDirectory() as tmp:
   root=Path(tmp); (root/".git").mkdir()
   fake=Mock(return_value=Mock(returncode=0,stdout="ok",stderr=""))
   with patch("container_test_runner.shutil.which",return_value="/usr/bin/docker"):
    result=run(root,"python",approved=True,runner=fake)
   args=fake.call_args.args[0]
   self.assertIn("none",args)
   self.assertIn("--read-only",args)
   self.assertIn("--cap-drop",args)
   self.assertIn("readonly"," ".join(args))
   self.assertTrue(result["verified"])
if __name__=="__main__":unittest.main()
