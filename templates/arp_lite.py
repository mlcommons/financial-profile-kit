#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Profile Lite: one row per agent deployment, for inventories and data requests (rules: spec/LITE.md).

  python3 arp_lite.py template OUT.xlsx|OUT.csv          # blank template
  python3 arp_lite.py check    IN.xlsx|IN.csv            # validate every row
  python3 arp_lite.py to-json  IN.xlsx|IN.csv OUT.json   # rows -> JSON records
  python3 arp_lite.py from-profile PROFILE.json --status production --customer-facing no \\
          --last-reviewed 2026-10-01 [--append IN.xlsx|IN.csv] [--out OUT.json]
  python3 arp_lite.py to-profiles IN.xlsx|IN.csv OUTDIR [--force]   # each valid row -> a draft full Profile

A Lite record is what the institution reports. Its values are as reported; the record itself is not
checked against evidence. It is a starting point for a full Profile, not a substitute for one.

CSV files are read as UTF-8 (with or without the byte-order mark Excel adds). Cells that would start a
formula in a spreadsheet (= + - @) are written to CSV with a leading apostrophe, which is removed again
on reading. Exit codes: 0 all rows valid; 1 a row or the file has problems; 2 usage.
"""
import argparse, csv, datetime as dt, json, re, sys
from pathlib import Path
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.workbook.defined_name import DefinedName

HERE = Path(__file__).resolve().parent; KIT = HERE.parent
sys.path.insert(0, str(KIT / "conformance"))
def _read_json(path): return json.loads(Path(path).read_text(encoding="utf-8"))
def vocab(n): return _read_json(KIT / "spec" / "vocab" / f"{n}.json")
SCHEMA = _read_json(KIT / "spec" / "profile-lite.schema.json")
LITE_SPEC = SCHEMA["properties"]["lite_spec"].get("const", "arp-lite/0.1")
_VALIDATOR = None
PROFILE_SPEC = _read_json(KIT / "spec" / "profile.schema.json")["properties"]["spec"].get("const", "arp/1.0-rc2")
_VOCAB_DIR = KIT / "spec" / "vocab"
VOCAB_VERSIONS = {k: v for k, v in ((f.stem, _read_json(f).get("version")) for f in sorted(_VOCAB_DIR.glob("*.json"))) if v}
DEFAULT_VOIDS = [{"trigger": t["id"], "description": t["meaning"]} for t in _read_json(_VOCAB_DIR / "invalidation-triggers.json")["terms"] if t.get("default")]
STATUS = ("Status: release candidate 2 of arp/1.0, prepared by the MLCommons Financial Services Working Group for pilot use and comment. "
          "Not a final MLCommons standard, certification scheme or endorsement. Field names and rules may change before 1.0.")
P = SCHEMA["properties"]
PEER = vocab("peer-control-set")["terms"]
CAT = {t["id"]: t["label"] for t in vocab("control-catalogue")["terms"]}
UC = {t["id"]: t for t in vocab("use-cases")["terms"]}

# (key, label, list values or None, width, guidance)
COLUMNS = [
    ("institution", "Institution", None, 22, "Legal name"),
    ("inventory_ref", "Inventory ref", None, 14, "Your internal id for this agent"),
    ("agent_name", "Agent name / description", None, 30, "Short description"),
    ("deployment_status", "Deployment status", P["deployment_status"]["enum"], 15, ""),
    ("business_line", "Business line", P["business_line"]["enum"], 22, ""),
    ("use_case_id", "Catalogued use case", ["ODD." + k.split(".")[1] for k in UC] , 13, "ODD.1–ODD.52 (see Use cases sheet), or ODD.x_<name>"),
    ("use_case", "Use case (your words)", None, 30, ""),
    ("customer_facing", "Customer-facing?", ["yes", "no"], 11, ""),
    ("autonomy_tier", "Autonomy tier", P["autonomy_tier"]["enum"], 10, "T0–T4, or U if not yet profiled"),
    ("tier_basis", "Tier basis", P["tier_basis"]["enum"], 13, "'substantiated' only if approval records support it"),
    ("human_approval", "Human approval before material actions", P["human_approval"]["enum"], 22, ""),
    ("permitted_actions", "Permitted action classes", None, 18, "Comma-separated, e.g. A1, A2, A4"),
    ("prohibited_actions", "Prohibited action classes", None, 18, "Comma-separated"),
] + [(f"control.{c}", "Control: " + CAT[c], P["controls"]["properties"][c]["enum"], 17, "") for c in PEER] + [
    ("models", "Models used", None, 24, "Provider, model and version"),
    ("vendor_or_platform", "Vendor or platform", None, 20, ""),
    ("profile_level", "Full Profile level", P["profile_level"]["enum"], 10, "none, or the headline level of the full Profile"),
    ("full_profile_ref", "Full Profile id", None, 22, "If a full Profile exists"),
    ("accountable_owner_role", "Accountable owner (role)", None, 22, ""),
    ("last_reviewed", "Last reviewed", None, 12, "YYYY-MM-DD"),
]
KEYS = [c[0] for c in COLUMNS]
EXAMPLE = {"institution": "e.g. Example Bank plc (fictional)", "inventory_ref": "AG-0042", "agent_name": "Retail alert triage assistant",
           "deployment_status": "production", "business_line": "financial_crime_compliance", "use_case_id": "ODD.20",
           "use_case": "Alert triage for structuring and rapid movement", "customer_facing": "no", "autonomy_tier": "T2",
           "tier_basis": "substantiated", "human_approval": "every_material_action", "permitted_actions": "A1, A2, A3, A4",
           "prohibited_actions": "A5, A6, A7, A8, A9, A10, A11, A12", "control.harness.human_approval_gates": "configured",
           "control.harness.kill_switch": "documented_only", "control.harness.immutable_tool_call_logging": "documented_only",
           "control.harness.high_risk_routing": "unknown", "control.tool.action_allowlists": "configured",
           "control.tool.least_privilege_credentials": "unknown", "control.tool.transaction_caps": "not_applicable",
           "control.environment.rollback_snapshot": "unknown", "models": "<provider> <model> <pinned version>",
           "vendor_or_platform": "", "profile_level": "L1", "full_profile_ref": "examplebank.fc.alert-triage.v3.L1",
           "accountable_owner_role": "Head of Financial Crime Operations", "last_reviewed": "2026-09-22"}

F = "Arial"; HB = Font(name=F, size=10, bold=True, color="FFFFFF"); BODY = Font(name=F, size=10)
GUIDE = Font(name=F, size=9, italic=True, color="6B7280"); KEYF = Font(name=F, size=8, color="9CA3AF")
FILL_IN = PatternFill("solid", fgColor="FFF7CC"); FILL_HEAD = PatternFill("solid", fgColor="1F4E79"); FILL_GUIDE = PatternFill("solid", fgColor="F3F4F6")
BOX = Border(*(Side(style="thin", color="D1D5DB"),) * 4)
FIRST = 6  # template layout: row 3 labels, row 4 machine keys, row 5 example, data from row 6 (reading finds the rows by content)
GUIDE_RGB = "F3F4F6"
INJECT = ("=", "+", "-", "@")

class LiteFileError(Exception): pass

def _csv_out(v):
    """Neutralise spreadsheet formula injection in CSV: prefix an apostrophe (removed again on reading)."""
    v = "" if v is None else str(v)
    return "'" + v if v.startswith(INJECT) else v

def _csv_in(v):
    v = v or ""
    return v[1:] if v.startswith("'") and v[1:2] in INJECT and v[1:2] != "" else v

def _put(ws, r, c, v):
    cell = ws.cell(r, c, v)
    if isinstance(v, str) and v.startswith("="): cell.data_type = "s"
    return cell

def template_xlsx(out, rows=200):
    wb = Workbook(); ws = wb.active; ws.title = "Inventory"
    ws["A1"] = "Agent Reliability Profile Lite — agent inventory"; ws["A1"].font = Font(name=F, size=14, bold=True)
    ws["A2"] = ("One row per agent deployment. Pale yellow cells are for you to fill in; the grey row starting 'e.g.' is an example and is ignored. "
                "Values are as reported by the institution and are not checked against evidence. See the 'About' sheet.")
    ws["A2"].font = GUIDE
    lists = wb.create_sheet("Lists"); col = 1
    for i, (k, label, vals, width, guide) in enumerate(COLUMNS, 1):
        c = ws.cell(3, i, label); c.font = HB; c.fill = FILL_HEAD; c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.cell(4, i, k).font = KEYF
        e = _put(ws, 5, i, EXAMPLE.get(k)); e.font = GUIDE; e.fill = FILL_GUIDE
        ws.column_dimensions[c.column_letter].width = width
        for r in range(FIRST, FIRST + rows):
            cell = ws.cell(r, i); cell.fill = FILL_IN; cell.border = BOX; cell.font = BODY
        if vals:
            for j, v in enumerate(vals, 2): lists.cell(j, col, v)
            L = lists.cell(1, col).column_letter; name = f"LL_{col}"
            wb.defined_names[name] = DefinedName(name, attr_text=f"Lists!${L}$2:${L}${len(vals)+1}")
            dv = DataValidation(type="list", formula1=f"={name}", allow_blank=True, showErrorMessage=(k != "use_case_id"))
            ws.add_data_validation(dv); dv.add(f"{c.column_letter}{FIRST}:{c.column_letter}{FIRST + rows - 1}"); col += 1
    ws.row_dimensions[3].height = 42; ws.freeze_panes = ws.cell(FIRST, 4)
    lists.sheet_state = "hidden"
    uc = wb.create_sheet("Use cases"); uc.append(["Id", "Business line", "Use case"])
    for t in UC.values(): uc.append([t["id"], t["business_line"], t["label"]])
    for c in uc[1]: c.font = HB; c.fill = FILL_HEAD
    uc.column_dimensions["A"].width = 10; uc.column_dimensions["B"].width = 26; uc.column_dimensions["C"].width = 70
    ab = wb.create_sheet("About"); ab.column_dimensions["A"].width = 120
    for i, t in enumerate([
        f"Profile Lite ({LITE_SPEC}, draft)",
        STATUS,
        "A one-row summary of each AI agent deployment: what it does, how autonomous it is, what it may and may not do, and how eight key controls are evidenced.",
        "Use it to build an agent inventory, or to answer a supervisory data request. It is a starting point for a full Agent Reliability Profile, not a substitute.",
        "",
        "Control status values: tested_held · tested_not_shown_to_hold · configured · documented_only · absent · not_applicable · unknown.",
        "Action classes: A1 read · A2 analyse · A3 draft · A4 recommend · A5 write internal · A6 commit internal · A7 external communication · A8 bounded transaction · A9 move funds · A10 regulatory filing · A11 access/infrastructure change · A12 delegate/spawn.",
        "",
        "Check a filled sheet:   python3 templates/arp_lite.py check MyInventory.xlsx",
        "Start a full Profile from a row:   python3 templates/arp_lite.py to-profiles MyInventory.xlsx out/",
        "Rules for each column: spec/LITE.md. Do not edit row 4 (machine keys): the tools use it to find the columns.",
        "",
        "Everything here is as reported by the institution and is not checked against evidence. Values are not comparable across institutions.",
    ], 1):
        ab.cell(i, 1, t).font = Font(name=F, size=12 if i == 1 else 10, bold=(i == 1))
    wb.save(out)

def template_csv(out):
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(KEYS); w.writerow([_csv_out(EXAMPLE.get(k, "")) for k in KEYS])

def _cell(v):
    if v is None: return ""
    if isinstance(v, dt.datetime): return v.date().isoformat()
    if isinstance(v, dt.date): return v.isoformat()
    if isinstance(v, float) and v.is_integer(): return str(int(v))
    return str(v).strip()

def read_raw(path):
    """-> [(row number, {key: text})], [problems]. Example rows ('e.g.' or grey) are skipped wherever they are;
    formula cells are refused. Raises LiteFileError when the file itself cannot be read."""
    path = Path(path); rows, problems = [], []
    if path.suffix.lower() == ".csv":
        try:
            with open(path, newline="", encoding="utf-8-sig") as f:
                r = csv.DictReader(f)
                missing = [k for k in ("institution", "inventory_ref") if k not in (r.fieldnames or [])]
                if missing: raise LiteFileError(f"{path}: the first row must hold the column keys (e.g. {', '.join(missing)}); start from the CSV template")
                for n, row in enumerate(r, 2):
                    if (row.get("institution") or "").strip().startswith("e.g."): continue
                    vals = {k: _csv_in((row.get(k) or "")).strip() for k in KEYS}
                    if any(vals.values()): rows.append((n, vals))
        except UnicodeDecodeError:
            raise LiteFileError(f"{path} is not UTF-8 text. In Excel, save it as 'CSV UTF-8 (Comma delimited)'.")
        return rows, problems
    try: wb = load_workbook(path)
    except Exception as e: raise LiteFileError(f"cannot open {path} as an Excel workbook: {e}")
    if "Inventory" not in wb.sheetnames: raise LiteFileError(f"{path}: sheet 'Inventory' is missing; do not rename it")
    ws = wb["Inventory"]
    head = next((r for r in range(1, 11) if ws.cell(r, 1).value == "institution"), None)
    if head is None: raise LiteFileError(f"{path}: the row of column keys (starting 'institution') was not found; do not edit row 4")
    keys = [ws.cell(head, c).value for c in range(1, ws.max_column + 1)]
    for r in range(head + 1, ws.max_row + 1):
        first = ws.cell(r, 1)
        if isinstance(first.value, str) and first.value.strip().startswith("e.g."): continue
        if str(first.fill.fgColor.rgb or "").upper().endswith(GUIDE_RGB): continue   # rc1 templates: grey example row
        row = {}
        for c, k in enumerate(keys, 1):
            if not k: continue
            cell = ws.cell(r, c)
            if cell.data_type == "f":
                problems.append((r, "LITE-001", k, f"contains a formula ({cell.value}); type the value itself")); row[k] = ""; continue
            row[k] = _cell(cell.value)
        if any(row.values()): rows.append((r, row))
    return rows, problems

def to_record(raw):
    rec = {"lite_spec": LITE_SPEC}
    ctl = {}
    for k in KEYS:
        v = raw.get(k, "")
        if k.startswith("control."): ctl[k[8:]] = v or "unknown"; continue
        if k in ("permitted_actions", "prohibited_actions"):
            rec[k] = [x.strip().upper() for x in v.split(",") if x.strip()]; continue
        if k == "use_case_id" and v and not v.startswith("ODD."): v = "ODD." + v
        if v != "": rec[k] = v
    rec["controls"] = ctl
    return rec

def check_record(rec):
    global _VALIDATOR
    if _VALIDATOR is None:
        from arp_conform import make_validator
        _VALIDATOR = make_validator(SCHEMA)
    out = [("LITE-001", "/".join(map(str, e.path)) or "-", e.message) for e in _VALIDATOR.iter_errors(rec)]
    both = set(rec.get("permitted_actions", [])) & set(rec.get("prohibited_actions", []))
    if both: out.append(("LITE-010", "actions", f"both permitted and prohibited: {sorted(both)}"))
    if rec.get("autonomy_tier") == "T2" and rec.get("human_approval") != "every_material_action":
        out.append(("LITE-011", "human_approval", "tier T2 means a person approves every material action"))
    if rec.get("tier_basis") == "substantiated" and rec.get("human_approval") == "none":
        out.append(("LITE-012", "tier_basis", "a tier cannot be substantiated by approval records when there is no human approval"))
    if rec.get("profile_level", "none") != "none" and not rec.get("full_profile_ref"):
        out.append(("LITE-013", "full_profile_ref", "a full Profile level is given but no Profile id"))
    u = UC.get(rec.get("use_case_id", ""))
    if u and rec.get("business_line") and u["business_line"] != rec["business_line"]:
        out.append(("LITE-W01", "use_case_id", f"warning: {u['id']} is catalogued under {u['business_line']}"))
    return out

def from_profile(p, status, customer_facing, last_reviewed):
    from arp_conform import field_dispositions
    c = p["claim"]; res = {k: v["disposition"] for k, v in field_dispositions(p.get("results", [])).items()}  # SPEC §4: most severe result per field
    def st(cid):
        x = next((k for k in c["controls"] if k["control_id"] == cid), None)
        if x is None: return "unknown"
        if x.get("applicable") is False: return "not_applicable"
        if x["present"] is False: return "absent"
        if x["present"] is None: return "unknown"
        d = res.get(f"controls.{cid}")
        if d: return "tested_held" if d == "held" else "tested_not_shown_to_hold"
        cls = p["provenance"].get(f"controls.{cid}", {}).get("class")
        return "configured" if cls in ("configuration_derived", "measured") else "documented_only"
    aq = c["autonomy"].get("approval_quality")
    gates = next((k for k in c["controls"] if k["control_id"] == "harness.human_approval_gates" and k["present"]), None)
    rec = {"lite_spec": LITE_SPEC, "institution": p["subject"]["institution"], "inventory_ref": p["subject"]["deployment_id"],
           "agent_name": p["subject"].get("description") or p["subject"]["deployment_id"], "deployment_status": status,
           "business_line": c["odd"]["business_line"], "use_case": c["odd"]["use_case"], "customer_facing": customer_facing,
           "autonomy_tier": c["autonomy"]["tier"], "tier_basis": c["autonomy"]["tier_basis"],
           "human_approval": "every_material_action" if c["autonomy"]["tier"] == "T2" else ("some_actions" if gates else "none"),
           "permitted_actions": sorted(c["actions"]["permitted"], key=lambda a: int(a[1:])),
           "prohibited_actions": sorted(c["actions"]["prohibited"], key=lambda a: int(a[1:])),
           "controls": {cid: st(cid) for cid in PEER},
           "profile_level": f"L{p['assurance']['headline']}" if p["stage"] == "issued" else "none",
           "accountable_owner_role": p["issuance"]["owner"]["role"], "last_reviewed": last_reviewed}
    if c["odd"].get("use_case_id"): rec["use_case_id"] = c["odd"]["use_case_id"]
    if p["subject"].get("models"): rec["models"] = ", ".join(f"{m['provider']} {m['model']} {m['version']}" for m in p["subject"]["models"])
    if p["subject"].get("vendor_products"): rec["vendor_or_platform"] = ", ".join(p["subject"]["vendor_products"])
    if rec["profile_level"] != "none": rec["full_profile_ref"] = p["profile_id"]
    return rec

def to_profile(rec):
    """A draft full Profile seeded from a Lite record. Everything is owner_attested; TODOs mark what the
    owner or the Builder must still supply. It will not conform until they do."""
    T = "TODO"; prov = {}
    att = lambda note: {"class": "owner_attested", "note": note}
    controls = []
    for cid, s in rec["controls"].items():
        if s == "unknown": continue
        x = {"control_id": cid, "layer": cid.split(".")[0], "present": {"absent": False}.get(s, True)}
        if s == "not_applicable": x["present"] = None; x["applicable"] = False
        controls.append(x); prov[f"controls.{cid}"] = att(f"Profile Lite status '{s}'; evidence not yet compiled")
    au = {"tier": rec["autonomy_tier"], "tier_basis": "asserted",
          "modifiers": {m: T for m in ("data_authority", "reversibility_profile", "customer_market_impact", "accountability", "population_scope")} | {"stack_composability": "not_assessed"}}
    au["modifiers"] = {k: au["modifiers"][k] for k in ("data_authority", "reversibility_profile", "customer_market_impact", "stack_composability", "accountability", "population_scope")}
    if rec["autonomy_tier"] == "T2":
        au["approval_quality"] = {"assessment": "not_assessed", "sample_size": 0}
        prov["autonomy.approval_quality"] = {"class": "absent", "note": "Approval records not yet reviewed"}
    for m in au["modifiers"]: prov[f"autonomy.modifiers.{m}"] = att("TODO")
    prov["autonomy.tier"] = att(f"Profile Lite; reported basis '{rec['tier_basis']}'")
    odd = {"business_line": rec["business_line"], "use_case": rec["use_case"]}
    if rec.get("use_case_id"): odd["use_case_id"] = rec["use_case_id"]; prov["odd.use_case_id"] = att("Profile Lite")
    prov["odd.use_case"] = att("Profile Lite"); prov["odd.business_line"] = att("Profile Lite")
    for a in rec["permitted_actions"] + rec["prohibited_actions"]: prov[f"actions.{a}"] = att("Profile Lite")
    return {"spec": PROFILE_SPEC, "profile_id": f"{rec['inventory_ref']}.L1", "stage": "draft",
            "subject": {"institution": rec["institution"], "deployment_id": rec["inventory_ref"], "deployment_version": None,
                        "description": rec["agent_name"], "vendor_products": [rec["vendor_or_platform"]] if rec.get("vendor_or_platform") else [],
                        "platform_baseline": None, "models": []},
            "issuance": {"owner": {"name": T, "role": rec["accountable_owner_role"]}, "issued_at": None, "valid_from": None, "valid_until": None,
                         "evidence_as_of": rec["last_reviewed"]},
            "claim": {"statement": "TODO: write the bounded claim for this deployment.", "autonomy": au, "odd": odd,
                      "actions": {"permitted": rec["permitted_actions"], "prohibited": rec["prohibited_actions"]}, "controls": controls},
            "assurance": {"axes": {"autonomy": 1, "odd": 1, "actions": 1, "controls": 1}, "headline": 1,
                          "assessors": {ax: {"role": "institution", "organisation": rec["institution"]} for ax in ("autonomy", "odd", "actions", "controls")},
                          "test_environment": None, "method": "seeded from Profile Lite (arp_lite.py)",
                          "comparability": {"flag": False, "environment_version": None, "hidden_set_version": None, "fidelity_statement": None},
                          "disclosures": ["level1_untested", "not_comparable"]},
            "provenance": prov, "conflicts": [], "floors": [], "results": [], "benchmark": None,
            "out_of_scope": {"statement": "TODO: state what the claim excludes.", "odd": [], "actions": [], "controls": [], "users": []},
            "invalidation": {"voids": [dict(x) for x in DEFAULT_VOIDS], "partial_retest": [], "cosmetic": [],
                             "monitoring": "TODO: say how the institution detects these changes."}, "evidence": [],
            "vocab_versions": dict(VOCAB_VERSIONS),
            "status": {"open_findings": [], "accepted_gaps": [], "exceptions": [], "risk_acceptances": [],
                       "limitations": ["Seeded from a Profile Lite record: every field is owner-attested and nothing has been checked against evidence."]},
            "signatures": []}

def _row_for(rec):
    row = {k: "" for k in KEYS}
    for k, v in rec.items():
        if k == "controls":
            for c, s in v.items(): row[f"control.{c}"] = s
        elif k in KEYS: row[k] = ", ".join(v) if isinstance(v, list) else v
    return row

def append(path, rec):
    path = Path(path); row = _row_for(rec)
    if path.suffix.lower() == ".csv":
        new = not path.exists()
        with open(path, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new: w.writerow(KEYS)
            w.writerow([_csv_out(row[k]) for k in KEYS])
    else:
        wb = load_workbook(path); ws = wb["Inventory"]
        r = FIRST
        while any(ws.cell(r, c).value not in (None, "") for c in range(1, len(KEYS) + 1)): r += 1
        for c, k in enumerate(KEYS, 1): _put(ws, r, c, row[k] or None)
        wb.save(path)

def _safe_name(ref, n):
    s = re.sub(r"[^A-Za-z0-9._-]", "_", str(ref or f"row{n}")).lstrip(".")
    return (s or f"row{n}")[:64]

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("template"); t.add_argument("out")
    c = sub.add_parser("check"); c.add_argument("path")
    j = sub.add_parser("to-json"); j.add_argument("path"); j.add_argument("out")
    f = sub.add_parser("from-profile"); f.add_argument("profile"); f.add_argument("--status", required=True)
    f.add_argument("--customer-facing", required=True); f.add_argument("--last-reviewed", required=True)
    f.add_argument("--append"); f.add_argument("--out")
    p = sub.add_parser("to-profiles"); p.add_argument("path"); p.add_argument("outdir")
    p.add_argument("--force", action="store_true", help="overwrite existing draft files")
    a = ap.parse_args()
    if a.cmd == "template":
        (template_csv if a.out.lower().endswith(".csv") else template_xlsx)(a.out); print(f"wrote {a.out}"); return 0
    if a.cmd == "from-profile":
        try: prof = _read_json(a.profile)
        except (OSError, ValueError) as e: print(f"ERROR   cannot read {a.profile} as JSON: {e}"); return 1
        rec = from_profile(prof, a.status, a.customer_facing, a.last_reviewed)
        errs = check_record(rec)
        for r, path, m in errs: print(f"{'WARNING' if r.startswith('LITE-W') else 'ERROR':7} {r:9} {path}: {m}", file=sys.stderr)
        if a.append: append(a.append, rec); print(f"appended to {a.append}", file=sys.stderr)
        text = json.dumps(rec, indent=2, ensure_ascii=False) + "\n"
        if a.out: Path(a.out).write_text(text, encoding="utf-8")
        elif not a.append: sys.stdout.write(text)
        return 1 if any(not e[0].startswith("LITE-W") for e in errs) else 0
    try: raw, problems = read_raw(a.path)
    except LiteFileError as e: print(f"ERROR   {e}"); return 1
    rows = [(n, to_record(r)) for n, r in raw]
    errs_by_row = {n: check_record(rec) for n, rec in rows}
    for n, code, key, m in problems: errs_by_row.setdefault(n, []).insert(0, (code, key, m))
    seen = {}
    for n, rec in rows:
        ref = rec.get("inventory_ref")
        if ref and ref in seen: errs_by_row[n].append(("LITE-001", "inventory_ref", f"'{ref}' is already used on row {seen[ref]}; refs must be unique in an inventory"))
        elif ref: seen[ref] = n
    hard = lambda n: [e for e in errs_by_row.get(n, []) if not e[0].startswith("LITE-W")]
    if a.cmd == "check":
        bad = 0
        for n, rec in rows:
            bad += bool(hard(n))
            for r, path, m in errs_by_row[n]: print(f"row {n}: {'WARNING' if r.startswith('LITE-W') else 'ERROR':7} {r:9} {path}: {m}")
        print(f"{len(rows) - bad}/{len(rows)} rows valid"); return 1 if bad else 0
    if a.cmd == "to-json":
        Path(a.out).write_text(json.dumps([r for _, r in rows], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {len(rows)} records to {a.out}"); return 1 if any(hard(n) for n, _ in rows) else 0
    if a.cmd == "to-profiles":
        out = Path(a.outdir); out.mkdir(parents=True, exist_ok=True); base = out.resolve(); bad = 0
        for n, rec in rows:
            if hard(n):
                bad += 1
                for r, path, m in hard(n): print(f"row {n}: ERROR   {r:9} {path}: {m}")
                print(f"row {n}: skipped (fix the errors above)"); continue
            fn = (out / f"{_safe_name(rec.get('inventory_ref'), n)}.draft.json").resolve()
            if fn.parent != base: print(f"row {n}: skipped (the file name would fall outside {out})"); bad += 1; continue
            if fn.exists() and not a.force: print(f"row {n}: skipped ({fn.name} already exists; use --force to overwrite)"); bad += 1; continue
            fn.write_text(json.dumps(to_profile(rec), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"row {n} -> {fn}")
        return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main())
