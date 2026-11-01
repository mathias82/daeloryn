"""Execute allowlisted container tests using only operator-registered checkouts.

The client provides a repository identifier, never a filesystem path.
"""
from authenticated_container_tests import run_approved_tests
from reliable_container_tests import run as container_run

def run_registered_tests(authorization,authenticator,repository,registry,suite,
                         digest,approval_token,approval_gate,*,receipt_path=None,
                         test_runner=container_run):
 # The registry is an operator-owned object, not constructed from HTTP payloads.
 checkout=registry.resolve(repository)
 return run_approved_tests(authorization,authenticator,repository,checkout,suite,
                           digest,approval_token,approval_gate,
                           receipt_path=receipt_path,test_runner=test_runner)
