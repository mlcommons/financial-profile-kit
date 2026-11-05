#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Agent Reliability Profile arp/1.0-rc2: reference conformance checker.

Normative source: ../spec/SPEC.md. This file is a *reference* implementation of the
rules there; where the two disagree, SPEC.md wins and this file has a bug.

  python3 arp_conform.py check  PROFILE.json [--json] [--as-of YYYY-MM-DD]
  python3 arp_conform.py hash   PROFILE.json            # canonical hash (RFC 8785, signatures excluded)
  python3 arp_conform.py sign   PROFILE.json --role owner --name "A. Person" --key owner.key --out SIGNED.json
  python3 arp_conform.py sign   SIGNED.json --role assessor --name "B. Person" --organisation "Firm LLP" --key a.key --in-place
  python3 arp_conform.py sign-manifest PROFILE.json --signer "A. Person" --key owner.key --in-place
  python3 arp_conform.py keygen owner.key
  python3 arp_conform.py pubkey owner.key
  python3 arp_conform.py redact-prepare ISSUED.json --out REDACTED.json [--suffix -redacted-1]   # DISCLOSURE.md

Exit codes: 0 conformant (or command done); 1 not conformant, or signing refused;
2 usage error; 3 input or tool error (file unreadable, unexpected failure).

Requires: jsonschema>=3.2. Signature checks need `cryptography` (>=40); without it the
result for an issued Profile is indeterminate, reported as an error (ARP-091).
"""
from __future__ import annotations

import argparse
import base64
import copy
import datetime as dt
import hashlib
import json
import math
import os
import re
import unicodedata
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = HERE.parent / "spec"
SPEC_ID = "arp/1.0-rc2"
SIG_CONTEXT = "arp-signature/1.0-rc2"
MANIFEST_CONTEXT = "arp-evidence-manifest/1.0-rc2"
AXES = ("autonomy", "odd", "actions", "controls")
ACTIONS = [f"A{i}" for i in range(1, 13)]
JUDGED = {"held", "contradicted"}
CITED = {"document_derived", "configuration_derived", "measured"}
VOCABS = ("action-classes", "autonomy-tiers", "business-lines", "conflict-kinds", "control-catalogue",
          "dispositions", "invalidation-triggers", "provenance-classes", "use-cases")
DEFAULT_TRIGGERS = ("model_change", "harness_change", "odd_expansion", "action_class_added",
                    "critical_control_removed", "access_or_owner_change")
SIMULATED = {"simulated_evidence", "suspected_simulated_evidence"}
# SPEC §4 "Several results on one field": a field's disposition is the most severe of its results, in this order.
DISPOSITION_ORDER = ("contradicted", "held_by_agent_only", "not_established", "held")


def field_dispositions(results):
    """Aggregate results per field (SPEC §4): {field_id: {"disposition": most severe, "results": [all, in order]}}.
    A contradiction is never hidden by a later pass; every result is kept."""
    out = {}
    for x in results:
        out.setdefault(x["field_id"], []).append(x)
    rank = {d: i for i, d in enumerate(DISPOSITION_ORDER)}
    return {fid: {"disposition": min((x["disposition"] for x in xs), key=lambda d: rank.get(d, len(rank))), "results": xs}
            for fid, xs in out.items()}
MAX_SAFE = 2 ** 53
MIN_DATE = dt.date(2000, 1, 1)
# Public keys of the DEMO-ONLY keys shipped in examples/demo-keys/. Anything they sign proves nothing.
DEMO_PUBLIC_KEYS = {
    "JsHW4JfvQC24+p46CNYcr7dsxv7Uf7ePg3FW/jvwu9o=": "DEMO-ONLY-owner.key",
    "NFG6vQQ8vsKo/kn+f88pimLKhoGIwMxzIoKQcJAh9tk=": "DEMO-ONLY-assessor.key",
}
PLACEHOLDER = re.compile(r"(?<![A-Za-z0-9])(?:TODO|TBD|FIXME)(?![A-Za-z0-9])", re.IGNORECASE)
ANGLE_PLACEHOLDER = re.compile(r"[ \t]*<[^<>]+>[ \t]*\Z")
DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
DATETIME_RE = re.compile(r"([0-9]{4}-[0-9]{2}-[0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})(\.[0-9]+)?(Z|[+-]([0-9]{2}):([0-9]{2}))\Z")


class InputError(Exception):
    """The bytes are not a JSON object a checker can read (reported as ARP-001)."""


# ------------------------------------------------------------------ canonical form (RFC 8785, JCS)

def _jcs_number(x) -> str:
    if isinstance(x, bool):
        raise TypeError("bool is not a number")
    if isinstance(x, int):
        if abs(x) >= MAX_SAFE:
            raise ValueError(f"number {x} has magnitude 2^53 or more")
        return str(x)
    if not math.isfinite(x):
        raise ValueError("NaN and Infinity are not allowed")
    if abs(x) >= MAX_SAFE:
        raise ValueError(f"number {x!r} has magnitude 2^53 or more")
    if x == 0:
        return "0"
    if x.is_integer():
        return str(int(x))
    # ECMAScript Number::toString from the shortest round-trip digits (repr gives those)
    from decimal import Decimal
    _, digits, exp = Decimal(repr(abs(x))).as_tuple()
    s = "".join(map(str, digits))
    n = exp + len(s)                           # position of the decimal point relative to the digits
    s = s.rstrip("0")
    k = len(s)
    if k <= n <= 21:
        out = s + "0" * (n - k)
    elif 0 < n <= 21:
        out = s[:n] + "." + s[n:]
    elif -6 < n <= 0:
        out = "0." + "0" * (-n) + s
    else:
        e = n - 1
        out = (s if k == 1 else s[0] + "." + s[1:]) + "e" + ("+" if e > 0 else "-") + str(abs(e))
    return ("-" if x < 0 else "") + out


def _jcs_string(s: str) -> str:
    if any(0xD800 <= ord(c) <= 0xDFFF for c in s):
        raise ValueError("string contains an unpaired surrogate")
    return json.dumps(s, ensure_ascii=False)


def canonical_json(obj) -> str:
    """RFC 8785 canonical form. Raises ValueError for values JCS cannot represent exactly."""
    if obj is None:
        return "null"
    if obj is True:
        return "true"
    if obj is False:
        return "false"
    if isinstance(obj, (int, float)):
        return _jcs_number(obj)
    if isinstance(obj, str):
        return _jcs_string(obj)
    if isinstance(obj, (list, tuple)):
        return "[" + ",".join(canonical_json(v) for v in obj) + "]"
    if isinstance(obj, dict):
        keys = sorted(obj, key=lambda k: k.encode("utf-16-be", "surrogatepass"))
        return "{" + ",".join(_jcs_string(k) + ":" + canonical_json(obj[k]) for k in keys) + "}"
    raise TypeError(f"not a JSON value: {type(obj).__name__}")


def sha256_of(obj) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def canonical_hash(profile: dict) -> str:
    return sha256_of({k: v for k, v in profile.items() if k != "signatures"})


def signature_statement(sig: dict) -> bytes:
    return canonical_json({"context": SIG_CONTEXT, "alg": sig.get("alg", "ed25519"), "role": sig["role"], "name": sig["name"],
                           "organisation": sig.get("organisation"), "public_key": sig["public_key"],
                           "signed_hash": sig["signed_hash"]}).encode("utf-8")


def manifest_statement(m: dict) -> bytes:
    return canonical_json({"context": MANIFEST_CONTEXT, "content_hash": m["content_hash"], "signer": m["signer"],
                           "public_key": m["public_key"]}).encode("utf-8")


# ------------------------------------------------------------------ strict loading

def _reject_duplicates(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise InputError(f"duplicate member name '{k}'")
        out[k] = v
    return out


def _finite_float(s):
    f = float(s)
    if not math.isfinite(f):
        raise InputError(f"number {s} is out of range")
    return f


def _no_constant(name):
    raise InputError(f"'{name}' is not allowed in JSON")


def loads_strict(data) -> dict:
    """Parse bytes or text as a Profile: UTF-8, no duplicate names, no NaN/Infinity, an object at the top."""
    if isinstance(data, (bytes, bytearray)):
        try:
            data = bytes(data).decode("utf-8-sig")
        except UnicodeDecodeError as e:
            raise InputError(f"the file is not UTF-8 ({e.reason} at byte {e.start})")
    elif data.startswith("﻿"):
        data = data[1:]
    try:
        obj = json.loads(data, object_pairs_hook=_reject_duplicates, parse_float=_finite_float, parse_constant=_no_constant)
    except InputError:
        raise
    except json.JSONDecodeError as e:
        raise InputError(f"not valid JSON: {e.msg} (line {e.lineno}, column {e.colno})")
    except RecursionError:
        raise InputError("the JSON is nested too deeply")
    if not isinstance(obj, dict):
        raise InputError(f"a Profile is a JSON object, not {type(obj).__name__}")
    return obj


def load_vocab(name: str) -> dict:
    return json.loads((SPEC / "vocab" / f"{name}.json").read_text(encoding="utf-8"))


def axis_of(field_id: str) -> str:
    return field_id.split(".", 1)[0]


def claim_fields(claim: dict) -> set:
    """Every populated claim field, by field id (SPEC §3). The statement is not a field."""
    au, odd, act = claim["autonomy"], claim["odd"], claim["actions"]
    f = {"autonomy.tier"} | {f"autonomy.modifiers.{m}" for m in au["modifiers"]}
    if "approval_quality" in au:
        f.add("autonomy.approval_quality")
    f |= {f"odd.{k}" for k, v in odd.items() if v not in (None, "", [], {})}
    f |= {f"actions.{a}" for a in set(act["permitted"]) | set(act["prohibited"])}
    f |= {f"controls.{c['control_id']}" for c in claim["controls"]}
    return f


def parse_date(s: str):
    if not isinstance(s, str) or not DATE_RE.match(s):
        return None
    try:
        return dt.date.fromisoformat(s)
    except ValueError:
        return None


def parse_datetime(s: str):
    m = DATETIME_RE.match(s) if isinstance(s, str) else None
    if not m:
        return None
    d = parse_date(m.group(1))
    hh, mm, ss = int(m.group(2)), int(m.group(3)), int(m.group(4))
    if d is None or hh > 23 or mm > 59 or ss > 59:
        return None
    if m.group(6) != "Z" and (int(m.group(7)) > 23 or int(m.group(8)) > 59):
        return None
    return d  # the calendar date as written


# Signer names are compared after Unicode NFC normalisation, with runs of whitespace collapsed to one
# space and leading/trailing whitespace removed (the same character set in every implementation).
_WS = re.compile("[\t\n\v\f\r \u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]+")


def norm_name(s) -> str:
    return _WS.sub(" ", unicodedata.normalize("NFC", str(s))).strip(" ")


class Report:
    def __init__(self):
        self.items = []

    def err(self, rule, msg, path="", pending=False):
        # pending: the error is only that a required signature has not been added yet
        it = {"rule": rule, "severity": "error", "message": msg, "path": path}
        if pending:
            it["pending_signature"] = True
        self.items.append(it)

    def warn(self, rule, msg, path=""):
        self.items.append({"rule": rule, "severity": "warning", "message": msg, "path": path})

    @property
    def errors(self):
        return [i for i in self.items if i["severity"] == "error"]


def _validator():
    return make_validator(json.loads((SPEC / "profile.schema.json").read_text(encoding="utf-8")))


def make_validator(schema: dict):
    """A Draft 7 validator with the kit's semantics, used for every ARP schema: strict calendar dates and
    RFC 3339 date-times for 'format', and ECMA-262 'pattern' matching (no match before a final newline).
    Works with jsonschema 3.2 and later."""
    import jsonschema
    schema = copy.deepcopy(schema)
    schema.pop("$id", None)  # all $refs are local; older jsonschema cannot resolve them against a urn: base
    fc = jsonschema.FormatChecker(formats=())

    @fc.checks("date")
    def _d(v):
        return not isinstance(v, str) or parse_date(v) is not None

    @fc.checks("date-time")
    def _dtm(v):
        return not isinstance(v, str) or parse_datetime(v) is not None

    def pattern(validator, patrn, instance, schema_):
        # ECMA-262 semantics: '$' matches only at the very end (Python's also matches before a final newline)
        if validator.is_type(instance, "string"):
            if not re.search(patrn, instance) or (patrn.endswith("$") and instance.endswith("\n")):
                yield jsonschema.ValidationError(f"{instance!r} does not match {patrn!r}")

    cls = jsonschema.validators.extend(jsonschema.Draft7Validator, validators={"pattern": pattern})
    return cls(schema, format_checker=fc)


def _value_problems(o, path=""):
    """ARP-001 checks the schema cannot express: exact numbers and well-formed strings."""
    if isinstance(o, dict):
        for k, v in o.items():
            if any(0xD800 <= ord(c) <= 0xDFFF for c in k):
                yield path, "a member name contains an unpaired surrogate"
            yield from _value_problems(v, f"{path}/{k}" if path else k)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _value_problems(v, f"{path}/{i}")
    elif isinstance(o, str):
        if any(0xD800 <= ord(c) <= 0xDFFF for c in o):
            yield path, "string contains an unpaired surrogate"
    elif isinstance(o, bool) or o is None:
        return
    elif isinstance(o, (int, float)):
        if isinstance(o, float) and not math.isfinite(o):
            yield path, "NaN and Infinity are not allowed"
        elif abs(o) >= MAX_SAFE:
            yield path, f"number {o!r} has magnitude 2^53 or more and cannot be represented exactly"


def _strings(o, path="", skip=("signatures", "evidence_manifest")):
    if isinstance(o, dict):
        for k, v in o.items():
            if not path and k in skip:
                continue
            yield from _strings(v, f"{path}/{k}" if path else k, skip)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _strings(v, f"{path}/{i}", skip)
    elif isinstance(o, str):
        yield path, o


def _crypto():
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature
        return Ed25519PublicKey, InvalidSignature
    except ImportError:
        return None, None


def _verify(public_key_b64: str, value_b64: str, message: bytes):
    """True / False, or None when cryptography is not installed."""
    Ed25519PublicKey, InvalidSignature = _crypto()
    if Ed25519PublicKey is None:
        return None
    try:
        pk = base64.b64decode(public_key_b64, validate=True)
        sv = base64.b64decode(value_b64, validate=True)
        if len(pk) != 32 or len(sv) != 64:
            return False
        Ed25519PublicKey.from_public_bytes(pk).verify(sv, message)
        return True
    except (InvalidSignature, ValueError):
        return False


# ------------------------------------------------------------------ the rules

def check(profile, as_of: dt.date | None = None) -> Report:
    r = Report()

    # ARP-001 structure -------------------------------------------------------
    if not isinstance(profile, dict):
        r.err("ARP-001", f"a Profile is a JSON object, not {type(profile).__name__}")
        return r
    for pth, msg in _value_problems(profile):
        r.err("ARP-001", msg, pth)
    if r.errors:
        return r
    try:
        import jsonschema  # noqa: F401
    except ImportError:  # pragma: no cover
        r.err("ARP-001", "jsonschema is not installed; structural validation cannot run")
        return r
    for e in sorted(_validator().iter_errors(profile), key=lambda e: [str(p) for p in e.path]):
        r.err("ARP-001", e.message, "/".join(str(p) for p in e.path))
    if r.errors:
        return r  # cross-field rules assume a well-formed document

    issued = profile["stage"] == "issued"

    # ARP-002 no unfilled placeholders survive into a Profile
    for pth, s in _strings(profile):
        if PLACEHOLDER.search(s):
            r.err("ARP-002", f"unfilled placeholder in {s[:60]!r}", pth)
        elif ANGLE_PLACEHOLDER.match(s):
            (r.err if issued else r.warn)("ARP-002", f"placeholder value {s.strip()!r}", pth)

    claim, ass, prov = profile["claim"], profile["assurance"], profile["provenance"]
    axes, headline = ass["axes"], ass["headline"]
    results = profile.get("results", [])
    status = profile["status"]
    open_f = status.get("open_findings", [])
    gaps = status.get("accepted_gaps", [])
    evidence = {e["id"]: e for e in profile["evidence"]}
    # ARP-055 one evidence item per id, so every citation resolves to exactly one file
    first_id, by_path, by_hash = {}, {}, {}
    for i, e in enumerate(profile["evidence"]):
        eid, pth, h = e["id"], e.get("path"), e.get("content_hash")
        if eid in first_id:
            r.err("ARP-055", f"evidence id '{eid}' is used by items {first_id[eid]} and {i}: a citation must resolve to exactly one item", f"evidence/{i}/id")
            continue
        first_id[eid] = i
        if pth in by_path and by_path[pth][1] != h:
            r.warn("ARP-055", f"evidence '{eid}' has the same path as '{by_path[pth][0]}' ({pth}) but a different content hash", f"evidence/{i}")
        by_path.setdefault(pth, (eid, h))
        if h in by_hash and by_hash[h] != eid:
            r.warn("ARP-055", f"evidence '{eid}' has the same content hash as '{by_hash[h]}'", f"evidence/{i}")
        by_hash.setdefault(h, eid)
    sigs = profile.get("signatures", [])
    iss = profile["issuance"]
    top = max(axes.values())

    # ARP-003 vocabulary versions
    vv = profile.get("vocab_versions")
    if issued:
        missing_v = [n for n in VOCABS if not (vv or {}).get(n)]
        if missing_v:
            r.err("ARP-003", f"an issued Profile must record the version of every vocabulary; missing: {missing_v}", "vocab_versions")
    for n, ver in (vv or {}).items():
        if n in VOCABS:
            mine = load_vocab(n).get("version")
            if mine and ver != mine:
                r.warn("ARP-003", f"written against {n} {ver}; this checker uses {mine}", f"vocab_versions/{n}")

    # ARP-010 headline is the minimum of the axis levels
    if headline != min(axes.values()):
        r.err("ARP-010", f"headline {headline} != min(axis levels) {min(axes.values())}", "assurance/headline")

    fields = claim_fields(claim)
    result_fields = {x["field_id"] for x in results}
    judged_fields = {x["field_id"] for x in results if x["disposition"] in JUDGED}

    # ARP-011 'measured' only from an executed test
    for fid, p in prov.items():
        if p["class"] == "measured":
            if axes[axis_of(fid)] < 2:
                r.err("ARP-011", f"{fid} is 'measured' but axis '{axis_of(fid)}' is Level 1 (nothing executed)", f"provenance/{fid}")
            elif fid not in result_fields:
                r.err("ARP-011", f"{fid} is 'measured' but no result tests it: only an executed test confers 'measured'", f"provenance/{fid}")
    for fid in sorted(judged_fields):
        if fid in prov and prov[fid]["class"] != "measured":
            r.warn("ARP-011", f"{fid} has a judged result but its provenance is '{prov[fid]['class']}', not 'measured'", f"provenance/{fid}")

    # ARP-012 an axis at Level >=2 judged something, and shows its coverage truthfully
    cov = ass.get("coverage", {})
    for ax, lvl in axes.items():
        if lvl < 2:
            continue
        on_ax = [x for x in results if axis_of(x["field_id"]) == ax]
        judged = [x for x in on_ax if x["disposition"] in JUDGED]
        if not judged:
            r.err("ARP-012", f"axis '{ax}' claims Level {lvl} but no result on it was judged (held/contradicted): a Profile that judged nothing is a Level 1 with a signature block", f"assurance/axes/{ax}")
        c = cov.get(ax)
        want = {"claim_fields": sum(1 for f in fields if axis_of(f) == ax),
                "tested": len({x["field_id"] for x in on_ax}), "judged": len({x["field_id"] for x in judged})}
        if c is None:
            r.err("ARP-012", f"axis '{ax}' is at Level {lvl} but assurance.coverage.{ax} is missing", f"assurance/coverage/{ax}")
        elif c != want:
            r.err("ARP-012", f"coverage for '{ax}' says {c}, but the Profile shows {want}", f"assurance/coverage/{ax}")

    # ARP-013 results only on axes at Level >=2, citing real evidence
    for i, x in enumerate(results):
        if x["field_id"] not in fields:
            r.err("ARP-013", f"result {x['claim_id']} tests {x['field_id']}, which is not a field of the claim", f"results/{i}")
        for ref in x["evidence_refs"]:
            if ref not in evidence:
                r.err("ARP-013", f"result {x['claim_id']} cites evidence '{ref}', which is not in the evidence manifest", f"results/{i}")
        if axes[axis_of(x["field_id"])] < 2:
            r.err("ARP-013", f"result {x['claim_id']} is on axis '{axis_of(x['field_id'])}', which is Level 1", f"results/{i}")
        if x["disposition"] in JUDGED and not x["evidence_refs"]:
            r.err("ARP-013", f"judged result {x['claim_id']} cites no evidence", f"results/{i}")

    # ARP-071 several results on one field: reported by the most severe (SPEC §4), every result kept
    for fid, agg in sorted(field_dispositions(results).items()):
        ds = [x["disposition"] for x in agg["results"]]
        if len(set(ds)) > 1:
            r.warn("ARP-071", f"{fid} has {len(ds)} results that disagree ({', '.join(ds)}); it is reported as '{agg['disposition']}', and every result is listed", "results")

    # ARP-014 who stands behind each axis
    assessors = ass["assessors"]
    owner_keys = {s["public_key"] for s in sigs if s["role"] == "owner"}
    l3_orgs = set()
    for ax in AXES:
        a, lvl = assessors[ax], axes[ax]
        indep = a["role"] == "independent_assessor"
        if lvl == 3 and not indep:
            r.err("ARP-014", f"axis '{ax}' is at Level 3, so its assessor must be an independent assessor", f"assurance/assessors/{ax}")
        if lvl < 3 and indep:
            r.err("ARP-014", f"axis '{ax}' is at Level {lvl} but names an independent assessor: independent testing is Level 3", f"assurance/assessors/{ax}")
        if indep:
            if not a.get("organisation"):
                r.err("ARP-014", f"the independent assessor for '{ax}' is not named (organisation)", f"assurance/assessors/{ax}/organisation")
            else:
                l3_orgs.add(a["organisation"])
            rep = a.get("report")
            if not rep:
                r.err("ARP-014", f"the independent assessor for '{ax}' cites no signed report", f"assurance/assessors/{ax}/report")
            elif rep not in evidence or evidence[rep].get("artifact_class") != "assessor_report":
                r.err("ARP-014", f"the assessor report '{rep}' for '{ax}' is not an evidence item of class 'assessor_report'", f"assurance/assessors/{ax}/report")
    if issued:
        for org in sorted(l3_orgs):
            asigs = [s for s in sigs if s["role"] == "assessor" and s.get("organisation") == org]
            if not asigs:
                r.err("ARP-014", f"an issued Level 3 Profile requires a signature from its assessor '{org}' (role 'assessor', that organisation)", "signatures", pending=True)
            elif any(s["public_key"] in owner_keys for s in asigs):
                r.err("ARP-014", f"the assessor '{org}' signed with the owner's key", "signatures")
    for i, s in enumerate(sigs):
        if s["role"] == "assessor" and s.get("organisation") not in l3_orgs:
            r.err("ARP-014", f"signature {i} is an assessor signature for '{s.get('organisation')}', which is not the assessor of any Level 3 axis", f"signatures/{i}")

    # ARP-015 the standard disclosures travel with the Profile
    lv = set(axes.values())
    comp = ass["comparability"]
    need = {"not_comparable"}
    if 1 in lv: need.add("level1_untested")
    if 2 in lv: need.add("self_tested")
    if 3 in lv: need.add("independently_verified")
    if comp["flag"]: need.add("benchmark_not_production")
    have = set(ass["disclosures"])
    if need - have:
        r.err("ARP-015", f"missing required disclosure(s): {sorted(need - have)}", "assurance/disclosures")
    if have - need:
        r.err("ARP-015", f"disclosure(s) not supported by the assurance vector: {sorted(have - need)}", "assurance/disclosures")

    # ARP-016 how each result was decided; enforceable boundaries are not decided by a model judge alone
    for i, x in enumerate(results):
        ev = x["evaluation"]
        if ev["method"] in ("model_judged", "hybrid") and not ev.get("judge_model"):
            r.err("ARP-016", f"{x['claim_id']} used a model judge but does not name it (provider, model, pinned version)", f"results/{i}/evaluation")
        if axis_of(x["field_id"]) not in ("actions", "controls") or x["disposition"] not in JUDGED:
            continue
        if ev["method"] == "model_judged":
            r.err("ARP-016", f"{x['claim_id']} decides an action or control claim by model judge alone; use control decisions or state (a model judge may propose, not decide)", f"results/{i}/evaluation")
        if not {"control_decisions", "state"} & set(ev["evidence_basis"]):
            r.err("ARP-016", f"{x['claim_id']} decides an action or control claim without control-decision or state evidence", f"results/{i}/evaluation")

    if top >= 2:
        # ARP-017 a tested axis can be rerun by someone else
        rep = ass.get("reproduction")
        if not rep:
            r.err("ARP-017", "an axis is at Level 2+ but assurance.reproduction is missing (test cases, initial state, deployment config, evaluator config, rerun instructions)", "assurance/reproduction")
        else:
            for k, ref in rep.items():
                if ref not in evidence:
                    r.err("ARP-017", f"reproduction.{k} cites '{ref}', which is not in the evidence manifest", f"assurance/reproduction/{k}")
        # ARP-018 test environment and fidelity
        if not ass.get("test_environment"):
            r.err("ARP-018", "an axis is at Level 2+ but assurance.test_environment is not stated", "assurance/test_environment")
        if not ass.get("fidelity"):
            r.err("ARP-018", "an axis is at Level 2+ but assurance.fidelity does not say how closely the test setting matched the deployment", "assurance/fidelity")
        # ARP-019 signed source manifest
        if not profile.get("evidence_manifest"):
            r.err("ARP-019", "an axis is at Level 2+ but the signed evidence manifest is missing", "evidence_manifest")
    m = profile.get("evidence_manifest")
    if m:
        if m["content_hash"] != sha256_of(profile["evidence"]):
            r.err("ARP-019", "evidence_manifest.content_hash is not the canonical hash of the evidence array", "evidence_manifest/content_hash")
        else:
            ok = _verify(m["public_key"], m["value"], manifest_statement(m))
            if ok is False:
                r.err("ARP-019", "the evidence manifest signature is not valid", "evidence_manifest")
            elif ok is None:
                (r.err if issued else r.warn)("ARP-019", "cryptography is not installed: the evidence manifest signature could not be checked (indeterminate)", "evidence_manifest")
        if m["public_key"] in DEMO_PUBLIC_KEYS:
            r.warn("ARP-092", f"the evidence manifest is signed with the published {DEMO_PUBLIC_KEYS[m['public_key']]}: it proves nothing", "evidence_manifest")

    # ARP-020 comparability is a flag, and only a flagged Profile carries grades
    bench = profile.get("benchmark")
    if bench is not None and not comp["flag"]:
        r.err("ARP-020", "benchmark present but comparability.flag is false: comparative results appear only on Benchmarked Profiles", "benchmark")
    if comp["flag"]:
        for k in ("environment_version", "hidden_set_version", "fidelity_statement"):
            if not comp.get(k):
                r.err("ARP-020", f"comparability.flag is true but {k} is missing", f"assurance/comparability/{k}")
        if bench is None:
            r.err("ARP-020", "comparability.flag is true but there is no benchmark result", "benchmark")
        else:
            a = bench.get("assessor") or {}
            if not (str(a.get("organisation") or "").strip() and str(a.get("accreditation_ref") or "").strip() and a.get("independent") is True):
                r.err("ARP-020", "a benchmark must name an independent, accredited assessor (organisation, accreditation_ref, independent: true)", "benchmark/assessor")
            if not bench.get("results"):
                r.err("ARP-020", "a benchmark must report at least one result", "benchmark/results")
        if top == 1:
            r.err("ARP-020", "the comparability flag is set but every production axis is Level 1: a Benchmarked Profile needs an agent that was run (preprint Table 4), and a Level 1 Profile executes nothing", "assurance/comparability")

    # ARP-030..032 action sets
    perm, proh = set(claim["actions"]["permitted"]), set(claim["actions"]["prohibited"])
    oos = set(profile["out_of_scope"].get("actions", []))
    if perm & proh:
        r.err("ARP-030", f"actions both permitted and prohibited: {sorted(perm & proh, key=lambda a: int(a[1:]))}", "claim/actions")
    missing = [a for a in ACTIONS if a not in perm | proh | oos]
    if missing:
        (r.err if issued else r.warn)("ARP-031", f"action classes not stated as permitted, prohibited or out of scope: {missing}", "claim/actions")
    if perm & oos:
        r.err("ARP-032", f"actions both permitted and out of scope: {sorted(perm & oos, key=lambda a: int(a[1:]))}", "out_of_scope/actions")
    if proh & oos:
        r.err("ARP-032", f"actions both prohibited and out of scope: {sorted(proh & oos, key=lambda a: int(a[1:]))}", "out_of_scope/actions")

    # ARP-040 / 041 tier rules
    au = claim["autonomy"]
    tier, basis = au["tier"], au["tier_basis"]
    if tier == "U":
        if headline != 1 or results:
            r.err("ARP-040", "tier U is a finding, not a claim: it cannot carry results or be issued above Level 1", "claim/autonomy/tier")
        unprof = [f for f in open_f if f["kind"] == "unprofiled"]
        if not unprof:
            r.err("ARP-040", "tier U requires an open finding of kind 'unprofiled'", "status/open_findings")
        if basis != "asserted" or "approval_quality" in au:
            r.err("ARP-040", "tier U has no evidenced tier: tier_basis must be 'asserted' and approval_quality absent", "claim/autonomy")
        if "no reliability claim" not in claim["statement"].lower():
            r.err("ARP-040", "for tier U the statement must say that no reliability claim is made", "claim/statement")
        if issued and not status.get("risk_acceptances") and not any(f.get("response") in ("remediation", "suspension") for f in unprof):
            r.err("ARP-040", "an issued tier U Profile must record a risk acceptance, or a remediation or suspension response to its 'unprofiled' finding", "status")
    if basis == "substantiated" and tier != "T2":
        r.err("ARP-041", f"tier_basis 'substantiated' is defined only for T2 in this candidate; {tier} must be 'asserted'", "claim/autonomy/tier_basis")
    if tier == "T2":
        aq = au.get("approval_quality")
        if not aq:
            r.err("ARP-041", "tier T2 requires an approval_quality block: T2 is earned by substantive approval, not by configuration", "claim/autonomy")
        elif aq["assessment"] == "reflexive":
            r.err("ARP-041", "approval quality is 'reflexive': the effective tier is T3, not T2", "claim/autonomy/approval_quality")
        elif basis == "substantiated":
            pc = prov.get("autonomy.approval_quality", {}).get("class")
            if aq["assessment"] != "substantive" or pc not in ("configuration_derived", "measured"):
                r.err("ARP-041", "T2 is marked substantiated, but approval quality is not 'substantive' on configuration-derived or measured evidence", "claim/autonomy/tier_basis")
            if aq.get("resource_displayed") is not True or not aq.get("sample_size"):
                r.err("ARP-041", "a substantiated T2 needs approvals that show the affected resource (resource_displayed: true) and a sample size above 0", "claim/autonomy/approval_quality")
            sim = [c for c in profile.get("conflicts", []) if c["kind"] in SIMULATED and axis_of(c["field_id"]) == "autonomy"]
            if sim:
                r.err("ARP-041", f"simulated or sample-marked records cannot substantiate T2 (conflict on {sim[0]['field_id']})", "claim/autonomy/tier_basis")
        if axes["autonomy"] >= 2:
            if basis != "substantiated":
                r.err("ARP-041", "the autonomy axis is at Level 2+ but T2 is only asserted: a tested T2 must be substantiated", "claim/autonomy/tier_basis")
            if aq and aq.get("habituation_catch_rate") is None:
                r.warn("ARP-041", "a tested T2 should record habituation_catch_rate (planted errors caught by approvers)", "claim/autonomy/approval_quality")

    # ARP-050 every populated claim field carries provenance
    for fid in sorted(fields):
        if fid not in prov:
            r.err("ARP-050", f"no provenance entry for {fid}", "provenance")
    for fid in sorted(set(prov) - fields):
        if prov[fid]["class"] != "absent":
            r.warn("ARP-050", f"provenance entry for {fid}, which is not a claim field (use class 'absent' to record a missing field)", f"provenance/{fid}")

    # ARP-051 cited classes cite real evidence
    for fid, p in prov.items():
        cites = p.get("citations", [])
        if p["class"] in CITED and not cites:
            r.err("ARP-051", f"{fid} is '{p['class']}' but cites no evidence", f"provenance/{fid}")
        for c in cites:
            if c["evidence_id"] not in evidence:
                r.err("ARP-051", f"{fid} cites evidence '{c['evidence_id']}', which is not in the evidence manifest", f"provenance/{fid}")

    # ARP-052 controls come from the catalogue, or are declared extensions
    catalogue = {t["id"]: t["layer"] for t in load_vocab("control-catalogue")["terms"]}
    for i, c in enumerate(claim["controls"]):
        cid = c["control_id"]
        if cid.split(".", 1)[0] != c["layer"]:
            r.err("ARP-052", f"{cid} is filed under layer '{c['layer']}'", f"claim/controls/{i}")
        if cid not in catalogue and not cid.split(".", 1)[1].startswith("x_"):
            r.err("ARP-052", f"{cid} is not in the control catalogue; extensions must use the 'x_' prefix", f"claim/controls/{i}")

    # ARP-053 / 054 the operational design domain
    odd = claim["odd"]
    uc = odd.get("use_case_id")
    if uc and not uc.startswith("ODD.x_"):
        ucs = {t["id"]: t["business_line"] for t in load_vocab("use-cases")["terms"]}
        if uc not in ucs:
            r.err("ARP-053", f"{uc} is not in vocab/use-cases.json; extensions use ODD.x_<name>", "claim/odd/use_case_id")
        elif ucs[uc] != odd["business_line"]:
            r.err("ARP-053", f"{uc} belongs to business line '{ucs[uc]}', not '{odd['business_line']}'", "claim/odd/business_line")
    if issued and not uc:
        r.warn("ARP-053", "an issued Profile should name its catalogued use case (use_case_id)", "claim/odd")
    if issued:
        for k in ("jurisdictions", "population", "data", "cost_of_failure"):
            if odd.get(k) in (None, "", []) and prov.get(f"odd.{k}", {}).get("class") != "absent":
                r.err("ARP-054", f"odd.{k} is empty: state it, or record provenance class 'absent' for it", f"claim/odd/{k}")

    # ARP-060..062 floors are pass or fail, set before any run, never averaged away
    floors = profile["floors"]
    floor_ids = {f["id"] for f in floors}
    finding_ids = {o["id"] for o in open_f}
    for f in floors:
        if f["status"] == "failed" and not any(o.get("floor_ref") == f["id"] and o["kind"] == "floor_failure" for o in open_f):
            r.err("ARP-060", f"floor '{f['id']}' failed but no open finding of kind 'floor_failure' references it", "status/open_findings")
        for ref in f.get("finding_refs", []):
            if ref not in finding_ids:
                r.err("ARP-060", f"floor '{f['id']}' refers to finding '{ref}', which is not an open finding", "floors")
    for o in open_f:
        if o.get("floor_ref") and o["floor_ref"] not in floor_ids:
            r.err("ARP-060", f"finding '{o['id']}' refers to floor '{o['floor_ref']}', which is not a floor", "status/open_findings")
    if issued:
        for f in floors:
            if f["status"] == "failed":
                r.err("ARP-061", f"floor '{f['id']}' failed: a failed floor blocks issuance", "floors")
    if top >= 2:
        if not floors:
            r.err("ARP-062", "an axis is at Level 2+ but the Profile states no floors", "floors")
        for f in floors:
            if f["status"] != "untested":
                continue
            ax = f.get("axis")
            if ax and axes[ax] >= 2:
                r.err("ARP-062", f"floor '{f['id']}' is on the '{ax}' axis, which is at Level {axes[ax]}, but it is untested", "floors")
            elif not ax and headline >= 2:
                r.err("ARP-062", f"Profile-wide floor '{f['id']}' is untested on a Level {headline} Profile", "floors")

    # ARP-070 every non-held result is accounted for
    of_claims = {o.get("claim_id") for o in open_f}
    gap_claims = {g["claim_id"] for g in gaps}
    for x in results:
        cid, d = x["claim_id"], x["disposition"]
        if d == "contradicted" and cid not in of_claims:
            r.err("ARP-070", f"contradicted claim {cid} is not listed as an open finding", "status/open_findings")
        if d in ("held_by_agent_only", "not_established") and cid not in of_claims | gap_claims:
            r.err("ARP-070", f"{d} claim {cid} is neither an accepted gap nor an open finding", "status")
    for g in gaps:
        if not any(x["claim_id"] == g["claim_id"] and x["disposition"] == g["disposition"] for x in results):
            r.err("ARP-070", f"accepted gap {g['claim_id']} does not match a result with disposition {g['disposition']}", "status/accepted_gaps")

    # ARP-080 issue date and validity window
    if issued:
        for k in ("issued_at", "valid_from", "valid_until", "evidence_as_of"):
            if not iss.get(k):
                r.err("ARP-080", f"an issued Profile requires issuance.{k}", f"issuance/{k}")
    d_iss = parse_datetime(iss["issued_at"]) if iss.get("issued_at") else None
    d_from = parse_date(iss["valid_from"]) if iss.get("valid_from") else None
    d_until = parse_date(iss["valid_until"]) if iss.get("valid_until") else None
    d_ev = parse_date(iss["evidence_as_of"]) if iss.get("evidence_as_of") else None
    for name, d in (("issued_at", d_iss), ("valid_from", d_from), ("valid_until", d_until), ("evidence_as_of", d_ev)):
        if d and d < MIN_DATE:
            r.err("ARP-080", f"issuance.{name} is before 2000-01-01: fill in the real date", f"issuance/{name}")
    if d_from and d_until and d_until <= d_from:
        r.err("ARP-080", "valid_until is not after valid_from", "issuance/valid_until")
    if d_iss and d_from and d_from < d_iss:
        r.err("ARP-080", "valid_from is before the issue date", "issuance/valid_from")
    if d_iss and d_ev and d_ev > d_iss:
        r.err("ARP-080", "evidence_as_of is later than the issue date", "issuance/evidence_as_of")
    if issued and as_of:
        if d_until and as_of > d_until:
            r.warn("ARP-080", f"expired: valid until {d_until.isoformat()}, checked as of {as_of.isoformat()}", "issuance/valid_until")
        if d_from and as_of < d_from:
            r.warn("ARP-080", f"not yet valid: valid from {d_from.isoformat()}, checked as of {as_of.isoformat()}", "issuance/valid_from")

    # ARP-081 an issued Profile names what it is about, precisely enough to invalidate it
    if issued:
        if not profile["subject"].get("deployment_version"):
            r.err("ARP-081", "an issued Profile requires subject.deployment_version", "subject/deployment_version")
        if not profile["subject"].get("models"):
            r.err("ARP-081", "an issued Profile requires subject.models (provider, model, pinned version)", "subject/models")

    # ARP-082 / 083 invalidation triggers
    void_triggers = {v["trigger"] for v in profile["invalidation"]["voids"]}
    if issued:
        want_t = list(DEFAULT_TRIGGERS)
        if any(c["layer"] == "inter_agent" for c in claim["controls"]):
            want_t.append("topology_change")
        miss_t = [t for t in want_t if t not in void_triggers]
        if miss_t:
            r.warn("ARP-082", f"changes that void the Profile do not include the default triggers {miss_t}", "invalidation/voids")
    if profile["subject"].get("platform_baseline") and "platform_baseline_void" not in void_triggers:
        r.err("ARP-083", "an anchored Profile must be void when its platform baseline is void (trigger 'platform_baseline_void')", "invalidation/voids")

    # ARP-090 the owner (and a different issuer) sign
    owner_name = iss["owner"]["name"]
    issuer = iss.get("issuer")
    if issued:
        if not issuer:
            r.err("ARP-090", "an issued Profile must name its issuer (issuance.issuer)", "issuance/issuer")
        if not any(s["role"] == "owner" and norm_name(s["name"]) == norm_name(owner_name) for s in sigs):
            r.err("ARP-090", f"an issued Profile requires the accountable owner's signature, made as '{owner_name}'", "signatures", pending=True)
        if issuer and norm_name(issuer["name"]) != norm_name(owner_name) and not any(s["role"] == "issuer" and norm_name(s["name"]) == norm_name(issuer["name"]) for s in sigs):
            r.err("ARP-090", f"the issuer '{issuer['name']}' is not the owner and has not signed (role 'issuer')", "signatures", pending=True)
    elif sigs:
        r.warn("ARP-090", "a draft carries signatures; they will be invalidated by any edit", "signatures")

    # ARP-091 / 092 signatures
    h = canonical_hash(profile)
    seen_rn, seen_rk, seen_v = set(), set(), set()
    for i, s in enumerate(sigs):
        rn, rk = (s["role"], norm_name(s["name"])), (s["role"], s["public_key"])
        if rn in seen_rn or rk in seen_rk or s["value"] in seen_v:
            r.err("ARP-091", f"signature {i} ({s['role']}, {s['name']}) duplicates another signature (same role with the same signer name or the same key)", f"signatures/{i}")
        seen_rn.add(rn); seen_rk.add(rk); seen_v.add(s["value"])
        if s["public_key"] in DEMO_PUBLIC_KEYS:
            r.warn("ARP-092", f"signature {i} ({s['role']}) uses the published {DEMO_PUBLIC_KEYS[s['public_key']]}: it proves nothing about anyone", f"signatures/{i}")
        if s["signed_hash"] != h:
            r.err("ARP-091", f"signature {i} ({s['role']}) covers {s['signed_hash'][:19]}…, but the Profile hashes to {h[:19]}…", f"signatures/{i}")
            continue
        ok = _verify(s["public_key"], s["value"], signature_statement(s))
        if ok is False:
            r.err("ARP-091", f"signature {i} ({s['role']}, {s['name']}) is not valid for its signature statement", f"signatures/{i}")
        elif ok is None:
            (r.err if issued else r.warn)("ARP-091", "cryptography is not installed: signatures could not be checked, so the result is indeterminate", f"signatures/{i}")

    # ARP-100 open conflicts on an issued Profile are carried as findings
    if issued:
        of_fields = {o.get("field_id") for o in open_f}
        for c in profile.get("conflicts", []):
            if c["state"] == "open" and c["field_id"] not in of_fields:
                r.err("ARP-100", f"open conflict on {c['field_id']} is not carried as an open finding", "status/open_findings")
    return r


def check_bytes(data, as_of=None) -> tuple[dict | None, Report]:
    """Strict load, then check. Returns (profile or None, report)."""
    try:
        p = loads_strict(data)
    except InputError as e:
        r = Report(); r.err("ARP-001", str(e)); return None, r
    return p, check(p, as_of)


# ------------------------------------------------------------------ signing

def keygen(path: str) -> None:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    key = Ed25519PrivateKey.generate()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(key.private_bytes_raw())
    print(f"wrote {path} (an unencrypted private key: keep it in your secrets store)")


def _private_key(key_path: str):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    raw = Path(key_path).read_bytes()
    if len(raw) != 32:
        raise ValueError(f"{key_path} is not a raw 32-byte Ed25519 private key")
    return Ed25519PrivateKey.from_private_bytes(raw)


def public_key_b64(key_path: str) -> str:
    return base64.b64encode(_private_key(key_path).public_key().public_bytes_raw()).decode()


class Refused(Exception):
    pass


def sign(profile: dict, role: str, name: str, key_path: str, organisation: str | None = None) -> dict:
    key = _private_key(key_path)
    out = copy.deepcopy(profile)
    if role == "issuer" and out.get("stage") != "issued":
        raise Refused("sign as owner first: the owner's signature issues the Profile, and an issuer signature made on a draft would not cover the issued Profile")
    if role == "assessor" and not organisation:
        raise Refused("an assessor signature needs --organisation (the assessor named in assurance.assessors)")
    if role in ("owner", "assessor"):
        out["stage"] = "issued"
    h = canonical_hash(out)
    for s in out.get("signatures", []):
        if s["signed_hash"] != h:
            raise Refused(f"an existing {s['role']} signature no longer covers this Profile")
        if s["role"] == role and norm_name(s["name"]) == norm_name(name):
            raise Refused(f"{name} has already signed as {role}")
        if s["role"] == role and s["public_key"] == base64.b64encode(key.public_key().public_bytes_raw()).decode():
            raise Refused(f"this key has already signed as {role}")
    sig = {"role": role, "name": name}
    if organisation:
        sig["organisation"] = organisation
    sig.update({"alg": "ed25519", "public_key": base64.b64encode(key.public_key().public_bytes_raw()).decode(), "signed_hash": h})
    sig["value"] = base64.b64encode(key.sign(signature_statement(sig))).decode()
    out.setdefault("signatures", []).append(sig)
    return out


def sign_manifest(profile: dict, signer: str, key_path: str) -> dict:
    if profile.get("signatures"):
        raise Refused("the Profile is already signed; sign the evidence manifest before the owner signs")
    key = _private_key(key_path)
    out = copy.deepcopy(profile)
    m = {"content_hash": sha256_of(out["evidence"]), "signer": signer,
         "public_key": base64.b64encode(key.public_key().public_bytes_raw()).decode()}
    m["value"] = base64.b64encode(key.sign(manifest_statement(m))).decode()
    out["evidence_manifest"] = m
    return out


def redact_prepare(profile: dict, suffix: str = "-redacted-1") -> tuple[dict, str]:
    """Start a redacted derivative (DISCLOSURE.md): a new draft without signatures, a new profile_id, and a limitation
    saying it is a redacted derivative. Returns (derivative, canonical hash of the original). The link to the original
    is kept outside the derivative, so a recipient cannot use the hash to test guesses about redacted content."""
    if not suffix or not re.fullmatch(r"[-._A-Za-z0-9]+", suffix):
        raise Refused("--suffix must be letters, digits, '.', '_' or '-'")
    original = canonical_hash(profile)
    out = copy.deepcopy(profile)
    out["signatures"] = []
    out["stage"] = "draft"
    out["profile_id"] = f"{profile['profile_id']}{suffix}"
    out.setdefault("status", {}).setdefault("limitations", []).append(
        f"Redacted derivative of Profile {profile['profile_id']}. Redacted text and paths cannot be checked by the recipient; "
        "open findings, failed floors and contradicted results are not redacted.")
    return out, original


# ------------------------------------------------------------------ CLI

def _write(profile, out_path):
    Path(out_path).write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check"); c.add_argument("profile"); c.add_argument("--json", action="store_true")
    c.add_argument("--as-of", help="report expiry against this date (YYYY-MM-DD)")
    h = sub.add_parser("hash"); h.add_argument("profile")
    s = sub.add_parser("sign"); s.add_argument("profile"); s.add_argument("--role", required=True, choices=["owner", "issuer", "assessor"])
    s.add_argument("--name", required=True); s.add_argument("--organisation"); s.add_argument("--key", required=True)
    g = s.add_mutually_exclusive_group(required=True); g.add_argument("--out"); g.add_argument("--in-place", action="store_true")
    m = sub.add_parser("sign-manifest"); m.add_argument("profile"); m.add_argument("--signer", required=True); m.add_argument("--key", required=True)
    g2 = m.add_mutually_exclusive_group(required=True); g2.add_argument("--out"); g2.add_argument("--in-place", action="store_true")
    k = sub.add_parser("keygen"); k.add_argument("path")
    pk = sub.add_parser("pubkey"); pk.add_argument("key")
    rp = sub.add_parser("redact-prepare", help="start a redacted derivative of a Profile (DISCLOSURE.md)")
    rp.add_argument("profile"); rp.add_argument("--out", required=True); rp.add_argument("--suffix", default="-redacted-1")
    a = ap.parse_args(argv)

    want_json = getattr(a, "json", False)

    def tool_error(msg):
        if want_json:
            print(json.dumps({"conformant": None, "error": msg, "findings": []}, indent=2))
        else:
            print(f"error: {msg}", file=sys.stderr)
        return 3

    try:
        if a.cmd == "keygen":
            keygen(a.path); return 0
        if a.cmd == "pubkey":
            print(public_key_b64(a.key)); return 0
        try:
            data = Path(a.profile).read_bytes()
        except OSError as e:
            return tool_error(f"cannot read {a.profile}: {e.strerror}")
        as_of = None
        if getattr(a, "as_of", None):
            as_of = parse_date(a.as_of)
            if as_of is None:
                print("error: --as-of must be a date YYYY-MM-DD", file=sys.stderr); return 2
        profile, rep = check_bytes(data, as_of)
        if a.cmd == "redact-prepare":
            if profile is None:
                print(f"refused: ARP-001 {rep.errors[0]['message']}", file=sys.stderr); return 1
            try:
                deriv, original = redact_prepare(profile, a.suffix)
            except Refused as e:
                print(f"refused: {e}", file=sys.stderr); return 1
            if os.path.exists(a.out):
                print(f"refused: {a.out} exists; choose another --out", file=sys.stderr); return 1
            _write(deriv, a.out)
            link = a.out + ".internal-link.txt"
            Path(link).write_text(f"INTERNAL: do not send with the redacted Profile.\nredacted: {deriv['profile_id']}\n"
                                  f"original: {profile['profile_id']}\noriginal canonical hash: {original}\n", encoding="utf-8")
            print(f"wrote {a.out} (draft, no signatures, profile_id {deriv['profile_id']}); keep {link} internally")
            print("next: redact; if you changed evidence paths, sign-manifest; check; then the owner signs (and the assessor, for any Level 3 axis)")
            return 0
        if a.cmd == "hash":
            if profile is None:
                print(f"error: {rep.errors[0]['message']}", file=sys.stderr); return 1
            print(canonical_hash(profile)); return 0
        if a.cmd in ("sign", "sign-manifest"):
            if profile is None:
                print(f"refused: ARP-001 {rep.errors[0]['message']}", file=sys.stderr); return 1
            out_path = a.profile if a.in_place else a.out
            if a.cmd == "sign-manifest":
                try:
                    signed = sign_manifest(profile, a.signer, a.key)
                except Refused as e:
                    print(f"refused: {e}", file=sys.stderr); return 1
                _write(signed, out_path); print(f"evidence manifest signed: {signed['evidence_manifest']['content_hash']}"); return 0
            # a Profile is only signed once it would conform as issued
            trial = copy.deepcopy(profile)
            if a.role in ("owner", "assessor"):
                trial["stage"] = "issued"
            pre = [e for e in check(trial).errors if e["path"] != "signatures"]
            if pre:
                for e in pre:
                    print(f"refused: {e['rule']} {e['path'] or '-'}: {e['message']}", file=sys.stderr)
                return 1
            # the signer must be the party the Profile names for that role
            iss = profile.get("issuance") or {}
            if a.role == "owner" and norm_name(a.name) != norm_name(((iss.get("owner") or {}).get("name")) or ""):
                print(f"refused: ARP-090 the owner signs as the named accountable owner '{(iss.get('owner') or {}).get('name')}', not '{a.name}'", file=sys.stderr); return 1
            if a.role == "issuer":
                inm = (iss.get("issuer") or {}).get("name")
                if not inm or norm_name(a.name) != norm_name(inm):
                    print(f"refused: ARP-090 the issuer signs as the named issuer '{inm}', not '{a.name}'", file=sys.stderr); return 1
            if a.role == "assessor":
                orgs = {str(v.get("organisation")) for v in ((profile.get("assurance") or {}).get("assessors") or {}).values()
                        if isinstance(v, dict) and v.get("role") == "independent_assessor"}
                if a.organisation not in orgs:
                    print(f"refused: ARP-014 '{a.organisation}' is not the independent assessor of any Level 3 axis (assurance.assessors)", file=sys.stderr); return 1
            try:
                signed = sign(profile, a.role, a.name, a.key, a.organisation)
            except Refused as e:
                print(f"refused: {e}", file=sys.stderr); return 1
            # the signed file is written only if it conforms, apart from signatures still to be added
            post = [e for e in check(signed).errors if not e.get("pending_signature")]
            if post:
                for e in post:
                    print(f"refused: {e['rule']} {e['path'] or '-'}: {e['message']}", file=sys.stderr)
                print("refused: nothing was written", file=sys.stderr)
                return 1
            _write(signed, out_path)
            print(f"signed as {a.role}: {signed['signatures'][-1]['signed_hash']} -> {out_path}")
            return 0
        if want_json:
            print(json.dumps({"conformant": not rep.errors, "spec": SPEC_ID, "stage": (profile or {}).get("stage"),
                              "headline_level": ((profile or {}).get("assurance") or {}).get("headline") if isinstance((profile or {}).get("assurance"), dict) else None,
                              "findings": rep.items}, indent=2, ensure_ascii=False))
        else:
            for i in rep.items:
                print(f"{i['severity'].upper():7} {i['rule']:8} {i['path'] or '-'}: {i['message']}")
            print(("CONFORMANT" if not rep.errors else "NOT CONFORMANT") +
                  f" ({len(rep.errors)} error(s), {len(rep.items) - len(rep.errors)} warning(s)) against {SPEC_ID}")
        return 0 if not rep.errors else 1
    except Exception as e:  # an unexpected failure is a tool error, never a verdict
        return tool_error(f"{type(e).__name__}: {e}")


if __name__ == "__main__":
    sys.exit(main())
