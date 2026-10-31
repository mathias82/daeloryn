"""Instruction/adapter integrity only; does not establish LLM compliance."""
import contextlib
import io
from pathlib import Path
import sys
import tempfile
import tomllib
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from agents import catalog, install

MARKER = 'Code impact, invariant and service-contract gates (mandatory)'


class CodeValidationAgentTests(unittest.TestCase):
    def test_all_22_specialties_have_scoped_honest_code_gates(self):
        definitions=catalog()
        self.assertEqual(22,len(definitions))
        checks=set()
        for meta,body in definitions:
            with self.subTest(agent=meta['name']):
                self.assertEqual(1,body.count('## '+MARKER))
                tail=body.split('## '+MARKER)[1]
                for required in ('Semantic impact','Invariant strength','Cross-service compatibility',
                                 'not mutation kills','UNKNOWN','not run','Role-specific code gate:'):
                    self.assertIn(required,tail)
                checks.add(tail.split('**Role-specific code gate:**')[1].strip())
        self.assertEqual(22,len(checks))

    def test_all_88_adapters_preserve_entire_specialty_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(88,install(target,'all','all'))
            for meta,body in catalog():
                name=meta['name']
                tail=body.split('## '+MARKER)[1]
                for filename in (f'.codex/agents/{name}.toml',f'.claude/agents/{name}.md',
                                 f'.github/agents/{name}.agent.md',f'.gemini/agents/{name}.md'):
                    content=(target/filename).read_text()
                    if filename.endswith('.toml'):
                        content=tomllib.loads(content)['developer_instructions']
                    with self.subTest(agent=name,adapter=filename):
                        self.assertIn(tail,content)


if __name__ == '__main__':
    unittest.main()
