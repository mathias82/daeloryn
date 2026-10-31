import json
import sys
from pathlib import Path
from types import SimpleNamespace
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from github_repository_catalog import list_github_repositories,recommend_github

class GithubRepositoryTests(unittest.TestCase):
 def test_list_filters_archived_and_preserves_private_flag(self):
  data=[{"full_name":"org/payments","private":True,"language":"Java"},
        {"full_name":"org/old","archived":True}]
  calls=[]
  def run(args,**kwargs):
   calls.append((args,kwargs))
   return SimpleNamespace(returncode=0,stdout=json.dumps(data).encode())
  rows=list_github_repositories(executable="/usr/bin/gh",runner=run)
  self.assertEqual(["org/payments"],[r["name"] for r in rows])
  self.assertTrue(rows[0]["private"])
  self.assertEqual(["/usr/bin/gh", "api", "--method", "GET"], calls[0][0][:4])
 def test_failure_does_not_leak_stderr(self):
  def run(*args,**kwargs):
   return SimpleNamespace(returncode=1,stdout=b"",stderr=b"secret")
  with self.assertRaises(RuntimeError) as ctx:
   list_github_repositories(executable="/usr/bin/gh",runner=run)
  self.assertNotIn("secret",str(ctx.exception))
 def test_rejects_invalid_catalog(self):
  def run(*args,**kwargs):
   return SimpleNamespace(returncode=0,stdout=b'{"message":"bad"}')
  with self.assertRaises(RuntimeError):
   list_github_repositories(executable="/usr/bin/gh",runner=run)
 def test_recommend_requires_confirmation(self):
  rows=[{"name":"org/payments","language":"Java","private":True}]
  decision=recommend_github("Review payments Java",rows)
  self.assertEqual("org/payments",decision["repository"]["name"])
  self.assertTrue(decision["requires_confirmation"])
 def test_ambiguous_no_selection(self):
  rows=[{"name":"a/java","language":"Java"},{"name":"b/java","language":"Java"}]
  self.assertIsNone(recommend_github("Java",rows)["repository"])
if __name__=="__main__":unittest.main()
