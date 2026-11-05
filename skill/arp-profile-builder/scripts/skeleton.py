#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Emit a Level 1 draft skeleton for the agent to fill in.

  python3 <skill>/scripts/skeleton.py --deployment ID --institution NAME --owner NAME --role ROLE \\
          --evidence <workdir>/evidence.json --run-on "ASSISTANT / MODEL / VERSION" --out <workdir>/skeleton.json

Every value the agent must supply is the string TODO; the checker rejects any that survive (ARP-002).
--run-on records which assistant and model compiled the Profile, in assurance.method, so the run can be
reproduced and compared across model families.
"""
import argparse, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL_VERSION = "0.2"

def spec_id():
    """The specification identifier from the bundled schema (e.g. arp/1.0-rc2)."""
    for p in (HERE.parent / "spec" / "profile.schema.json", HERE.parents[2] / "spec" / "profile.schema.json"):
        if p.exists(): return json.loads(p.read_text(encoding="utf-8"))["properties"]["spec"].get("const", "arp/1.0-rc2")
    return "arp/1.0-rc2"

def _vocab_dir():
    for d in (HERE.parent / "spec" / "vocab", HERE.parents[2] / "spec" / "vocab"):
        if d.exists(): return d
    raise SystemExit("cannot find the spec vocabularies next to the skill")

def vocab_versions():
    out = {}
    for f in sorted(_vocab_dir().glob("*.json")):
        v = json.loads(f.read_text(encoding="utf-8")).get("version")
        if v: out[f.stem] = v
    return out

def default_voids():
    """The preprint §5.3 default triggers (vocab/invalidation-triggers.json), each with a TODO description to fill in."""
    t = json.loads((_vocab_dir() / "invalidation-triggers.json").read_text(encoding="utf-8"))["terms"]
    return [{"trigger": x["id"], "description": "TODO: " + x["meaning"]} for x in t if x.get("default")]

def build(a):
    TODO = "TODO"
    evidence = json.loads(Path(a.evidence).read_text(encoding="utf-8"))
    return {
      "spec": spec_id(), "vocab_versions": vocab_versions(), "profile_id": f"{a.deployment}.L1", "stage": "draft",
      "subject": {"institution": a.institution, "deployment_id": a.deployment, "deployment_version": None, "models": [], "vendor_products": [], "platform_baseline": None},
      "issuance": {"owner": {"name": a.owner, "role": a.role},
                   "issuer": {"name": a.owner, "role": a.role, "organisation": a.institution, "independent": False},
                   "issued_at": None, "valid_from": None, "valid_until": None,
                   "evidence_as_of": TODO},
      "claim": {"statement": TODO,
                "autonomy": {"tier": "U", "tier_basis": "asserted", "modifiers": {"data_authority": TODO, "reversibility_profile": TODO, "customer_market_impact": TODO,
                                                        "stack_composability": "not_assessed", "accountability": TODO, "population_scope": TODO}},
                "odd": {"business_line": TODO, "use_case": TODO},
                "actions": {"permitted": [], "prohibited": []},
                "controls": []},
      "assurance": {"axes": {"autonomy": 1, "odd": 1, "actions": 1, "controls": 1}, "headline": 1,
                    "assessors": {ax: {"role": "institution", "organisation": a.institution} for ax in ("autonomy", "odd", "actions", "controls")},
                    "test_environment": None,
                    "disclosures": ["level1_untested", "not_comparable"],
                    "method": f"arp-profile-builder skill {SKILL_VERSION}; run on {a.run_on}",
                    "comparability": {"flag": False, "environment_version": None, "hidden_set_version": None, "fidelity_statement": None}},
      "provenance": {}, "conflicts": [], "floors": [], "results": [], "benchmark": None,
      "out_of_scope": {"statement": TODO, "actions": []},
      "invalidation": {"voids": default_voids(), "partial_retest": [], "cosmetic": [], "monitoring": TODO},
      "evidence": evidence,
      "status": {"open_findings": [], "accepted_gaps": [], "exceptions": [], "risk_acceptances": [],
                 "limitations": ["Level 1: nothing executed; every claim is as asserted or as configured.", "Not comparable with any other deployment."]},
      "signatures": []}

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for k in ("deployment", "institution", "owner", "role", "evidence"): ap.add_argument(f"--{k}", required=True)
    ap.add_argument("--run-on", required=True, help='the assistant, model and version running the skill, e.g. "ExampleAssistant / example-model / 2026-09-01"')
    ap.add_argument("--out", help="write here instead of standard output (folders are created)")
    a = ap.parse_args()
    text = json.dumps(build(a), indent=2, ensure_ascii=False) + "\n"
    if a.out: Path(a.out).parent.mkdir(parents=True, exist_ok=True); Path(a.out).write_text(text, encoding="utf-8"); print(f"wrote {a.out}", file=sys.stderr)
    else: sys.stdout.write(text)

if __name__ == "__main__":
    main()
