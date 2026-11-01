import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from repository_router import discover,suggest
class RepositoryRouterTests(unittest.TestCase):
 def test_discover_local_git_directory(self):
  with TemporaryDirectory() as tmp:
   root=Path(tmp)
   (root/"payments").mkdir()
   (root/"payments"/".git").mkdir()
   (root/"payments"/"pom.xml").write_text("<project/>")
   (root/"not-a-repo").mkdir()
   rows=discover([root])
   self.assertEqual(["payments"],[r["name"] for r in rows])
   self.assertEqual(["java", "java-maven"],rows[0]["technologies"])
 def test_reject_symlink_root(self):
  with TemporaryDirectory() as tmp:
   root=Path(tmp)
   (root/"link").symlink_to(root,target_is_directory=True)
   with self.assertRaises(ValueError):discover([root/"link"])
 def test_no_roots(self):
  self.assertEqual([],discover([]))
 def test_name_match_requires_confirmation(self):
  rows=[{"name":"payments-service","path":"/tmp/payments","technologies":["java-maven"]}]
  result=suggest("Review payments Java",rows)
  self.assertEqual("payments-service",result["repository"]["name"])
  self.assertTrue(result["requires_confirmation"])
  self.assertEqual("not_run",result["execution"])
 def test_tie_is_not_autoselected(self):
  rows=[{"name":"java-a","technologies":["java-maven"]},{"name":"java-b","technologies":["java-maven"]}]
  self.assertIsNone(suggest("Review Java",rows)["repository"])
 def test_no_match(self):
  self.assertIsNone(suggest("Hello",[])["repository"])
if __name__=="__main__":unittest.main()
