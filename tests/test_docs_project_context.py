"""Docs-only context cannot include source/configuration even when names match."""
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from approved_copilot_review import prepare, execute
from docs_project_context import snapshot_docs

class DocsOnlySnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.repo=self.root/"demo"
        (self.repo/".git").mkdir(parents=True)
        (self.repo/"docs").mkdir()
        (self.repo/"README.md").write_text("# What this service does\nThis is public documentation.\n")
        (self.repo/"docs"/"architecture.md").write_text("Architecture overview and supported endpoints.\n")
        (self.repo/"App.java").write_text('class App { String sourceCode = "sensitive"; }')
        (self.repo/"pom.xml").write_text("<project>PRIVATE-BUILD</project>")
        (self.repo/"config.yml").write_text("application-secret")
    def test_docs_snapshot_excludes_java_pom_and_config(self):
        s=snapshot_docs(self.root,"demo","Describe project architecture")
        self.assertEqual({"README.md","docs/architecture.md"},{x["path"] for x in s["files"]})
        combined="".join(x["source"] for x in s["files"])
        self.assertNotIn("sourceCode",combined)
        self.assertNotIn("PRIVATE-BUILD",combined)
        self.assertNotIn("application-secret",combined)
        self.assertFalse(s["all_eligible_files_included"])
    def test_docs_review_is_digest_bound_and_requires_approval(self):
        a=prepare(self.root,"demo","Explain the docs","test-model",scope="docs")
        self.assertEqual("docs",a["scope"])
        self.assertNotIn("PRIVATE-BUILD",a["prompt"])
        self.assertNotIn("sourceCode",a["prompt"])
        self.assertIn("README.md",a["files"])
        responses=[]
        def transport(request,**kwargs):
            responses.append(request)
            return {"reply":"The README explains supported behavior."}
        result=execute(a,"test-model",a["sha256"],transport=transport)
        self.assertEqual("completed",result["status"])
        self.assertEqual(a["batch_count"],len(responses))
        with self.assertRaises(PermissionError):
            execute(a,"test-model","bad",transport=lambda *args,**kwargs:self.fail("unauthorized upload"))
    def test_symlinked_documentation_is_not_followed(self):
        outside=Path(self.tmp.name)/"private.txt"
        outside.write_text("EXTERNAL DOCUMENTATION SECRET")
        try:
            (self.repo/"docs"/"external.md").symlink_to(outside)
        except OSError:
            self.skipTest("symlinks unavailable on host")
        s=snapshot_docs(self.root,"demo","external")
        self.assertNotIn("docs/external.md",[x["path"] for x in s["files"]])
        self.assertNotIn("EXTERNAL DOCUMENTATION SECRET","".join(x["source"] for x in s["files"]))

if __name__=="__main__": unittest.main()
