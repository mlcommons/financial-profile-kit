#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run the arp/1.0-rc2 conformance vectors.

  python3 run_suite.py                                            # test the reference checker (arp_conform.py)
  python3 run_suite.py --impl "mytool check {file}"               # test another implementation by exit code
  python3 run_suite.py --impl "mytool check {file} --json" --json # ... and by rule id
  python3 run_suite.py --impl-hash "mytool hash {file}"           # ... and its canonical hash (RFC 8785)

An implementation conforms when it accepts every valid vector and rejects every invalid
one; with --json it must also name the expected rule ids in `findings[].rule` (errors only);
with --impl-hash it must print each parsable vector's canonical hash.
Exit codes expected from an implementation: 0 conformant, 1 not conformant.
"""
import argparse, json, shlex, subprocess, sys
from pathlib import Path
from arp_conform import check_bytes, canonical_hash

HERE = Path(__file__).resolve().parent


def run(cmd, f):
    return subprocess.run([t.format(file=str(f)) for t in shlex.split(cmd)], capture_output=True, text=True, cwd=HERE)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--impl"); ap.add_argument("--json", action="store_true"); ap.add_argument("--impl-hash")
    a = ap.parse_args()
    m = json.loads((HERE / "vectors" / "manifest.json").read_text(encoding="utf-8"))
    fails = 0
    for v in m["vectors"]:
        f = HERE / "vectors" / v["file"]
        if a.impl:
            cp = run(a.impl, f)
            ok = cp.returncode in (0, 1) and (cp.returncode == 0) == (v["expect"] == "pass")
            got = set()
            if a.json:
                try: got = {i["rule"] for i in json.loads(cp.stdout)["findings"] if i.get("severity", "error") == "error"}
                except Exception: got = {"<unparseable>"}
                ok = ok and got == set(v["error_rules"])
        else:
            p, rep = check_bytes(f.read_bytes())
            got = {e["rule"] for e in rep.errors}
            ok = got == set(v["error_rules"]) and (not rep.errors) == (v["expect"] == "pass")
            if v.get("canonical_hash") and p is not None:
                ok = ok and canonical_hash(p) == v["canonical_hash"]
        if a.impl_hash and v.get("canonical_hash"):
            ok = ok and run(a.impl_hash, f).stdout.strip() == v["canonical_hash"]
        fails += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {v['file']:52} expect={v['expect']:4} rules={','.join(v['error_rules']) or '-':16} got={','.join(sorted(got)) or '-'}")
    print(f"\n{len(m['vectors']) - fails}/{len(m['vectors'])} vectors behave as specified")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
