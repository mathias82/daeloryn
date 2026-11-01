"""Safe full-file Code Inspector: approved local source only; no provider calls."""
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from approved_source_view import read_approved_source


class SourceViewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.project=self.root/"demo"
        self.project.mkdir()
        self.source=self.project/"src"/"main"/"java"/"MailConfiguration.java"
        self.source.parent.mkdir(parents=True)
        self.body=("package example;\n"+
                   "public class MailConfiguration {\n"+
                   "  private String template;\n"+
                   "  void configure() {\n"+
                   "    String password = \"PRIVATE\";\n"+
                   "    template = \"ok\";\n"+
                   "  }\n"+
                   "}\n")
        self.source.write_text(self.body,encoding="utf-8")
        self.file="src/main/java/MailConfiguration.java"
        self.prepared={"repository":"demo","sha256":"a"*64,"files":[self.file]}
    def read(self,**kwargs):
        return read_approved_source(self.root,"demo",self.prepared,"a"*64,
                                    kwargs.get("file",self.file))
    def test_returns_entire_class_with_line_numbers_no_model_calls_and_redaction(self):
        data=self.read()
        self.assertEqual(self.file,data["file"])
        self.assertEqual(8,data["line_count"])
        self.assertEqual(8,len(data["lines"]))
        self.assertEqual("public class MailConfiguration {",data["lines"][1])
        self.assertEqual("  void configure() {",data["lines"][3])
        self.assertEqual("[REDACTED]",data["lines"][4])
        self.assertEqual([5],data["redacted_lines"])
        self.assertNotIn("PRIVATE",repr(data))
        self.assertEqual(hashlib.sha256(self.body.encode()).hexdigest(),data["source_sha256"])
        self.assertTrue(data["local_only"])
        self.assertEqual(0,data["model_calls"])
    def test_requires_exact_manifest_consent_and_allowlisted_file(self):
        with self.assertRaises(PermissionError):
            read_approved_source(self.root,"demo",self.prepared,"b"*64,self.file)
        with self.assertRaises(PermissionError):
            self.read(file="pom.xml")
        with self.assertRaises(PermissionError):
            self.read(file="../demo/src/main/java/MailConfiguration.java")
        with self.assertRaises(PermissionError):
            self.read(file="/etc/passwd")
        with self.assertRaises(PermissionError):
            self.read(file="src/main/java/../../secret.txt")
        with self.assertRaises(PermissionError):
            read_approved_source(self.root,"other",self.prepared,"a"*64,self.file)
    def test_symlink_and_oversized_files_are_denied(self):
        other=self.project/"secret.java"
        other.write_text("private credentials")
        link=self.source.parent/"Linked.java"
        try:
            link.symlink_to(other)
        except OSError:
            self.skipTest("Symlinks unsupported on this host")
        included={**self.prepared,"files":[self.file,"src/main/java/Linked.java"]}
        with self.assertRaises(PermissionError):
            read_approved_source(self.root,"demo",included,"a"*64,"src/main/java/Linked.java")
        self.source.write_text("class Oversized {}\n"*40000)
        with self.assertRaises(ValueError):
            self.read()
    def test_missing_or_binary_source_never_falls_back_to_arbitrary_files(self):
        self.source.write_bytes(b"class A\0 binary")
        with self.assertRaises(ValueError):
            self.read()
        self.source.unlink()
        with self.assertRaises(FileNotFoundError):
            self.read()


if __name__=="__main__":
    unittest.main()
