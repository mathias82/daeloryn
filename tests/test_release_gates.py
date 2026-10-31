import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from check_release_gates import check,REQUIRED

class ReleaseGateTests(unittest.TestCase):
    def test_unverified_gates_block_release(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"gate.json"
            path.write_text(json.dumps({"schema_version":1,"gates":{}}))
            self.assertEqual(set(check(path)),set(REQUIRED))
    def test_all_attestations_required(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"gate.json"
            gates={name:{"passed":True,"evidence_url":"https://example.org/verifiable/"+name} for name in REQUIRED}
            gates["field_pilots"]["passed"]=False
            path.write_text(json.dumps({"schema_version":1,"gates":gates}))
            self.assertEqual(check(path),["field_pilots"])
    def test_complete_records_are_structurally_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"gate.json"
            gates={name:{"passed":True,"evidence_url":"https://example.org/"+name} for name in REQUIRED}
            path.write_text(json.dumps({"schema_version":1,"gates":gates}))
            self.assertEqual(check(path),[])
            # Structural validation does not independently verify attestation claims.
