"""Explicitly approved repair patch application and isolated test validation.

Local-only library. No AI calls, HTTP mutation endpoints or auto-publication.
"""
from pathlib import Path
from approved_patch_apply import apply as apply_patch
from reliable_container_tests import run as run_tests

def validate_repair(root,repository,path,replacement,patch_sha256,branch,suite,
                    *,approve_apply=False,approve_tests=False,
                    applier=apply_patch,runner=run_tests):
 if approve_apply is not True or approve_tests is not True:
  raise PermissionError("separate patch and test approvals required")
 if not isinstance(patch_sha256,str) or len(patch_sha256)!=64:
  raise ValueError("exact patch SHA-256 required")
 checkout=Path(root).resolve(strict=True)/repository
 applied=applier(root,repository,path,replacement,patch_sha256,branch)
 if applied.get("applied") is not True or applied.get("sha256")!=patch_sha256:
  raise RuntimeError("patch application not verified")
 result=runner(checkout,suite,approved=True)
 return {"patch":applied,"tests":result,
         "verified":result.get("verified") is True and result.get("containerized") is True,
         "pr_created":False,"requires_human_review":True}
