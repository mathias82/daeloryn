"""SQLite-backed one-use local approvals with atomic cross-process consumption.

This module does not authenticate users or expose an execution API.
"""
import hashlib
from contextlib import closing
import hmac
import re
import secrets
import sqlite3
import time
from pathlib import Path

ACTIONS=frozenset(("apply_patch","run_tests","publish_pr"))
DIGEST=re.compile(r"[0-9a-f]{64}\Z")

class DurableApprovalGate:
 def __init__(self,db_path,ttl_seconds=120,clock=time.time):
  self.path=Path(db_path)
  if self.path.is_symlink():raise ValueError("symlink approval database")
  if not isinstance(ttl_seconds,(int,float)) or isinstance(ttl_seconds,bool) or not 0<ttl_seconds<=3600:
   raise ValueError("invalid TTL")
  self.ttl=ttl_seconds
  self.clock=clock
  with closing(self._connect()) as db:
   db.execute("CREATE TABLE IF NOT EXISTS approvals (token_hash TEXT PRIMARY KEY, action TEXT NOT NULL, repository TEXT NOT NULL, digest TEXT NOT NULL, expires REAL NOT NULL)")
 def _connect(self):
  if self.path.is_symlink():raise ValueError("symlink approval database")
  db=sqlite3.connect(self.path,timeout=10,isolation_level=None)
  db.execute("PRAGMA busy_timeout=10000")
  return db
 @staticmethod
 def _subject(action,repository,digest):
  if action not in ACTIONS or not isinstance(repository,str) or not 1<=len(repository)<=256 or not DIGEST.fullmatch(digest if isinstance(digest,str) else ""):
   raise ValueError("invalid approval subject")
 def prepare(self,action,repository,digest):
  self._subject(action,repository,digest)
  token=secrets.token_urlsafe(32)
  key=hashlib.sha256(token.encode()).hexdigest()
  with closing(self._connect()) as db:
   db.execute("BEGIN IMMEDIATE")
   db.execute("DELETE FROM approvals WHERE expires < ?",(self.clock(),))
   db.execute("INSERT INTO approvals VALUES (?,?,?,?,?)",(key,action,repository,digest,self.clock()+self.ttl))
   db.commit()
  return token
 def consume(self,token,action,repository,digest):
  self._subject(action,repository,digest)
  if not isinstance(token,str) or not 1<=len(token)<=256:
   raise PermissionError("invalid token")
  key=hashlib.sha256(token.encode()).hexdigest()
  with closing(self._connect()) as db:
   db.execute("BEGIN IMMEDIATE")
   record=db.execute("SELECT action,repository,digest,expires FROM approvals WHERE token_hash=?",(key,)).fetchone()
   db.execute("DELETE FROM approvals WHERE token_hash=?",(key,))
   db.commit()
  if record is None or record[3]<self.clock() or not all(hmac.compare_digest(a,b) for a,b in zip(record[:3],(action,repository,digest))):
   raise PermissionError("approval absent, expired or mismatched")
  return True
