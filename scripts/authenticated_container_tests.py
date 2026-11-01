"""Approved local container test action; no arbitrary commands or HTTP exposure."""
from pathlib import Path
from authenticated_execution import authenticated_dispatch
from reliable_container_tests import run as container_run

def run_approved_tests(authorization,authenticator,repository,checkout,suite,
                       digest,approval_token,approval_gate,*,receipt_path=None,
                       test_runner=container_run):
 if not isinstance(suite,str) or suite not in ("python","maven","gradle","npm"):
  raise ValueError("unsupported test suite")
 root=Path(checkout).resolve(strict=True)
 if not (root/".git").is_dir() or (root/".git").is_symlink():
  raise ValueError("git checkout required")
 # Checkout must be an operator-configured path; repository string is the grant identifier.
 return authenticated_dispatch(
  authorization,authenticator,repository,"run_tests",digest,
  approval_token,approval_gate,
  lambda:test_runner(root,suite,approved=True),
  receipt_path=receipt_path)
