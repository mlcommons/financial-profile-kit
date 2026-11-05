#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Profile Summary (arp-summary/0.3-draft, for arp/1.0-rc2): derive, sign and check (reference implementation).

Design draft for the gated Profile Exchange; needed only if the Exchange passes its gate. `check` establishes a signed, conformant
submission. It cannot verify derivation from the full Profile, which does not go to the
Exchange; that rests on the owner attestation and sampled verification in the bank.

The Summary is the only artifact the Profile Exchange accepts. It is derived by rule from an
issued, conformant Profile, inside the institution. The full Profile does not go to the Exchange (it may still go to a
supervisor through the inventory feed; see spec/FEED.md).

  python3 arp_summary.py derive PROFILE.json --institution-type large_bank --region eu \\
        --contributor-ref c-xxxxxxxx --salt-file deployment.salt --out SUMMARY.json
  python3 arp_summary.py sign  SUMMARY.json --key owner.key --out SIGNED.json
  python3 arp_summary.py check SUMMARY.json [--json]
"""
import argparse, base64, copy, hashlib, json, sys
from pathlib import Path
from arp_conform import canonical_hash, check as check_profile, load_vocab, loads_strict, InputError, SPEC, AXES, field_dispositions

JUDGED_KINDS = ["unprofiled", "floor_failure", "contradicted_claim", "open_conflict", "configuration_finding", "gap", "other"]
PROV = ["absent", "owner_attested", "document_derived", "configuration_derived", "measured"]


class Refused(Exception):
    pass


def derive(p: dict, institution_type: str, region: str, contributor_ref: str, salt: bytes) -> dict:
    # SUM-011: only an issued, conformant Profile may be summarized
    errs = check_profile(p).errors
    if errs:
        raise Refused("source Profile is not conformant: " + "; ".join(f"{e['rule']} {e['message']}" for e in errs[:5]))
    if p["stage"] != "issued":
        raise Refused("only an issued Profile may be summarized")
    c, a = p["claim"], p["assurance"]
    uc = c["odd"].get("use_case_id")
    ids = {t["id"] for t in load_vocab("use-cases")["terms"]}
    if uc not in ids:
        raise Refused(f"use_case_id {uc!r} is missing or an extension; the Exchange only aggregates catalogued use cases (vocab/use-cases.json)")
    peer_set = load_vocab("peer-control-set")["terms"]
    ph = canonical_hash(p)
    res = {k: v["disposition"] for k, v in field_dispositions(p.get("results", [])).items()}  # SPEC §4: most severe result per field
    def status(cid):
        ctl = next((x for x in c["controls"] if x["control_id"] == cid), None)
        if ctl is None: return "not_declared"
        if ctl.get("applicable") is False: return "not_applicable"
        if ctl["present"] is False: return "absent"
        if ctl["present"] is None: return "not_established"
        d = res.get(f"controls.{cid}")
        if d: return "tested_held" if d == "held" else "tested_other"
        cls = p["provenance"].get(f"controls.{cid}", {}).get("class")
        return "configured" if cls in ("configuration_derived", "measured") else "asserted"
    aq = c["autonomy"].get("approval_quality")
    s = {
        "spec": "arp-summary/0.3-draft",
        "summary_id": "sum-" + hashlib.sha256((ph + contributor_ref).encode()).hexdigest()[:16],
        "profile_hash": ph,
        "profile_spec": p["spec"],
        "contributor_ref": contributor_ref,
        "deployment_ref": "d-" + hashlib.sha256(salt + p["subject"]["deployment_id"].encode()).hexdigest()[:16],
        "segment": {"institution_type": institution_type, "region": region},
        "dates": {"evidence_as_of_month": p["issuance"]["evidence_as_of"][:7],
                  "issued_month": p["issuance"]["issued_at"][:7],
                  "valid_until_month": (p["issuance"].get("valid_until") or "")[:7] or None},
        "claim": {
            "tier": c["autonomy"]["tier"], "tier_basis": c["autonomy"]["tier_basis"],
            "approval_quality": aq["assessment"] if aq else "none_recorded",
            "business_line": c["odd"]["business_line"], "use_case_id": uc,
            "actions": {"permitted": sorted(c["actions"]["permitted"], key=lambda x: int(x[1:])),
                        "prohibited": sorted(c["actions"]["prohibited"], key=lambda x: int(x[1:]))},
            "peer_controls": {cid: status(cid) for cid in peer_set},
            "platform_anchored": bool(p["subject"].get("platform_baseline")),
        },
        "assurance": {"axes": a["axes"], "headline": a["headline"], "assessor_roles": {ax: a["assessors"][ax]["role"] for ax in AXES},
                      "comparability_flag": a["comparability"]["flag"], "disclosures": sorted(a["disclosures"])},
        "derivation": {"tool": "arp_summary.py (reference implementation)", "tool_version": "0.3",
                       "owner_attestation": "I attest that this Summary was derived by the named tool, without alteration, from the issued Profile identified by profile_hash."},
        "signatures": [],
    }
    if a.get("coverage"):
        s["assurance"]["coverage"] = a["coverage"]
    return s


def summary_hash(s: dict) -> str:
    return canonical_hash(s)  # signatures excluded, as for Profiles


def sign(s: dict, key_path: str) -> dict:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    k = Ed25519PrivateKey.from_private_bytes(Path(key_path).read_bytes())
    out = copy.deepcopy(s); h = summary_hash(out)
    out["signatures"] = [{"role": "owner", "alg": "ed25519",
                          "public_key": base64.b64encode(k.public_key().public_bytes_raw()).decode(),
                          "signed_hash": h, "value": base64.b64encode(k.sign(h.encode())).decode()}]
    return out


def check(s: dict) -> list:
    import jsonschema
    out = []
    schema = json.loads((SPEC / "profile-summary.schema.json").read_text(encoding="utf-8"))
    schema.pop("$id", None)  # local refs only; older jsonschema cannot resolve them against a urn: base
    for e in jsonschema.Draft7Validator(schema).iter_errors(s):
        out.append(("SUM-001", "/".join(map(str, e.path)), e.message))
    if out:
        return out
    c, a = s["claim"], s["assurance"]
    # SUM-010 levels and disclosures are consistent
    if a["headline"] != min(a["axes"].values()):
        out.append(("SUM-010", "assurance/headline", "headline is not the minimum of the axis levels"))
    lv = set(a["axes"].values()); need = {"not_comparable"}
    if 1 in lv: need.add("level1_untested")
    if 2 in lv: need.add("self_tested")
    if 3 in lv: need.add("independently_verified")
    if a["comparability_flag"]: need.add("benchmark_not_production")
    for ax in AXES:
        if (a["axes"][ax] == 3) != (a["assessor_roles"][ax] == "independent_assessor"):
            out.append(("SUM-010", f"assurance/assessor_roles/{ax}", "Level 3 if and only if an independent assessor stands behind the axis"))
    if need != set(a["disclosures"]):
        out.append(("SUM-010", "assurance/disclosures", f"disclosures should be {sorted(need)}"))
    # SUM-012 exactly the peer control set; SUM-013 catalogued use case; SUM-014 disjoint action sets
    peer_set = set(load_vocab("peer-control-set")["terms"])
    if set(c["peer_controls"]) != peer_set:
        out.append(("SUM-012", "claim/peer_controls", f"must report exactly the peer control set: missing {sorted(peer_set - set(c['peer_controls']))}, extra {sorted(set(c['peer_controls']) - peer_set)}"))
    uc = {t["id"]: t["business_line"] for t in load_vocab("use-cases")["terms"]}
    if c["use_case_id"] not in uc:
        out.append(("SUM-013", "claim/use_case_id", f"{c['use_case_id']} is not in vocab/use-cases.json"))
    if set(c["actions"]["permitted"]) & set(c["actions"]["prohibited"]):
        out.append(("SUM-014", "claim/actions", "an action class is both permitted and prohibited"))
    # SUM-020 signature covers this summary and verifies (fails closed)
    h = summary_hash(s)
    for i, g in enumerate(s["signatures"]):
        if g["signed_hash"] != h:
            out.append(("SUM-020", f"signatures/{i}", "signature does not cover this summary"))
            continue
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
            Ed25519PublicKey.from_public_bytes(base64.b64decode(g["public_key"])).verify(base64.b64decode(g["value"]), h.encode())
        except ImportError:
            out.append(("SUM-020", f"signatures/{i}", "cannot verify signatures: no verdict"))
        except Exception:
            out.append(("SUM-020", f"signatures/{i}", "signature does not verify"))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("derive"); d.add_argument("profile"); d.add_argument("--institution-type", required=True)
    d.add_argument("--region", required=True); d.add_argument("--contributor-ref", required=True)
    d.add_argument("--salt-file", required=True); d.add_argument("--out", required=True)
    g = sub.add_parser("sign"); g.add_argument("summary"); g.add_argument("--key", required=True)
    go = g.add_mutually_exclusive_group(required=True); go.add_argument("--out"); go.add_argument("--in-place", action="store_true")
    k = sub.add_parser("check"); k.add_argument("summary"); k.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.cmd == "derive":
        try:
            s = derive(loads_strict(Path(a.profile).read_bytes()), a.institution_type, a.region, a.contributor_ref, Path(a.salt_file).read_bytes())
        except (Refused, InputError) as e:
            print(f"refused: {e}", file=sys.stderr); return 1
        Path(a.out).write_text(json.dumps(s, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"); print(f"derived {s['summary_id']} (unsigned)"); return 0
    try:
        s = loads_strict(Path(a.summary).read_bytes())
    except InputError as e:
        print(f"error: {e}", file=sys.stderr); return 1
    if a.cmd == "sign":
        Path(a.summary if a.in_place else a.out).write_text(json.dumps(sign(s, a.key), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"); print("signed"); return 0
    res = check(s)
    if a.json:
        print(json.dumps({"conformant": not res, "findings": [{"rule": r, "path": p, "message": m} for r, p, m in res]}, indent=2))
    else:
        for r, p, m in res: print(f"ERROR   {r:8} {p}: {m}")
        print("SIGNED, CONFORMANT SUBMISSION (derivation not verified)" if not res else f"NOT CONFORMANT ({len(res)} error(s))")
    return 0 if not res else 1


if __name__ == "__main__":
    sys.exit(main())
