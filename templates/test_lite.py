#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Profile Lite tool tests: the example inventory reads cleanly; an Excel 'CSV UTF-8' file (with BOM) reads;
formulas, duplicate refs and unsafe refs are reported; to-profiles never writes outside its folder or
overwrites; CSV output neutralises formula injection.

  python3 templates/test_lite.py
"""
import csv, json, subprocess, sys, tempfile
from pathlib import Path
from openpyxl import load_workbook
HERE = Path(__file__).resolve().parent
TOOL = [sys.executable, str(HERE / "arp_lite.py")]
EXAMPLE = HERE / "examples" / "example-profile-lite-inventory.xlsx"

def run(*args):
    r = subprocess.run(TOOL + [str(a) for a in args], capture_output=True, text=True, encoding="utf-8")
    return r.returncode, r.stdout + r.stderr

def main():
    fails = 0; count = 0
    def ok(name, cond, info=""):
        nonlocal fails, count; fails += not cond; count += 1
        print(("  PASS " if cond else "  FAIL ") + name + ("" if cond else f"\n     {info[:600]}"))
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        code, out = run("check", EXAMPLE); ok("example inventory: all rows valid", code == 0 and "2/2 rows valid" in out, out)
        code, out = run("to-json", EXAMPLE, tmp / "rows.json")
        recs = json.loads((tmp / "rows.json").read_text(encoding="utf-8"))
        csvp = tmp / "inv.csv"
        with open(csvp, "w", newline="", encoding="utf-8-sig") as f:      # what Excel's 'CSV UTF-8' writes
            w = csv.writer(f); keys = load_keys(); w.writerow(keys)
            for rec in recs: w.writerow([row_value(rec, k) for k in keys])
        code, out = run("check", csvp); ok("CSV with a byte-order mark reads", code == 0 and "2/2 rows valid" in out, out)
        bad = tmp / "bad.csv"
        with open(bad, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); keys = load_keys(); w.writerow(keys)
            for ref in ("../../escaped", "AG-1", "AG-1"):
                rec = dict(recs[0]); rec["inventory_ref"] = ref; w.writerow([row_value(rec, k) for k in keys])
        code, out = run("check", bad)
        ok("unsafe and duplicate inventory refs are reported", code == 1 and "already used on row 3" in out and "row 2:" in out, out)
        outdir = tmp / "out" / "deep"
        code, out = run("to-profiles", bad, outdir)
        made = sorted(p.name for p in outdir.glob("*.json")); escaped = list((tmp).glob("escaped*"))
        ok("to-profiles skips invalid rows and writes nothing outside its folder", made == ["AG-1.draft.json"] and not escaped and code == 1, out + str(made))
        code, out = run("to-profiles", bad, outdir)
        ok("to-profiles refuses to overwrite without --force", "already exists" in out, out)
        wb = load_workbook(EXAMPLE); ws = wb["Inventory"]; ws.cell(7, 1, "=CONCAT(\"Example\",\" Bank\")"); x = tmp / "f.xlsx"; wb.save(x)
        code, out = run("check", x); ok("a formula cell is refused with its row", code == 1 and "contains a formula" in out, out)
        nonl = tmp / "cp1252.csv"; nonl.write_bytes("institution,inventory_ref\nCaf\xe9 Bank,AG-9\n".encode("cp1252"))
        code, out = run("check", nonl); ok("a non-UTF-8 CSV gets a clear message", code == 1 and "CSV UTF-8" in out, out)
        inj = tmp / "inj.csv"
        prof = HERE.parent / "examples" / "l1-aml-alert-triage.issued.json"
        p = json.loads(prof.read_text(encoding="utf-8")); p["subject"]["description"] = "=HYPERLINK(\"https://attacker.example\")"
        pj = tmp / "p.json"; pj.write_text(json.dumps(p), encoding="utf-8")
        run("from-profile", pj, "--status", "production", "--customer-facing", "no", "--last-reviewed", "2026-10-01", "--append", inj)
        raw = inj.read_text(encoding="utf-8")
        code, out = run("to-json", inj, tmp / "inj.json"); back = json.loads((tmp / "inj.json").read_text(encoding="utf-8"))
        ok("CSV formula injection is neutralised and reads back unchanged", "'=HYPERLINK" in raw and back[0]["agent_name"].startswith("=HYPERLINK"), raw[:300])
        code, out = run("from-profile", prof, "--status", "production", "--customer-facing", "no", "--last-reviewed", "2026-10-01")
        ok("from-profile prints the record to standard output", code == 0 and '"lite_spec"' in out, out)
    total = count
    print(f"\n{total - fails}/{total} passed"); sys.exit(1 if fails else 0)

def load_keys():
    sys.path.insert(0, str(HERE)); import arp_lite; return arp_lite.KEYS

def row_value(rec, k):
    if k.startswith("control."): return rec["controls"].get(k[8:], "")
    v = rec.get(k, ""); return ", ".join(v) if isinstance(v, list) else v

if __name__ == "__main__":
    main()
