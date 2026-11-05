#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Checks that the feed schemas stay in step: the Profile Lite record embedded in inventory.schema.json is identical to
spec/profile-lite.schema.json, and the peer-control fields use vocab/peer-control-set.json and vocab/peer-control-status.json.
  python3 regulator/test_schemas.py
"""
import json, sys
from pathlib import Path
SPEC = Path(__file__).resolve().parent.parent / "spec"
rd = lambda p: json.loads((SPEC / p).read_text(encoding="utf-8"))
lite, inv = rd("profile-lite.schema.json"), rd("inventory.schema.json")
ids = [t["id"] for t in rd("vocab/peer-control-status.json")["terms"]]; peer = rd("vocab/peer-control-set.json")["terms"]
ctl = lite["properties"]["controls"]
tests = [
    ("inventory.schema.json embeds profile-lite.schema.json unchanged",
     inv["definitions"]["lite_record"] == {k: v for k, v in lite.items() if k not in ("$schema", "$id")}),
    ("Lite controls are exactly the peer control set", sorted(ctl["required"]) == sorted(peer) and sorted(ctl["properties"]) == sorted(peer)),
    ("every control status enum equals vocab/peer-control-status.json", all(v.get("enum") == ids for v in ctl["properties"].values())),
    ("snapshots carry institution signatures only (receipts are separate documents)",
     inv["properties"]["signatures"]["items"]["properties"]["role"].get("const") == "institution"),
]
bad = 0
for name, ok in tests:
    print(("pass  " if ok else "FAIL  ") + name); bad += not ok
print(f"{len(tests) - bad} passed, {bad} failed"); sys.exit(1 if bad else 0)
