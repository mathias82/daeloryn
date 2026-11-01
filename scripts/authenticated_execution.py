"""Authenticate a local caller before authorization and single-use execution approval.

No HTTP endpoint, automatic credential issuance, or user-supplied handlers.
"""
from approved_execution_dispatch import dispatch

def authenticated_dispatch(authorization,authenticator,repository,action,digest,
                           approval_token,approval_gate,handler,*,receipt_path=None):
 principal=authenticator.authenticate(authorization)
 return dispatch(principal,repository,action,digest,approval_token,
                 approval_gate,handler,receipt_path=receipt_path)
