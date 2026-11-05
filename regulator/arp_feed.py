#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""ARP Supervisory Feed (arp-inventory/0.1, draft; part of the arp/1.0-rc2 kit): build, sign, check and compare inventory snapshots.

  python3 arp_feed.py build  LITE.xlsx|.csv|.json --firm-id ID --as-of 2026-09-30 \\
          [--profiles DIR] [--previous PREV.json] [--trigger scheduled] \\
          --key FIRM.key --signer-name "<name>" --signer-role "<role>" --out SNAPSHOT.json
  python3 arp_feed.py check  SNAPSHOT.json --registry REGISTER.json [--previous PREV.json] [--objects DIR]
  python3 arp_feed.py chain  DIR --registry REGISTER.json [--objects DIR] [--json]
  python3 arp_feed.py diff   OLD.json NEW.json
  python3 arp_feed.py hash   FILE.json

check and chain need the supervisor's key register (spec/FEED.md §6, "Creating your firm register").
Without one, a signature proves only that someone holding some key signed: pass --no-register to run
anyway, and every snapshot is reported with an INV-040 "UNVERIFIED SIGNER" warning.

The same snapshot is delivered by pull, push or file: see spec/FEED.md. A snapshot proves who reported
what and when, and that it has not been altered. It does not prove the records are true.

Every checked snapshot is reported as TRUSTED or QUARANTINED (spec/FEED.md §6). Only a trusted snapshot may feed
supervisory views: any error, or a warning other than INV-010, INV-022 or INV-023, quarantines it.

Exit codes: 0 conforms, 1 does not conform, 2 usage error, 3 input could not be read.
"""
import argparse, base64, copy, datetime as dt, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent; KIT = HERE.parent
sys.path.insert(0, str(KIT / "conformance")); sys.path.insert(0, str(KIT / "templates"))
from arp_conform import canonical_hash, canonical_json, make_validator, check as check_profile  # noqa: E402
import arp_lite  # noqa: E402

SCHEMA = json.loads((KIT / "spec" / "inventory.schema.json").read_text(encoding="utf-8"))
_VALIDATOR = None
SNAP_CONTEXT = "arp-inventory/0.1 snapshot signature"

def validator():
    global _VALIDATOR
    if _VALIDATOR is None: _VALIDATOR = make_validator(SCHEMA)
    return _VALIDATOR

def snapshot_statement(sig):
    """What a snapshot signature signs (FEED.md §6): the snapshot hash together with the signer's role, name and key,
    so none of them can be edited after signing. RFC 8785 canonical JSON, UTF-8."""
    return canonical_json({"context": SNAP_CONTEXT, "alg": sig.get("alg", "ed25519"), "role": sig["role"], "name": sig["name"],
                           "public_key": sig["public_key"], "signed_hash": sig["signed_hash"]}).encode("utf-8")
ATTEST = ("This snapshot lists every agent deployment of the institution in development, pilot or production "
          "at the as-of date, and any retired since the previous snapshot, as recorded in its inventory.")

class InputError(Exception): pass

def _no_dupes(pairs):
    d = {}
    for k, v in pairs:
        if k in d: raise InputError(f"duplicate key '{k}' in a JSON object")
        d[k] = v
    return d

def loads(text):
    """Strict JSON for feed documents: duplicate keys and NaN/Infinity are rejected."""
    def bad(c): raise InputError(f"'{c}' is not valid JSON")
    return json.loads(text, object_pairs_hook=_no_dupes, parse_constant=bad)

def _load(p):
    try: return loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError, InputError) as e: raise InputError(f"{p}: {e}")

# INV-023: the Lite fields an inventory record shares with its full Profile (spec/FEED.md §6)
SHARED = ("business_line", "use_case", "use_case_id", "autonomy_tier", "tier_basis", "permitted_actions", "prohibited_actions",
          "models", "accountable_owner_role")
OPTIONAL_SHARED = ("use_case_id", "models")  # compared only when both the record and the Profile state them

def _norm_models(v): return sorted(" ".join(x.split()) for x in str(v).split(",") if x.strip())

def profile_divergence(rec, doc):
    """[(field, record value, Profile value)] where an inventory record disagrees with its full Profile (INV-023).
    The Profile's values are derived exactly as arp_lite.from_profile derives a Lite record."""
    d = arp_lite.from_profile(doc, rec.get("deployment_status"), rec.get("customer_facing"), rec.get("last_reviewed"))
    out = []
    for k in SHARED:
        a, b = rec.get(k), d.get(k)
        if k in OPTIONAL_SHARED and (a is None or b is None): continue
        if k in ("permitted_actions", "prohibited_actions"): same = sorted(a or []) == sorted(b or [])
        elif k == "models": same = _norm_models(a) == _norm_models(b)
        else: same = a == b
        if not same: out.append((k, a, b))
    if (doc.get("claim") or {}).get("autonomy", {}).get("tier") == "T2" and rec.get("human_approval") != "every_material_action":
        out.append(("human_approval", rec.get("human_approval"), "every_material_action"))
    for c in arp_lite.PEER:
        a, b = (rec.get("controls") or {}).get(c), d["controls"].get(c)
        if a != b: out.append((f"controls.{c}", a, b))
    return out

def _fmt(v): return " ".join(v) if isinstance(v, list) else str(v)

def _divergence(r, doc, meta, path, E, W):
    """INV-023 for one record against one full Profile."""
    div = profile_divergence(r, doc)
    note = r.get("divergence")
    if div:
        declared = set((note or {}).get("fields") or [])
        undeclared = [x for x in div if x[0] not in declared]
        if undeclared:
            E("INV-023", f"{path}/record", f"{r['inventory_ref']}: the record differs from its full Profile on {', '.join(x[0] for x in undeclared)} "
              f"({'; '.join(f'{k}: record {_fmt(a)}, Profile {_fmt(b)}' for k, a, b in undeclared[:3])}); derive it from the Profile or declare the divergence with a date and reason")
        else:
            W("INV-023", f"{path}/record", f"{r['inventory_ref']}: declared divergence from the full Profile since {note['as_of']} on {', '.join(x[0] for x in div)}: {note['reason']}")
    if note and note.get("as_of", "") > meta["as_of"]:
        E("INV-023", f"{path}/record/divergence", f"{r['inventory_ref']}: the divergence is dated {note['as_of']}, after the snapshot's as-of date")

# Quarantine (spec/FEED.md §6, "Trusted and quarantined snapshots"): only a verified snapshot may feed supervisory views.
USABLE_WARNINGS = {"INV-010", "INV-022", "INV-023"}  # labelled in the views, but the snapshot stays usable

def trust(findings):
    """(trusted, reasons). Any error, or any warning outside USABLE_WARNINGS (for example an UNVERIFIED SIGNER without a
    key register, or a chain that was not checked), quarantines the snapshot."""
    reasons = [f"{r} {m}" for r, sev, _, m in findings if sev == "error" or r not in USABLE_WARNINGS]
    return (not reasons, reasons)

def profile_ref(p):
    return {"profile_id": p["profile_id"], "stage": p["stage"], "headline": p["assurance"]["headline"],
            "valid_until": p["issuance"].get("valid_until"), "sha256": canonical_hash(p)}

def build(records, firm_id, as_of, previous=None, profiles=None, trigger="scheduled", produced_at=None,
          lei=None, jurisdictions=None, attestation=None, change_note=None):
    names = {r["institution"] for r in records}
    if len(names) != 1: raise SystemExit(f"records name {len(names)} institutions; a snapshot is for one: {sorted(names)}")
    profiles = profiles or {}
    entries = []
    for r in sorted(records, key=lambda r: r["inventory_ref"]):
        e = {"record": r}
        p = profiles.get(r.get("full_profile_ref", ""))
        if p: e["profile"] = profile_ref(p)
        entries.append(e)
    inst = {"name": names.pop(), "firm_id": firm_id}
    if lei: inst["lei"] = lei
    if jurisdictions: inst["jurisdictions"] = jurisdictions
    snap = {"inventory_spec": "arp-inventory/0.1", "institution": inst,
            "snapshot": {"sequence": previous["snapshot"]["sequence"] + 1 if previous else 1, "as_of": as_of,
                         "produced_at": produced_at or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                         "trigger": trigger, "previous_hash": canonical_hash(previous) if previous else None},
            "records": entries, "attestation": attestation or {"name": "<signer>", "role": "<role>", "statement": ATTEST},
            "signatures": []}
    if change_note: snap["snapshot"]["change_note"] = change_note
    return snap

def public_key_b64(key_bytes):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    return base64.b64encode(Ed25519PrivateKey.from_private_bytes(key_bytes).public_key().public_bytes_raw()).decode()

def sign(snap, key_bytes, name):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    key = Ed25519PrivateKey.from_private_bytes(key_bytes)
    out = copy.deepcopy(snap); out["signatures"] = []
    h = canonical_hash(out)
    sig = {"role": "institution", "name": name, "alg": "ed25519",
           "public_key": base64.b64encode(key.public_key().public_bytes_raw()).decode(), "signed_hash": h}
    sig["value"] = base64.b64encode(key.sign(snapshot_statement(sig))).decode()
    out["signatures"].append(sig)
    return out

def _verify(sig):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    try:
        Ed25519PublicKey.from_public_bytes(base64.b64decode(sig["public_key"], validate=True)).verify(
            base64.b64decode(sig["value"], validate=True), snapshot_statement(sig))
        return True
    except Exception:
        return False

def key_allowed(entry, public_key, sequence):
    """The firm's registered key, or a retired key still valid for this sequence (key rotation)."""
    if not isinstance(entry, dict): return False
    if entry.get("public_key") == public_key: return True
    for k in entry.get("retired_keys") or []:
        if isinstance(k, dict) and k.get("public_key") == public_key and isinstance(k.get("last_sequence"), int) and sequence <= k["last_sequence"]:
            return True
    return False

def check(snap, previous=None, objects=None, registry=None):
    """Returns [(rule, severity, path, message)].
    objects: {sha256: Profile}. registry: {firm_id: {public_key, retired_keys?}}; None means no register was supplied."""
    try:
        return _check(snap, previous, objects or {}, registry)
    except Exception as e:  # a malformed document must produce a finding, never a crash
        return [("INV-001", "error", "-", f"could not be checked: {type(e).__name__}: {e}")]

def _check(snap, previous, objects, registry):
    out = []
    E = lambda r, p, m: out.append((r, "error", p, m)); W = lambda r, p, m: out.append((r, "warning", p, m))
    for e in validator().iter_errors(snap):
        E("INV-001", "/".join(map(str, e.path)) or "-", e.message)
    if out: return out
    inst, meta, entries = snap["institution"], snap["snapshot"], snap["records"]
    seen = {}
    for i, e in enumerate(entries):
        r, path = e["record"], f"records/{i}"
        for rule, field, msg in arp_lite.check_record(r):
            if rule == "LITE-001": continue  # covered by INV-001
            (W if "W" in rule else E)("INV-010", f"{path}/record/{field}", f"{r['inventory_ref']}: {rule} {msg}")
        if r["inventory_ref"] in seen: E("INV-011", path, f"{r['inventory_ref']} appears more than once")
        seen[r["inventory_ref"]] = r
        if r["institution"] != inst["name"]: E("INV-012", f"{path}/record/institution", f"{r['inventory_ref']} names '{r['institution']}', not '{inst['name']}'")
        pr = e.get("profile")
        if r["profile_level"] != "none":
            if not pr: E("INV-020", path, f"{r['inventory_ref']} reports a Level {r['profile_level'][1]} Profile but carries no commitment to it")
            elif pr["stage"] != "issued" or f"L{pr['headline']}" != r["profile_level"] or pr["profile_id"] != r.get("full_profile_ref"):
                E("INV-020", f"{path}/profile", f"{r['inventory_ref']}: the committed Profile ({pr['profile_id']}, {pr['stage']}, Level {pr['headline']}) does not match the record ({r.get('full_profile_ref')}, {r['profile_level']})")
        elif pr and pr["stage"] == "issued":
            E("INV-020", f"{path}/profile", f"{r['inventory_ref']} commits to an issued Profile but reports profile_level 'none'")
        if pr:
            valid_until = pr.get("valid_until")
            doc = objects.get(pr["sha256"])
            if doc is None:
                # No document with the committed hash. If a document with the committed profile_id is held, the commitment
                # is wrong (or the firm withheld the committed version): an error, and the record is still checked against
                # the held Profile, so a wrong hash cannot hide a record that contradicts its Profile (INV-021, INV-023).
                held = sorted((d for d in objects.values() if isinstance(d, dict) and d.get("profile_id") == pr["profile_id"]),
                              key=lambda d: ((d.get("subject") or {}).get("deployment_id") != r["inventory_ref"], canonical_hash(d)))
                if held:
                    E("INV-021", f"{path}/profile", f"{r['inventory_ref']}: Profile {pr['profile_id']} is held with hash {canonical_hash(held[0])[:19]}…, "
                      f"not the committed {str(pr['sha256'])[:19]}…: deliver the committed version or correct the commitment")
                    if (held[0].get("subject") or {}).get("deployment_id") == r["inventory_ref"]:
                        _divergence(r, held[0], meta, path, E, W)
            if doc is not None:
                h = canonical_hash(doc)
                if h != pr["sha256"]:
                    E("INV-021", f"{path}/profile", f"{r['inventory_ref']}: the delivered Profile's hash {h[:19]}… is not the committed one")
                else:
                    subj, iss = doc.get("subject") or {}, doc.get("issuance") or {}
                    actual = {"profile_id": doc.get("profile_id"), "stage": doc.get("stage"),
                              "headline": (doc.get("assurance") or {}).get("headline"), "valid_until": iss.get("valid_until")}
                    diffs = [k for k in actual if pr.get(k) != actual[k]]
                    if diffs: E("INV-021", f"{path}/profile", f"{r['inventory_ref']}: the commitment's {', '.join(diffs)} differ{'s' if len(diffs) == 1 else ''} from the delivered Profile")
                    if subj.get("institution") != inst["name"]:
                        E("INV-021", f"{path}/profile", f"{r['inventory_ref']}: the delivered Profile is about '{subj.get('institution')}', not '{inst['name']}'")
                    if subj.get("deployment_id") != r["inventory_ref"]:
                        E("INV-021", f"{path}/profile", f"{r['inventory_ref']}: the delivered Profile's deployment_id '{subj.get('deployment_id')}' is not this record's inventory_ref")
                    _divergence(r, doc, meta, path, E, W)
                    rep = check_profile(doc)
                    for f in rep.errors: E("INV-021", f"{path}/profile", f"{r['inventory_ref']}: the Profile fails {f['rule']}: {f['message']}")
                    valid_until = iss.get("valid_until")
            if pr["stage"] == "issued" and valid_until and valid_until < meta["as_of"]:
                W("INV-022", f"{path}/profile", f"{r['inventory_ref']}: Profile {pr['profile_id']} expired on {valid_until}")
    if previous is not None:
        pm = previous["snapshot"]
        if previous["institution"]["firm_id"] != inst["firm_id"]: E("INV-030", "institution/firm_id", "the previous snapshot is for a different firm")
        if meta["sequence"] != pm["sequence"] + 1: E("INV-030", "snapshot/sequence", f"sequence {meta['sequence']} does not follow {pm['sequence']}")
        if meta["previous_hash"] != canonical_hash(previous): E("INV-030", "snapshot/previous_hash", "previous_hash is not the hash of the previous snapshot: history has been altered or a snapshot is missing")
        if meta["as_of"] < pm["as_of"]: E("INV-030", "snapshot/as_of", "as_of is earlier than the previous snapshot's")
        for pe in previous["records"]:
            pr_ = pe["record"]
            if pr_["deployment_status"] != "retired" and pr_["inventory_ref"] not in seen:
                E("INV-031", "records", f"{pr_['inventory_ref']} ({pr_['agent_name']}) was in the previous snapshot and has disappeared without being marked retired")
    elif meta["sequence"] != 1:
        W("INV-030", "snapshot", "previous snapshot not supplied, so the chain was not checked")
    if meta["sequence"] == 1 and meta["previous_hash"] is not None:
        E("INV-030", "snapshot/previous_hash", "the first snapshot (sequence 1) must have previous_hash null")
    sigs = snap["signatures"]
    if not sigs: E("INV-040", "signatures", "no institution signature")
    h = canonical_hash(snap)
    entry = registry.get(inst["firm_id"]) if registry is not None else None
    if registry is not None and entry is None:
        E("INV-040", "institution/firm_id", f"firm {inst['firm_id']} is not in the key register")
    for i, s in enumerate(sigs):
        if s["signed_hash"] != h: E("INV-040", f"signatures/{i}", "the signature does not cover this snapshot"); continue
        if not _verify(s): E("INV-040", f"signatures/{i}", "the signature does not verify"); continue
        if registry is None:
            W("INV-040", f"signatures/{i}", "UNVERIFIED SIGNER: no key register was supplied, so the signing key was not checked")
            prev_keys = {x["public_key"] for x in (previous or {}).get("signatures", [])}
            if previous is not None and prev_keys and s["public_key"] not in prev_keys:
                E("INV-040", f"signatures/{i}", "the signing key changed since the previous snapshot and no key register records the rotation")
        elif entry is not None:
            if not entry.get("public_key"): E("INV-040", f"signatures/{i}", f"firm {inst['firm_id']} has no registered key")
            elif not key_allowed(entry, s["public_key"], meta["sequence"]):
                E("INV-040", f"signatures/{i}", "signed with a key that is not the firm's registered key")
    return out

def check_feed(snaps, objects=None, registry=None):
    """Check one firm's snapshots as a chain. Returns [(snapshot, findings)] in sequence order.
    Two different snapshots claiming the same sequence are a fork (INV-030): neither is accepted as the chain."""
    objects = objects or {}
    good, bad = [], []
    for s in snaps:
        f = check(s, None, objects, registry)
        (bad if any(x[0] == "INV-001" for x in f) else good).append((s, f))
    # each firm's history is a separate chain: another firm's snapshot never affects this one
    firms = {}
    for s, f in good: firms.setdefault(s["institution"]["firm_id"], []).append((s, f))
    out = []
    for fid in sorted(firms):
        out += _check_chain(firms[fid], objects, registry)
    return out + bad

def _check_chain(good, objects, registry):
    by_seq = {}
    for s, _ in good: by_seq.setdefault(s["snapshot"]["sequence"], []).append(s)
    hashes = {id(s): canonical_hash(s) for s, _ in good}
    out = []; fork_at = None
    for seq in sorted(by_seq):
        group = by_seq[seq]; uniq = {}
        for s in group: uniq.setdefault(hashes[id(s)], s)  # identical copies count once
        if len(uniq) > 1 and fork_at is None: fork_at = seq
        for s in uniq.values():
            cands = by_seq.get(seq - 1, [])
            prev = next((p for p in cands if hashes[id(p)] == s["snapshot"]["previous_hash"]), None)
            if prev is None and len({hashes[id(p)] for p in cands}) == 1: prev = cands[0]
            f = check(s, prev, objects, registry)
            if seq > 1 and not cands:
                f.insert(0, ("INV-030", "error", "snapshot/sequence", f"snapshot {seq - 1} is missing from the feed"))
            elif seq > 1 and prev is None:
                f.insert(0, ("INV-030", "error", "snapshot/previous_hash", f"no snapshot {seq - 1} in the feed has this snapshot's previous_hash"))
            if len(uniq) > 1:
                f.insert(0, ("INV-030", "error", "snapshot/sequence", f"fork: {len(uniq)} different snapshots claim sequence {seq}"))
            elif fork_at is not None and seq > fork_at:
                f.insert(0, ("INV-030", "error", "snapshot/sequence", f"follows an unresolved fork at sequence {fork_at}: not used until the supervisor confirms with the firm which snapshot {fork_at} is genuine and removes the other"))
            out.append((s, f))
    return out

def diff(old, new):
    """Changes from old to new: {'added': [...], 'removed': [...], 'changed': [(ref, field, before, after)]}."""
    o = {e["record"]["inventory_ref"]: e for e in old["records"]}; n = {e["record"]["inventory_ref"]: e for e in new["records"]}
    ch = []
    for ref in sorted(set(o) & set(n)):
        a, b = o[ref]["record"], n[ref]["record"]
        for k in sorted(set(a) | set(b)):
            if k == "controls":
                for c in sorted(set(a.get(k, {})) | set(b.get(k, {}))):
                    if a[k].get(c) != b[k].get(c): ch.append((ref, f"control.{c}", a[k].get(c), b[k].get(c)))
            elif a.get(k) != b.get(k): ch.append((ref, k, a.get(k), b.get(k)))
        if (o[ref].get("profile") or {}).get("sha256") != (n[ref].get("profile") or {}).get("sha256"):
            ch.append((ref, "profile", (o[ref].get("profile") or {}).get("profile_id"), (n[ref].get("profile") or {}).get("profile_id")))
    return {"added": sorted(set(n) - set(o)), "removed": sorted(set(o) - set(n)), "changed": ch}

def _objects(d):
    out = {}
    if d:
        for f in sorted(Path(d).glob("*.json")):
            try: doc = _load(f)
            except InputError as e: print(f"warning: skipped {e}", file=sys.stderr); continue
            if isinstance(doc, dict): out[canonical_hash(doc)] = doc
    return out

def load_registry(p):
    reg = _load(p)
    if not isinstance(reg, dict) or not isinstance(reg.get("firms"), list): raise InputError(f"{p}: a key register needs a 'firms' list")
    return {f["firm_id"]: f for f in reg["firms"] if isinstance(f, dict) and f.get("firm_id")}

def _print(findings):
    for r, sev, path, msg in findings: print(f"{sev.upper():7} {r}  {path}: {msg}")
    errs = sum(1 for f in findings if f[1] == "error")
    print(f"{'CONFORMS' if not errs else 'DOES NOT CONFORM'}: {errs} error(s), {len(findings) - errs} warning(s)")
    ok, why = trust(findings)
    print("TRUSTED: may feed supervisory views" if ok else f"QUARANTINED: not to be used in supervisory views ({len(why)} reason(s))")
    return 1 if errs else 0

def _register(a, ap):
    if a.registry: return load_registry(a.registry)
    if a.no_register: return None
    ap.error("a key register is required: pass --registry REGISTER.json, or --no-register to check without one (signers are then reported as unverified)")

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build"); b.add_argument("lite"); b.add_argument("--firm-id", required=True); b.add_argument("--as-of", required=True)
    b.add_argument("--profiles"); b.add_argument("--previous"); b.add_argument("--trigger", default="scheduled")
    b.add_argument("--key", required=True); b.add_argument("--signer-name", required=True); b.add_argument("--signer-role", required=True)
    b.add_argument("--lei"); b.add_argument("--out", required=True)
    c = sub.add_parser("check"); c.add_argument("snapshot"); c.add_argument("--previous"); c.add_argument("--objects")
    c.add_argument("--registry"); c.add_argument("--no-register", action="store_true")
    ch = sub.add_parser("chain"); ch.add_argument("dir"); ch.add_argument("--objects"); ch.add_argument("--registry")
    ch.add_argument("--no-register", action="store_true"); ch.add_argument("--json", action="store_true")
    d = sub.add_parser("diff"); d.add_argument("old"); d.add_argument("new")
    h = sub.add_parser("hash"); h.add_argument("file")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "build": return _build(a)
        if a.cmd == "check":
            reg = _register(a, c)
            try: snap = _load(a.snapshot)
            except InputError as e: _print([("INV-001", "error", "-", str(e))]); return 3
            return _print(check(snap, _load(a.previous) if a.previous else None, _objects(a.objects), reg))
        if a.cmd == "chain":
            reg = _register(a, ch); snaps, names, rc, report = [], {}, 0, []
            for f in sorted(Path(a.dir).glob("inventory-*.json")):
                try: s = _load(f)
                except InputError as e:
                    rc = 1; report.append({"file": f.name, "sequence": None, "trusted": False, "quarantine_reasons": [f"INV-001 {e}"], "findings": [["INV-001", "error", "-", str(e)]]})
                    if not a.json: print(f"{f.name}: could not be read, 1 error(s)\n   INV-001 -: {e}")
                    continue
                snaps.append(s); names[id(s)] = f.name
            for s, fs in check_feed(snaps, _objects(a.objects), reg):
                errs = [x for x in fs if x[1] == "error"]; rc |= bool(errs)
                meta = s.get("snapshot") if isinstance(s, dict) and isinstance(s.get("snapshot"), dict) else {}
                ok, why = trust(fs)
                report.append({"file": names[id(s)], "sequence": meta.get("sequence"), "trusted": ok, "quarantine_reasons": why, "findings": [list(x) for x in fs]})
                if not a.json:
                    nrec = len(s["records"]) if isinstance(s, dict) and isinstance(s.get("records"), list) else 0
                    print(f"{names[id(s)]}: sequence {meta.get('sequence')} as of {meta.get('as_of')}, {nrec} records, {len(errs)} error(s), {len(fs) - len(errs)} warning(s), {'trusted' if ok else 'QUARANTINED'}")
                    for x in errs: print(f"   {x[0]} {x[2]}: {x[3]}")
            if a.json: print(json.dumps(report, ensure_ascii=False))
            return int(rc)
        if a.cmd == "diff":
            r = diff(_load(a.old), _load(a.new))
            print(f"added {len(r['added'])}: {', '.join(r['added'])}\nremoved {len(r['removed'])}: {', '.join(r['removed'])}")
            for ref, k, x, y in r["changed"]: print(f"  {ref}  {k}: {x} -> {y}")
            return 0
        if a.cmd == "hash":
            print(canonical_hash(_load(a.file))); return 0
    except InputError as e:
        print(f"error: {e}", file=sys.stderr); return 3

def _build(a):
    src = Path(a.lite)
    if src.suffix.lower() == ".json": records = _load(src)
    else:
        try: res = arp_lite.read_raw(src)
        except Exception as e: raise InputError(f"{src}: {e}")
        rows, problems = res if isinstance(res, tuple) and len(res) == 2 and isinstance(res[1], list) else (res, [])
        if problems:
            print(f"not written: {src} has problems to fix first:"); [print(f"  {p}") for p in problems]; return 1
        records = [arp_lite.to_record(r) for _, r in rows]
    by_id = {}
    for p in _objects(a.profiles).values():
        pid = p.get("profile_id")
        if pid in by_id:
            stages = {by_id[pid].get("stage"), p.get("stage")}
            if stages == {"draft", "issued"}:
                if p.get("stage") == "issued": by_id[pid] = p
                continue
            raise SystemExit(f"error: two {p.get('stage')} Profiles in {a.profiles} share the id {pid}; keep one")
        by_id[pid] = p
    key = Path(a.key).read_bytes()
    prev = _load(a.previous) if a.previous else None
    snap = build(records, a.firm_id, a.as_of, prev, by_id, a.trigger, lei=a.lei,
                 attestation={"name": a.signer_name, "role": a.signer_role, "statement": ATTEST})
    snap = sign(snap, key, a.signer_name)
    own = {a.firm_id: {"firm_id": a.firm_id, "public_key": public_key_b64(key)}}
    findings = check(snap, prev, _objects(a.profiles), own)
    if any(f[1] == "error" for f in findings):
        print(f"not written: the snapshot fails its own checks. Fix these and build again:")
        return _print(findings)
    Path(a.out).write_text(json.dumps(snap, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {a.out}: {len(snap['records'])} records, sequence {snap['snapshot']['sequence']}, {canonical_hash(snap)}")
    return _print(findings)

if __name__ == "__main__":
    sys.exit(main())
