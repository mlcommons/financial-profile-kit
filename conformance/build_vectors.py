#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Regenerate the conformance vectors (arp/1.0-rc2) from the worked examples.

Every invalid vector is a valid Profile with ONE defect, labelled with the rule(s) it must
trip. A few are raw files (bad bytes, duplicate names) that no JSON library can write.
Each parsable vector also records its canonical hash (RFC 8785) so that implementations can
test their canonical form. Re-run after changing the examples or the spec:

  python3 build_vectors.py

The output is deterministic (Ed25519 signatures are deterministic).
"""
import base64, copy, json
from pathlib import Path
from arp_conform import sign, sign_manifest, canonical_hash, loads_strict, InputError, _private_key, signature_statement

HERE = Path(__file__).resolve().parent
EX, OUT = HERE.parent / "examples", HERE / "vectors"
OWNER_KEY = str(EX / "demo-keys" / "DEMO-ONLY-owner.key")
ASSESSOR_KEY = str(EX / "demo-keys" / "DEMO-ONLY-assessor.key")
ASSESSOR_ORG = "Example Assurance LLP (fictional)"
ASSESSOR_NAME = "Riley Example (fictional)"


def load(n): return json.loads((EX / n).read_text(encoding="utf-8"))
def draft(p):
    p = copy.deepcopy(p); p["stage"] = "draft"; p["signatures"] = []; return p


L1 = load("l1-aml-alert-triage.draft.json")
L1I = load("l1-aml-alert-triage.issued.json")
L2I = load("l2-open-banking.json")
L2 = draft(L2I)
OWNER1 = L1I["issuance"]["owner"]["name"]
OWNER2 = L2I["issuance"]["owner"]["name"]

manifest = []


def _record(kind, name, text, expect_rules, note):
    path = OUT / kind / f"{name}.json"
    path.write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))
    try:
        h = canonical_hash(loads_strict(path.read_bytes()))
    except (InputError, ValueError, TypeError):
        h = None
    manifest.append({"file": f"{kind}/{name}.json", "expect": "pass" if kind == "valid" else "fail",
                     "error_rules": sorted(set(expect_rules)), "canonical_hash": h, "note": note})


def emit(kind, name, profile, expect_rules=(), note=""):
    _record(kind, name, json.dumps(profile, indent=2, ensure_ascii=False) + "\n", expect_rules, note)


def emit_raw(name, data, rules, note):
    _record("invalid", name, data, rules, note)


def mut(base, fn):
    p = copy.deepcopy(base); fn(p); return p


def resign(p, name=None, key=OWNER_KEY):
    """Re-issue p with a fresh owner signature (so only the intended defect remains)."""
    p = copy.deepcopy(p); p["signatures"] = []
    return sign(p, "owner", name or p["issuance"]["owner"]["name"], key)


def issue(base, fn=lambda p: None, name=None):
    p = mut(base, fn); return resign(p, name)


for d in ("valid", "invalid"):
    (OUT / d).mkdir(parents=True, exist_ok=True)  # files are overwritten; the manifest is authoritative

# ---------------------------------------------------------------- valid
emit("valid", "v01-l1-draft", L1, note="Builder output awaiting the owner")
emit("valid", "v02-l1-issued", L1I, note="Level 1, owner-signed, open conflict carried as a finding (DEMO-ONLY key: ARP-092 warning)")
emit("valid", "v03-l2-issued", L2I, note="Level 2, one contradicted control, one accepted gap, signed evidence manifest")


def tier_u(p):
    au = p["claim"]["autonomy"]
    au["tier"] = "U"; au["tier_basis"] = "asserted"; au.pop("approval_quality"); p["provenance"].pop("autonomy.approval_quality")
    p["claim"]["statement"] = ("On the evidence supplied, no reliability claim is made for the alert-triage agent: in batch mode its "
                               "fallback and envelope are unspecified, so its autonomy is recorded as U (unprofiled). This is a Level 1 draft.")
    p["status"]["open_findings"].append({"id": "of-u", "kind": "unprofiled", "note": "Fallback and envelope unspecified for batch mode.", "response": "remediation"})
V04 = mut(L1, tier_u)
emit("valid", "v04-tier-u", V04, note="U is recorded as a finding, with no reliability claim")


def mixed(p):
    p["assurance"]["axes"]["autonomy"] = 1; p["assurance"]["headline"] = 1
    p["assurance"]["coverage"].pop("autonomy"); p["assurance"]["disclosures"] = ["level1_untested", "self_tested", "not_comparable"]
    p["provenance"]["autonomy.approval_quality"] = {"class": "configuration_derived", "citations": [{"evidence_id": "e4", "locator": "approval_records.csv"}]}
    p["results"] = [r for r in p["results"] if not r["field_id"].startswith("autonomy.")]
emit("valid", "v05-mixed-axis", mut(L2, mixed), note="Level 2 on three axes, Level 1 on autonomy: headline is the minimum")


def warn31(p):
    p["claim"]["actions"]["prohibited"].remove("A12"); p["provenance"].pop("actions.A12")
emit("valid", "v06-warning-unstated-class", mut(L1, warn31), note="Draft, conformant with warning ARP-031")


def lvl3(p):
    p["assurance"]["axes"]["controls"] = 3
    p["assurance"]["assessors"]["controls"] = {"role": "independent_assessor", "organisation": ASSESSOR_ORG, "report": "a1"}
    p["assurance"]["disclosures"] = ["self_tested", "independently_verified", "not_comparable"]
    p["evidence"].append({"id": "a1", "path": "assurance/controls_verification_report.pdf",
                          "content_hash": "sha256:" + "a1" * 32, "artifact_class": "assessor_report"})
L3D = sign_manifest(mut(L2, lvl3) | {"evidence_manifest": None}, OWNER2, OWNER_KEY)
L3O = sign(L3D, "owner", OWNER2, OWNER_KEY)
L3 = sign(L3O, "assessor", ASSESSOR_NAME, ASSESSOR_KEY, ASSESSOR_ORG)
emit("valid", "v07-l3-controls-axis", L3, note="Level 3 on the controls axis only: owner and assessor signatures, assessor report")


def canon(p):
    p["claim"]["autonomy"]["approval_quality"]["median_seconds_to_approve"] = 212.0
    p["claim"]["controls"][0]["configuration"] = {"scope": "accounts named in consent", "é": 1.5, "😀": "astral key", "Z": 0.000001, "max": 9007199254740991}
    p["evidence"][0]["bytes"] = 4096
V08 = mut(L2, canon) | {"evidence_manifest": None}
V08 = sign_manifest(V08, OWNER2, OWNER_KEY)
V08 = sign(V08, "owner", OWNER2, OWNER_KEY)
emit("valid", "v08-canonical-form", V08, note="Signed over RFC 8785 canonical form: 212.0, 1e-6, non-ASCII and astral member names, 2^53-1")


def anchored(p):
    p["subject"]["platform_baseline"] = {"profile_id": "examplebank.platform.agents.baseline", "version": "2026.09",
                                         "content_hash": "sha256:" + "b2" * 32}
    p["invalidation"]["voids"].append({"trigger": "platform_baseline_void", "description": "The bank's agent platform baseline is voided or replaced."})
V10 = mut(L1, anchored)
emit("valid", "v09-anchored-to-platform", V10, note="Anchored to a platform baseline; void if the parent is void")
emit("valid", "v10-owner-name-whitespace", resign(L1I, name="  " + OWNER1.replace(" ", "  ") + " "), note="Signer names compare after NFC and whitespace normalisation")


def raw_sig(p, role, name, key_path):
    """Append a signature without the signer's refusals (to build defective vectors)."""
    p = copy.deepcopy(p); key = _private_key(key_path)
    sig = {"role": role, "name": name, "alg": "ed25519",
           "public_key": base64.b64encode(key.public_key().public_bytes_raw()).decode(), "signed_hash": canonical_hash(p)}
    sig["value"] = base64.b64encode(key.sign(signature_statement(sig))).decode()
    p["signatures"].append(sig); return p

# ---------------------------------------------------------------- invalid (one defect each)
I = lambda name, base, fn, rules, note: emit("invalid", name, mut(base, fn), rules, note)
II = lambda name, base, fn, rules, note: emit("invalid", name, issue(base, fn), rules, note)  # mutate, then re-sign

I("i01-schema-missing-statement", L1, lambda p: p["claim"].pop("statement"), ["ARP-001"], "structure")
I("i02-headline-not-minimum", L2, lambda p: p["assurance"].update(headline=1), ["ARP-010"], "headline must equal min of axes")
I("i03-measured-at-level-1", L1, lambda p: p["provenance"].update({"actions.A1": {"class": "measured", "citations": [{"evidence_id": "e3"}]}}), ["ARP-011"], "Level 1 executes nothing")
def i04(p):
    p["results"] = [r for r in p["results"] if not r["field_id"].startswith("odd.")]
    p["provenance"]["odd.use_case"] = {"class": "document_derived", "citations": [{"evidence_id": "e1", "locator": "§1 Scope"}]}
I("i04-level-2-judged-nothing", L2, i04, ["ARP-012"], "odd axis claims Level 2 with no judged result")
I("i05-result-on-level-1-axis", L1, lambda p: p.update(results=[{"claim_id": "x", "field_id": "actions.A1", "disposition": "held", "evidence_refs": ["e3"], "evaluation": {"method": "deterministic", "tool": "t", "version": "1", "evidence_basis": ["state"], "review_status": "unreviewed"}}]), ["ARP-013"], "results need an axis at Level 2+")
def i06(p):
    p["assurance"]["axes"]["controls"] = 3; p["assurance"]["disclosures"].append("independently_verified")
I("i06-level-3-not-independent", L2, i06, ["ARP-014"], "Level 3 without an independent assessor")
I("i07-grades-without-flag", L1, lambda p: p.update(benchmark={"grade": "B"}), ["ARP-020"], "comparative results only on Benchmarked Profiles")
def i08(p):
    p["assurance"]["comparability"].update(flag=True); p["assurance"]["disclosures"].append("benchmark_not_production")
I("i08-flag-without-environment", L1, i08, ["ARP-020"], "flag needs environment, hidden set, fidelity statement and a benchmark")
I("i09-permitted-and-prohibited", L1, lambda p: p["claim"]["actions"]["prohibited"].append("A1"), ["ARP-030"], "A1 in both sets")
I("i10-permitted-and-out-of-scope", L1, lambda p: p["out_of_scope"].update(actions=["A2"]), ["ARP-032"], "A2 permitted and out of scope")
def i11(p):
    p["claim"]["autonomy"]["tier"] = "U"; p["claim"]["autonomy"]["tier_basis"] = "asserted"; p["claim"]["autonomy"].pop("approval_quality")
    p["provenance"].pop("autonomy.approval_quality")
I("i11-tier-u-without-finding", L1, i11, ["ARP-040"], "U must be carried as a finding")
I("i12-t2-without-approval-quality", L1, lambda p: (p["claim"]["autonomy"].pop("approval_quality"), p["provenance"].pop("autonomy.approval_quality")), ["ARP-041"], "T2 is earned by evidence")
I("i13-t2-reflexive-approval", L1, lambda p: p["claim"]["autonomy"]["approval_quality"].update(assessment="reflexive"), ["ARP-041"], "reflexive approval means effective T3")
I("i14-missing-provenance", L1, lambda p: p["provenance"].pop("odd.use_case"), ["ARP-050"], "every claim field carries provenance")
I("i15-derived-without-citation", L1, lambda p: p["provenance"]["controls.tool.action_allowlists"].update(citations=[]), ["ARP-051"], "derived classes must cite")
I("i16-citation-not-in-manifest", L1, lambda p: p["provenance"]["odd.use_case"]["citations"].append({"evidence_id": "e99"}), ["ARP-051"], "citations resolve to the manifest")
def i17(p):
    p["claim"]["controls"].append({"control_id": "tool.magic_firewall", "layer": "tool", "present": True})
    p["provenance"]["controls.tool.magic_firewall"] = {"class": "owner_attested"}
I("i17-control-not-in-catalogue", L1, i17, ["ARP-052"], "unknown control without x_ prefix")
I("i18-failed-floor-not-disclosed", L2, lambda p: p["floors"][2].update(status="failed"), ["ARP-060"], "a failed floor is never averaged away")
I("i19-contradiction-not-disclosed", L2, lambda p: p["status"].update(open_findings=[]), ["ARP-070"], "contradicted claims are open findings")
I("i20-gap-not-accepted", L2, lambda p: p["status"].update(accepted_gaps=[]), ["ARP-070"], "held_by_agent_only must be accepted or open")
I("i21-validity-inverted", L1, lambda p: p["issuance"].update(valid_from="2026-10-01", valid_until="2026-09-01"), ["ARP-080"], "validity window")
def i22(p):
    p["stage"] = "issued"; p["issuance"].update(issued_at="2026-09-22T10:00:00Z", valid_from="2026-09-22", valid_until="2026-10-22")
I("i22-issued-unsigned", L1, i22, ["ARP-090"], "issued needs the owner's signature")
I("i23-edited-after-signing", L2I, lambda p: p["claim"].update(statement=p["claim"]["statement"] + " Also safe for business accounts."), ["ARP-091"], "one changed byte breaks the signature")
def i24(p):
    s = p["signatures"][0]; v = bytearray(base64.b64decode(s["value"])); v[0] ^= 1
    s["value"] = base64.b64encode(bytes(v)).decode()
I("i24-forged-signature", L2I, i24, ["ARP-091"], "signature value is not valid")
def i25(p):
    i22(p); p["status"]["open_findings"] = []
I("i25-open-conflict-hidden", L1, i25, ["ARP-090", "ARP-100"], "open conflicts on an issued Profile are findings")
I("i26-placeholder-left", L1, lambda p: p["claim"]["autonomy"]["modifiers"].update(accountability="TODO"), ["ARP-002"], "no unfilled placeholders")
I("i27-result-evidence-missing", L2, lambda p: p["results"][0].update(evidence_refs=["t99"]), ["ARP-013"], "result evidence resolves to the manifest")
I("i28-result-not-a-claim-field", L2, lambda p: (p["results"][0].update(field_id="actions.A13"), p["provenance"].update({"actions.A9": {"class": "configuration_derived", "citations": [{"evidence_id": "e3"}]}})), ["ARP-013"], "a result tests a field of the claim")
I("i29-disclosure-missing", L1, lambda p: p["assurance"]["disclosures"].remove("level1_untested"), ["ARP-015"], "Level 1 carries the untested disclosure")
I("i30-t2-asserted-at-level-2", L2, lambda p: p["claim"]["autonomy"].update(tier_basis="asserted"), ["ARP-041"], "a tested T2 must be substantiated")
I("i31-coverage-overstated", L2, lambda p: p["assurance"]["coverage"]["actions"].update(tested=12, judged=12), ["ARP-012"], "coverage must match the results")
I("i32-odd-field-without-provenance", L1, lambda p: p["provenance"].pop("odd.jurisdictions"), ["ARP-050"], "every populated claim field carries provenance")
def i33(p):
    i22(p); p["subject"]["models"] = []
I("i33-issued-without-model-identity", L1, i33, ["ARP-081", "ARP-090"], "an issued Profile names its models")
I("i34-t2-substantiated-without-evidence", L1, lambda p: p["claim"]["autonomy"]["approval_quality"].update(assessment="not_assessed"), ["ARP-041"], "substantiated T2 needs substantive approval evidence")
JUDGE = {"provider": "ExampleAI (fictional)", "model": "judge-model", "version": "2026-06-01"}
I("i35-model-judge-decides-control", L2, lambda p: p["results"][1]["evaluation"].update(method="model_judged", judge_model=JUDGE, evidence_basis=["traces", "agent_output"]), ["ARP-016"], "a model judge may propose, not decide, a control claim")
I("i36-reproduction-missing", L2, lambda p: p["assurance"].pop("reproduction"), ["ARP-017"], "Level 2 needs a rerun package")
I("i37-reproduction-not-in-manifest", L2, lambda p: p["assurance"]["reproduction"].update(initial_state="r99"), ["ARP-017"], "rerun package resolves to the manifest")
I("i38-model-judge-unnamed", L2, lambda p: p["results"][3]["evaluation"].update(method="hybrid"), ["ARP-016"], "a model judge must be named and pinned")

# ---- ARP-001: strict JSON and exact structure
l1_text = json.dumps(L1, indent=2, ensure_ascii=False)
emit_raw("i39-duplicate-member-name", l1_text.replace('"claim": {\n', '"claim": {\n    "statement": "This agent is certified safe for all business accounts and payments.",\n', 1), ["ARP-001"], "duplicate names: readers disagree on which value counts")
I("i40-number-not-exact", L1, lambda p: p["evidence"][0].update(bytes=2 ** 53), ["ARP-001"], "numbers of magnitude 2^53 or more cannot be represented exactly")
I("i41-date-not-padded", L1, lambda p: p["issuance"].update(evidence_as_of="2026-9-20"), ["ARP-001"], "dates are YYYY-MM-DD")
I("i42-date-not-a-date", L1, lambda p: p["issuance"].update(evidence_as_of="2026-13-45"), ["ARP-001"], "dates must be real calendar dates")
I("i43-pattern-trailing-newline", L1, lambda p: p.update(profile_id=p["profile_id"] + "\n"), ["ARP-001"], "patterns match the whole string")
I("i44-inherited-property-name", L1, lambda p: p.update(constructor={}), ["ARP-001"], "no additional properties, whatever their name")
I("i45-wrong-enum-value", L1, lambda p: p.update(stage="final"), ["ARP-001"], "enumerated values only")
I("i46-wrong-spec-identifier", L1, lambda p: p.update(spec="arp/1.0"), ["ARP-001"], "a release-candidate Profile says so")
emit_raw("i47-nan", l1_text.replace('"sample_size": 40', '"sample_size": NaN', 1), ["ARP-001"], "NaN is not JSON")
emit_raw("i48-unpaired-surrogate", l1_text.replace('"Agent that works', '"\\ud800 Agent that works', 1), ["ARP-001"], "strings must be valid Unicode")
emit_raw("i49-not-an-object", "[" + l1_text + "]\n", ["ARP-001"], "a Profile is a JSON object")
emit_raw("i50-not-utf8", l1_text.encode("utf-8").replace("Retail customers".encode(), "Retail customers\xe9".encode("latin-1"), 1), ["ARP-001"], "a Profile is UTF-8")
I("i51-signature-not-base64", L1I, lambda p: p["signatures"][0].update(value="!" * 86 + "=="), ["ARP-001"], "signature values are base64")
I("i52-judge-model-free-text", L2, lambda p: p["results"][3]["evaluation"].update(method="hybrid", judge_model="gpt"), ["ARP-001"], "a model judge is named as provider, model and pinned version")

# ---- ARP-002 / 003
I("i53-placeholder-tbd", L1, lambda p: p["claim"]["odd"].update(population="tbd"), ["ARP-002"], "TBD is a placeholder in any case")
I("i54-placeholder-joined", L1, lambda p: p["claim"]["autonomy"]["modifiers"].update(accountability="TODO_owner"), ["ARP-002"], "TODO joined by an underscore is still a placeholder")
II("i55-angle-placeholder-issued", L1I, lambda p: p["subject"]["models"][0].update(provider="<model provider>"), ["ARP-002"], "angle-bracket placeholders cannot be issued")
II("i56-issued-without-vocab-versions", L1I, lambda p: p.pop("vocab_versions"), ["ARP-003"], "an issued Profile records its vocabulary versions")

# ---- ARP-011 .. 020
I("i57-measured-without-result", L2, lambda p: p["provenance"].update({"actions.A1": {"class": "measured", "citations": [{"evidence_id": "t1"}]}}), ["ARP-011"], "only an executed test confers 'measured'")
I("i58-coverage-entry-missing", L2, lambda p: p["assurance"]["coverage"].pop("odd"), ["ARP-012"], "a tested axis shows its coverage")
I("i59-judged-result-without-evidence", L2, lambda p: p["results"][0].update(evidence_refs=[]), ["ARP-013"], "a judged result cites evidence")
I("i60-l3-issued-without-assessor-signature", L3O, lambda p: None, ["ARP-014"], "an issued Level 3 Profile is signed by its assessor")
def i61(p):
    p["assurance"]["assessors"]["odd"] = {"role": "independent_assessor", "organisation": ASSESSOR_ORG, "report": "t4"}
I("i61-level-2-axis-with-independent-assessor", L2, i61, ["ARP-014"], "independent testing is Level 3")
I("i62-l3-assessor-without-report", L3D, lambda p: p["assurance"]["assessors"]["controls"].update(report=None), ["ARP-014"], "a Level 3 assessor cites its signed report")
emit("invalid", "i63-assessor-signed-with-owner-key", sign(L3O, "assessor", ASSESSOR_NAME, OWNER_KEY, ASSESSOR_ORG), ["ARP-014"], "the assessor signs with its own key")
I("i64-unsupported-disclosure", L1, lambda p: p["assurance"]["disclosures"].append("self_tested"), ["ARP-015"], "disclosures match the levels exactly")
I("i65-control-claim-without-state-evidence", L2, lambda p: p["results"][0]["evaluation"].update(evidence_basis=["traces"]), ["ARP-016"], "boundaries rest on control decisions or state")
I("i66-test-environment-missing", L2, lambda p: p["assurance"].update(test_environment=None), ["ARP-018"], "a tested Profile states its test environment")
I("i67-fidelity-missing", L2, lambda p: p["assurance"].pop("fidelity"), ["ARP-018"], "a tested Profile states environment fidelity")
I("i68-evidence-manifest-missing", L2, lambda p: p.pop("evidence_manifest"), ["ARP-019"], "Level 2 needs signed inputs")
I("i69-evidence-manifest-stale", L2, lambda p: p["evidence"].append({"id": "t6", "path": "runs/extra.jsonl", "content_hash": "sha256:" + "c3" * 32, "artifact_class": "test_output"}), ["ARP-019"], "the manifest covers the evidence as listed")
def i70(p):
    p["assurance"]["comparability"].update(flag=True, environment_version="ref-env 1.0", hidden_set_version="hs-2026-09", fidelity_statement="Reference ODD for retail alert triage")
    p["assurance"]["disclosures"].append("benchmark_not_production")
    p["benchmark"] = {"assessor": {"organisation": "Example Benchmarks Ltd (fictional)", "accreditation_ref": "ACC-0001", "independent": False}, "results": [{"metric": "boundary_detection_rate", "value": 0.92}]}
I("i70-benchmark-not-independent", L1, i70, ["ARP-020"], "a benchmark is run by an independent, accredited assessor")

# ---- ARP-031 / 032 / 040 / 041
II("i71-issued-class-unstated", L1I, warn31, ["ARP-031"], "an issued Profile states all twelve classes")
I("i72-prohibited-and-out-of-scope", L1, lambda p: p["out_of_scope"].update(actions=["A12"]), ["ARP-032"], "A12 prohibited and out of scope")
I("i73-tier-u-with-approval-quality", V04, lambda p: (p["claim"]["autonomy"].update(approval_quality={"assessment": "not_assessed"}), p["provenance"].update({"autonomy.approval_quality": {"class": "owner_attested"}})), ["ARP-040"], "U has no evidenced tier")
I("i74-tier-u-claims-reliability", V04, lambda p: p["claim"].update(statement=L1["claim"]["statement"]), ["ARP-040"], "a U statement makes no reliability claim")
II("i75-tier-u-issued-without-response", V04 | {"stage": "issued", "issuance": L1I["issuance"]}, lambda p: p["status"]["open_findings"][-1].pop("response"), ["ARP-040"], "an issued U records remediation, suspension or a risk acceptance")
I("i76-substantiated-non-t2", L1, lambda p: p["claim"]["autonomy"].update(tier="T3"), ["ARP-041"], "substantiated is defined for T2 only")
I("i77-t2-resource-not-displayed", L1, lambda p: p["claim"]["autonomy"]["approval_quality"].update(resource_displayed=False), ["ARP-041"], "T2: the approver sees the affected resource")
I("i78-t2-simulated-evidence", L1, lambda p: p["conflicts"].append({"field_id": "autonomy.approval_quality", "kind": "simulated_evidence", "state": "resolved", "resolution_note": "Records marked SAMPLE replaced."}), ["ARP-041"], "simulated records cannot substantiate, even once resolved")

# ---- ARP-052 .. 062
I("i79-control-wrong-layer", L1, lambda p: p["claim"]["controls"][1].update(layer="harness"), ["ARP-052"], "a control sits under its own layer")
I("i80-use-case-unknown", L1, lambda p: p["claim"]["odd"].update(use_case_id="ODD.99"), ["ARP-053"], "use cases come from the vocabulary")
I("i81-use-case-wrong-business-line", L1, lambda p: p["claim"]["odd"].update(use_case_id="ODD.1"), ["ARP-053"], "a catalogued use case fixes its business line")
II("i82-issued-odd-population-missing", L1I, lambda p: (p["claim"]["odd"].pop("population"), p["provenance"].pop("odd.population")), ["ARP-054"], "an issued Profile states the population, or records it as absent")
I("i83-floor-refers-to-missing-finding", L2, lambda p: p["floors"][0].update(finding_refs=["of-99"]), ["ARP-060"], "floor and finding links resolve")
def i84(p):
    p["floors"][2]["status"] = "failed"
    p["status"]["open_findings"].append({"id": "of-2", "kind": "floor_failure", "floor_ref": "no_funds_movement", "note": "A9 executed in one run."})
II("i84-issued-with-failed-floor", L2I, i84, ["ARP-061"], "a failed floor blocks issuance")
I("i85-tested-profile-without-floors", L2, lambda p: p.update(floors=[]), ["ARP-062"], "a tested Profile states its floors")
I("i86-untested-floor-on-tested-axis", L2, lambda p: p["floors"][2].update(status="untested"), ["ARP-062"], "floors on tested axes are tested")
I("i87-accepted-gap-without-result", L2, lambda p: p["status"]["accepted_gaps"].append({"claim_id": "c-x", "disposition": "not_established", "reason": "n/a", "accepted_by": OWNER2}), ["ARP-070"], "every accepted gap matches a result")

# ---- ARP-080 .. 083
II("i88-issued-without-expiry", L1I, lambda p: p["issuance"].update(valid_until=None), ["ARP-080"], "an issued Profile expires")
II("i89-evidence-after-issue", L1I, lambda p: p["issuance"].update(evidence_as_of=(__import__("datetime").date.fromisoformat(p["issuance"]["issued_at"][:10]) + __import__("datetime").timedelta(days=8)).isoformat()), ["ARP-080"], "evidence cannot post-date issue")
I("i90-sentinel-date", L1, lambda p: p["issuance"].update(evidence_as_of="1970-01-01"), ["ARP-080"], "fill in the real date")
II("i91-backdated-validity", L1I, lambda p: p["issuance"].update(valid_from="2026-09-01"), ["ARP-080"], "validity starts on or after the issue date")
II("i92-issued-without-deployment-version", L1I, lambda p: p["subject"].update(deployment_version=None), ["ARP-081"], "an issued Profile names its deployment version")
I("i93-anchored-without-baseline-trigger", V10, lambda p: p["invalidation"]["voids"].pop(), ["ARP-083"], "an anchored Profile is void if its parent is void")

# ---- ARP-090 .. 091
emit("invalid", "i94-owner-signed-under-another-name", resign(L1I, name="Someone Else (fictional)"), ["ARP-090"], "the owner signs as the named owner")
II("i95-issued-without-issuer", L1I, lambda p: p["issuance"].pop("issuer"), ["ARP-090"], "an issued Profile names its issuer")
II("i96-issuer-not-signed", L1I, lambda p: p["issuance"]["issuer"].update(name="Casey Example (fictional)"), ["ARP-090"], "an issuer other than the owner signs too")
I("i97-duplicate-signature", L1I, lambda p: p["signatures"].append(copy.deepcopy(p["signatures"][0])), ["ARP-091"], "no signature twice")
I("i98-signer-organisation-edited", L1I, lambda p: p["signatures"][0].update(organisation="Example Bank plc (fictional)"), ["ARP-091"], "the signature covers its own role, name and organisation")
I("i99-signature-wrong-key", L1I, lambda p: p["signatures"][0].update(public_key=L3["signatures"][1]["public_key"]), ["ARP-091"], "the signature is valid only for its own key")

# ---- W5 verification fixes
def bench_ok(p, independent=True, accreditation="ACC-0001"):
    p["assurance"]["comparability"].update(flag=True, environment_version="ref-env 1.0", hidden_set_version="hs-2026-09", fidelity_statement="Reference ODD for retail alert triage")
    p["assurance"]["disclosures"].append("benchmark_not_production")
    p["benchmark"] = {"assessor": {"organisation": "Example Benchmarks Ltd (fictional)", "accreditation_ref": accreditation, "independent": independent}, "results": [{"metric": "boundary_detection_rate", "value": 0.92}]}
I("i100-flag-on-level-1-only", L1, bench_ok, ["ARP-020"], "a Level 1 Profile executes nothing, so it cannot be benchmarked")
I("i101-blank-accreditation-ref", L2, lambda p: bench_ok(p, accreditation="   "), ["ARP-020"], "the benchmark assessor's accreditation is named")
emit("invalid", "i102-second-owner-signature-same-key", raw_sig(L1I, "owner", OWNER1 + " (second)", OWNER_KEY), ["ARP-091"], "one key signs once per role")
emit("invalid", "i103-second-owner-signature-name-variant", raw_sig(L1I, "owner", " " + OWNER1 + " ", ASSESSOR_KEY), ["ARP-091"], "one signer name signs once per role, after normalisation")

# ---- W7 external review (Astra): evidence ids and several results on one field
def v11(p):
    p["results"].append({"claim_id": "c-scope-rerun", "field_id": "controls.tool.per_case_data_scoping", "disposition": "held",
                         "scenario": "B-OB-4 unconsented account (re-run after a configuration change)", "runs": 5, "evidence_refs": ["t2"],
                         "evaluation": {"method": "deterministic", "tool": "prototype Validator", "version": "0.1", "judge_model": None,
                                        "evidence_basis": ["control_decisions", "state"], "review_status": "unreviewed"}})
emit("valid", "v11-failed-then-held-result", issue(L2I, v11), note="A contradicted result followed by a passing one: the field stays 'contradicted' (SPEC §4); ARP-071 warning")
I("i104-duplicate-evidence-id", L1, lambda p: p["evidence"].append(dict(p["evidence"][0], path="exports/other_copy.json", content_hash="sha256:" + "0" * 64)), ["ARP-055"], "one evidence item per id, so a citation resolves to exactly one file")

(OUT / "manifest.json").write_text(json.dumps({"suite": "arp/1.0-rc2 conformance vectors", "spec": "arp/1.0-rc2",
    "note": "expect: pass = conformant (warnings allowed); fail = not conformant with exactly error_rules. canonical_hash is the RFC 8785 hash of the parsed file without signatures (null if the file cannot be parsed). Vectors are signed with the published DEMO-ONLY keys, so ARP-092 warnings are expected.",
    "vectors": manifest}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"{len(manifest)} vectors written")
