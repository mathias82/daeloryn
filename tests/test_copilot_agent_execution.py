"""Exercise the real CLI launcher with a local fake CLI; no remote inference."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from copilot_agents import resolve_agent
from copilot_chat import copilot_chat, validate
from copilot_auto import route_chat
from approved_copilot_review import prepare, execute

MODEL = "claude-sonnet-4"


def request(agent="java-reviewer"):
    return {"model": MODEL, "agent": agent,
            "messages": [{"role": "user", "content": "Review Java concurrency"}]}


class CopilotAgentExecutionTests(unittest.TestCase):
    def test_unknown_or_path_agent_rejected_before_process(self):
        for agent in ("../java-reviewer", "--allow-all", "unknown-agent", None, 42):
            with self.subTest(agent=agent), patch("copilot_chat.subprocess.Popen") as process:
                with self.assertRaises(ValueError):
                    copilot_chat(request(agent))
                process.assert_not_called()

    def test_auto_model_preserves_agent(self):
        original = request()
        original["model"] = "auto"
        routed, _ = route_chat(original, lambda: [MODEL, "claude-haiku-4"])
        self.assertEqual(MODEL, routed["model"])
        self.assertEqual("java-reviewer", routed["agent"])

    def test_profile_mismatch_never_invokes_cli(self):
        with patch("copilot_chat.subprocess.Popen") as process:
            with self.assertRaises(PermissionError):
                copilot_chat(request(), expected_agent_sha256="0" * 64)
            process.assert_not_called()

    @unittest.skipUnless(os.name == "posix", "POSIX CLI launcher")
    def test_real_subprocess_receives_model_and_staged_exact_agent(self):
        profile = resolve_agent("java-reviewer")
        with tempfile.TemporaryDirectory() as tmp:
            executable = Path(tmp) / "copilot"
            # The subprocess records only fixture data, its args and staged profile.
            executable.write_text("#!" + sys.executable + "\n" + '''
import json, pathlib, sys
args = sys.argv[1:]
agent = args[args.index('--agent') + 1]
root = pathlib.Path.cwd()
path = root / '.github' / 'agents' / (agent + '.agent.md')
print(json.dumps({'args': args, 'profile': path.read_text(), 'cwd': str(root),
                  'files': sorted(str(p.relative_to(root)) for p in root.rglob('*') if p.is_file())}))
''')
            executable.chmod(0o700)
            result = copilot_chat(request(), executable=str(executable),
                                  expected_agent_sha256=profile["sha256"])
        observed = json.loads(result["reply"])
        args = observed["args"]
        self.assertEqual(MODEL, args[args.index("--model") + 1])
        cli_agent = args[args.index("--agent") + 1]
        self.assertTrue(cli_agent.startswith("daeloryn-"))
        self.assertEqual([".github/agents/" + cli_agent + ".agent.md"], observed["files"])
        self.assertIn("tools: []", observed["profile"])
        self.assertIn(profile["body"], observed["profile"])
        self.assertNotIn("--allow-all", args)
        self.assertNotIn("--add-dir", args)
        self.assertIn("--deny-tool=shell,write,read,url,memory", args)
        self.assertIn("--disable-builtin-mcps", args)
        self.assertIn("--no-custom-instructions", args)
        self.assertFalse(Path(observed["cwd"]).exists())
        self.assertEqual("java-reviewer", result["agent_selected"])
        self.assertEqual(profile["sha256"], result["agent_profile_sha256"])
        self.assertFalse(result["agent_identity_verified"])
        self.assertFalse(result["model_identity_verified"])

    def test_approval_binds_source_repository_model_agent_and_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkout = root / "demo"
            checkout.mkdir()
            (checkout / ".git").mkdir()
            source = checkout / "App.java"
            source.write_text("class App {}")
            prepared = prepare(root, "demo", "Review Java", MODEL, "java-reviewer")
            calls = []
            def transport(payload, **kwargs):
                calls.append((payload, kwargs))
                return {"reply": "fixture review"}
            result = execute(prepared, MODEL, prepared["sha256"], transport=transport)
            self.assertEqual("java-reviewer", calls[0][0]["agent"])
            self.assertEqual(MODEL, calls[0][0]["model"])
            self.assertEqual(prepared["agent_profile_sha256"], calls[0][1]["expected_agent_sha256"])
            self.assertFalse(result["patch_applied"])
            for field, value in (("model", "other"), ("agent", "java-developer"),
                                 ("agent_profile_sha256", "0" * 64), ("repository", "other")):
                with self.subTest(field=field), self.assertRaises(PermissionError):
                    execute({**prepared, field: value}, MODEL, prepared["sha256"], transport=transport)
            source.write_text("class Changed {}")
            changed = prepare(root, "demo", "Review Java", MODEL, "java-reviewer")
            with self.assertRaises(PermissionError):
                execute(changed, MODEL, prepared["sha256"], transport=transport)
            self.assertEqual(1, len(calls))
            with self.assertRaises(ValueError):
                prepare(root, "demo", "Review", "auto", "java-reviewer")

    def test_profile_changes_invalidate_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "demo" / ".git").mkdir(parents=True)
            (root / "demo" / "App.java").write_text("class App {}")
            prepared = prepare(root, "demo", "Review", MODEL, "java-reviewer")
            changed = {**resolve_agent("java-reviewer"), "sha256": "1" * 64}
            with patch("approved_copilot_review.resolve_agent", return_value=changed):
                with self.assertRaises(PermissionError):
                    execute(prepared, MODEL, prepared["sha256"], transport=lambda _: self.fail("called"))


if __name__ == "__main__":
    unittest.main()
