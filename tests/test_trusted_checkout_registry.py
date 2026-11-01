import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from trusted_checkout_registry import TrustedCheckoutRegistry

class CheckoutRegistryTests(unittest.TestCase):
 def test_only_operator_configured_repository(self):
  with TemporaryDirectory() as d:
   root=Path(d)/"repo"
   (root/".git").mkdir(parents=True)
   registry=TrustedCheckoutRegistry({"org/repo":root})
   self.assertEqual(root,registry.resolve("org/repo"))
   with self.assertRaises(PermissionError):registry.resolve("../repo")
   with self.assertRaises(PermissionError):registry.resolve("org/other")
 def test_symlink_checkout_rejected(self):
  with TemporaryDirectory() as d:
   root=Path(d)/"repo"
   (root/".git").mkdir(parents=True)
   link=Path(d)/"link"
   link.symlink_to(root,target_is_directory=True)
   with self.assertRaises(ValueError):TrustedCheckoutRegistry({"repo":link})
if __name__=="__main__":unittest.main()
