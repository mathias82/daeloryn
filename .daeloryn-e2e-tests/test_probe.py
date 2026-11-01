import errno
import os
import socket
import unittest
from pathlib import Path

class ContainerProbe(unittest.TestCase):
 def test_isolation_and_writable_workspace(self):
  self.assertEqual(65534,os.getuid())
  self.assertNotIn("GH_TOKEN",os.environ)
  Path("scratch.txt").write_text("container-only")
  with self.assertRaises(OSError):Path("/source/host-write.txt").write_text("forbidden")
  with self.assertRaises(OSError):Path("/rootfs-write.txt").write_text("forbidden")
  self.assertEqual(["lo"],sorted(p.name for p in Path("/sys/class/net").iterdir()))
  with socket.socket() as connection:
   connection.settimeout(0.2)
   with self.assertRaises(OSError) as denied:connection.connect(("198.51.100.1",443))
   self.assertIn(denied.exception.errno,(errno.ENETUNREACH,errno.EHOSTUNREACH,errno.ENETDOWN))
