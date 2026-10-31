import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from code_review import review

class ArchitectureInventoryTests(unittest.TestCase):
 def test_java_component_and_framework_hints(self):
  with TemporaryDirectory() as temp:
   root=Path(temp)
   repo=root/"demo"
   repo.mkdir()
   (repo/".git").mkdir()
   (repo/"App.java").write_text("import org.springframework.context.ApplicationContext;\nclass App {}\n")
   result=review(root,"demo","Review architecture")
   architecture=result["architecture"]
   self.assertEqual("App.java",architecture["components"][0]["file"])
   self.assertIn("App",architecture["components"][0]["symbols"])
   self.assertEqual("Spring",architecture["framework_hints"][0]["name"])
   self.assertEqual("not_run",result["execution"])
if __name__=="__main__":unittest.main()
