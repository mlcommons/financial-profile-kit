#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Follows the redaction procedure in DISCLOSURE.md, step by step, on both worked examples, with the command-line tools
exactly as documented, and checks that the result is a conformant, re-signed Profile.

  python3 conformance/test_redaction.py
"""
import json, os, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent; KIT = HERE.parent
TOOL = [sys.executable, str(HERE / "arp_conform.py")]
OWNER_KEY = str(KIT / "examples" / "demo-keys" / "DEMO-ONLY-owner.key")
passed = failed = 0


def ok(name, cond, detail=""):
    global passed, failed
    passed += bool(cond); failed += not cond
    print(("pass  " if cond else "FAIL  ") + name + (f": {detail}" if detail and not cond else ""))


def run(*args, cwd):
    cp = subprocess.run(TOOL + list(args), capture_output=True, text=True, cwd=cwd)
    return cp.returncode, cp.stdout + cp.stderr


def redact(p):
    """Step 1 of DISCLOSURE.md 'Making a redacted version': replace a verbatim quotation and an evidence path."""
    for v in p["provenance"].values():
        for c in v.get("citations") or []:
            if c.get("verbatim"):
                c["verbatim"] = "[redacted]"; break
        else:
            continue
        break
    p["evidence"][0]["path"] = "[redacted]/" + Path(p["evidence"][0]["path"]).name
    p["status"]["limitations"].append("Redacted: one verbatim quotation and the folder of one evidence path.")
    return p


for ex in ("l1-aml-alert-triage.issued.json", "l2-open-banking.json"):
    with tempfile.TemporaryDirectory(prefix="arp redaction ") as d:
        d = Path(d); src = json.loads((KIT / "examples" / ex).read_text(encoding="utf-8"))
        owner = src["issuance"]["owner"]["name"]
        (d / "original.json").write_text(json.dumps(src, indent=2, ensure_ascii=False), encoding="utf-8")
        # Why the signatures must be removed first: editing the signed file leaves stale signatures (ARP-091)
        (d / "edited-in-place.json").write_text(json.dumps(redact(json.loads(json.dumps(src))), indent=2), encoding="utf-8")
        rc, out = run("check", "edited-in-place.json", cwd=d)
        ok(f"{ex}: editing the signed Profile in place is reported (stale signature, ARP-091)", rc == 1 and "ARP-091" in out, out)
        # Step 1: start the derivative
        rc, out = run("redact-prepare", "original.json", "--out", "redacted.json", cwd=d)
        ok(f"{ex}: redact-prepare writes an unsigned draft and an internal link", rc == 0 and (d / "redacted.json").exists() and (d / "redacted.json.internal-link.txt").exists(), out)
        r = json.loads((d / "redacted.json").read_text(encoding="utf-8"))
        rc_h, h = run("hash", "original.json", cwd=d)
        ok(f"{ex}: the derivative has no signatures, a new id, and the original hash is kept outside it",
           r["signatures"] == [] and r["stage"] == "draft" and r["profile_id"] == src["profile_id"] + "-redacted-1"
           and h.strip() in (d / "redacted.json.internal-link.txt").read_text() and h.strip() not in (d / "redacted.json").read_text())
        # Step 2: redact
        (d / "redacted.json").write_text(json.dumps(redact(r), indent=2, ensure_ascii=False), encoding="utf-8")
        # Step 3: evidence paths changed, so a signed evidence manifest must be signed again (ARP-019)
        if r.get("evidence_manifest"):
            rc, out = run("check", "redacted.json", cwd=d)
            ok(f"{ex}: a changed evidence path breaks the signed evidence manifest until it is signed again (ARP-019)", rc == 1 and "ARP-019" in out, out)
            rc, out = run("sign-manifest", "redacted.json", "--signer", r["evidence_manifest"]["signer"], "--key", OWNER_KEY, "--in-place", cwd=d)
            ok(f"{ex}: sign-manifest re-signs the evidence manifest", rc == 0, out)
        # Step 4: check the draft
        rc, out = run("check", "redacted.json", cwd=d)
        ok(f"{ex}: the redacted draft conforms", rc == 0, out)
        # Step 5: the named owner signs it again (another name is refused)
        rc, out = run("sign", "redacted.json", "--role", "owner", "--name", "Someone Else (fictional)", "--key", OWNER_KEY, "--out", "wrong.json", cwd=d)
        ok(f"{ex}: signing under another name is refused", rc == 1 and not (d / "wrong.json").exists(), out)
        rc, out = run("sign", "redacted.json", "--role", "owner", "--name", owner, "--key", OWNER_KEY, "--out", "redacted.issued.json", cwd=d)
        ok(f"{ex}: the named owner signs the redacted Profile", rc == 0, out)
        # Step 6: the result conforms; the original is unchanged
        rc, out = run("check", "redacted.issued.json", cwd=d)
        ok(f"{ex}: the redacted, re-signed Profile conforms", rc == 0 and "CONFORMANT" in out, out)
        rc, out = run("check", "original.json", cwd=d)
        ok(f"{ex}: the original still conforms", rc == 0, out)

print(f"{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
