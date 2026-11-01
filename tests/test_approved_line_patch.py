"""Code changes require explicit per-diff approval, exact SHA and a clean Git branch."""
import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from approved_line_patch import apply_line_patch


class ApprovedLinePatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.repo=self.root/"demo"
        self.repo.mkdir()
        subprocess.run(["git","init","-q",str(self.repo)],check=True)
        subprocess.run(["git","-C",str(self.repo),"config","user.name","CI Test"],check=True)
        subprocess.run(["git","-C",str(self.repo),"config","user.email","test@example.invalid"],check=True)
        self.path="src/main/java/MailConfiguration.java"
        self.file=self.repo/self.path
        self.file.parent.mkdir(parents=True)
        self.original='class MailConfiguration {\n  String state = "before";\n  void run() {}\n}\n'
        self.file.write_text(self.original,encoding="utf-8")
        subprocess.run(["git","-C",str(self.repo),"add","."],check=True)
        subprocess.run(["git","-C",str(self.repo),"commit","-qm","baseline"],check=True)
        self.source_sha=hashlib.sha256(self.original.encode()).hexdigest()
        self.prepared={"repository":"demo","sha256":"a"*64,"scope":"focused","files":[self.path]}
    def apply(self,**kwargs):
        return apply_line_patch(self.root,"demo",self.prepared,"a"*64,self.path,
            kwargs.get("start",2),kwargs.get("end",2),
            kwargs.get("original",'  String state = "before";'),
            kwargs.get("replacement",'  String state = "after";'),
            kwargs.get("sha",self.source_sha),
            kwargs.get("branch","daeloryn/approved-fix"),approved=kwargs.get("approved",True))
    def test_approved_patch_creates_new_branch_and_modifies_only_selected_file(self):
        response=self.apply()
        self.assertEqual("applied",response["status"])
        self.assertEqual("daeloryn/approved-fix",response["branch"])
        self.assertEqual([self.path],response["changed_files"])
        self.assertFalse(response["tests_executed"])
        self.assertEqual(0,response["provider_calls"])
        self.assertEqual(self.original.replace("before","after"),self.file.read_text())
        branch=subprocess.run(["git","-C",str(self.repo),"branch","--show-current"],
            capture_output=True,text=True,check=True).stdout.strip()
        self.assertEqual("daeloryn/approved-fix",branch)
        self.assertEqual(["M src/main/java/MailConfiguration.java"],
            subprocess.run(["git","-C",str(self.repo),"status","--porcelain"],
                           capture_output=True,text=True,check=True).stdout.strip().splitlines())
    def test_no_approval_no_write_no_branch(self):
        with self.assertRaises(PermissionError):
            self.apply(approved=False)
        self.assertEqual(self.original,self.file.read_text())
        self.assertNotIn("daeloryn/approved-fix",subprocess.run(
            ["git","-C",str(self.repo),"branch","--list"],capture_output=True,text=True,check=True).stdout)
    def test_stale_file_and_changed_range_cannot_write(self):
        with self.assertRaises(PermissionError):
            self.apply(sha="0"*64)
        with self.assertRaises(PermissionError):
            self.apply(original="not the exact original source")
        self.assertEqual(self.original,self.file.read_text())
    def test_dirty_worktree_and_invalid_branch_are_refused(self):
        (self.repo/"untracked.txt").write_text("other user work")
        with self.assertRaises(PermissionError):
            self.apply()
        with self.assertRaises(ValueError):
            self.apply(branch="main")
        self.assertEqual(self.original,self.file.read_text())
    def test_sensitive_source_ranges_and_unapproved_path_are_refused(self):
        self.file.write_text('class MailConfiguration {\n  String password = "foo";\n}\n')
        with self.assertRaises(PermissionError):
            self.apply()
        with self.assertRaises(PermissionError):
            apply_line_patch(self.root,"demo",{**self.prepared,"files":["x.java"]},
                "a"*64,self.path,2,2,"x","y",self.source_sha,"daeloryn/fix",approved=True)
    def test_out_of_range_missing_source_and_large_patch_are_refused(self):
        with self.assertRaises(ValueError):
            self.apply(start=99,end=99)
        with self.assertRaises(ValueError):
            self.apply(replacement="x"*13000)
        with self.assertRaises(PermissionError):
            apply_line_patch(self.root,"demo",self.prepared,"0"*64,
                self.path,2,2,'  String state = "before";','  String state = "after";',
                self.source_sha,"daeloryn/fix",approved=True)


if __name__=="__main__":
    unittest.main()
