"""Manifest-only project fingerprint tests, without provider calls or source scanning."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from project_stack import detect_technologies
from repository_router import discover


class ProjectStackTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.project=self.root/'example'
        self.project.mkdir()
        (self.project/'.git').mkdir()

    def test_java_only_never_assumes_spring(self):
        (self.project/'pom.xml').write_text('<project><modelVersion>4.0.0</modelVersion></project>')
        tags=detect_technologies(self.project)
        self.assertIn('java',tags)
        self.assertIn('java-maven',tags)
        self.assertNotIn('spring',tags)
        self.assertNotIn('react',tags)
        row=discover([self.root])[0]
        self.assertEqual(tags,row['technologies'])

    def test_spring_boot_and_nested_react_are_both_detected(self):
        (self.project/'pom.xml').write_text(
            '<project><parent><artifactId>spring-boot-starter-parent</artifactId></parent></project>')
        client=self.project/'frontend'
        client.mkdir()
        (client/'package.json').write_text(
            '{"dependencies":{"react":"^19.0.0","react-dom":"^19.0.0"},'
            '"devDependencies":{"typescript":"^5.0.0"}}')
        (self.project/'Dockerfile').write_text('FROM scratch')
        tags=detect_technologies(self.project)
        for key in ('java','spring','node','react','typescript','docker'):
            self.assertIn(key,tags)

    def test_node_without_react_never_selects_react_agents(self):
        (self.project/'package.json').write_text(
            '{"dependencies":{"express":"^5.0.0"}}')
        tags=detect_technologies(self.project)
        self.assertIn('node',tags)
        self.assertNotIn('react',tags)

    def test_symlinked_manifest_cannot_fake_a_framework(self):
        outside=self.root/'outside.json'
        outside.write_text('{"dependencies":{"react":"*"}}')
        try:
            (self.project/'package.json').symlink_to(outside)
        except OSError:
            self.skipTest('symlinks unavailable')
        self.assertNotIn('react',detect_technologies(self.project))

    def test_malformed_or_oversized_manifest_fails_closed(self):
        (self.project/'package.json').write_text('{not valid json')
        self.assertNotIn('react',detect_technologies(self.project))
        (self.project/'package.json').write_text('{"dependencies":{"react":"*"}}'+(' '*70000))
        self.assertNotIn('react',detect_technologies(self.project))

if __name__=="__main__":
    unittest.main()
