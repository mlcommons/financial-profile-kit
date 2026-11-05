#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Regenerate every workbook and CSV template in templates/ from spec/ and examples/.

  python3 templates/build_workbooks.py

Run it after any change to spec/ or examples/. It writes:
  templates/arp-profile-template.xlsx               blank full-Profile workbook
  templates/arp-profile-lite-template.xlsx          blank Profile Lite inventory
  templates/arp-profile-lite-template.csv           the same, as CSV
  templates/examples/example-aml-alert-triage-L1.xlsx   examples/l1-aml-alert-triage.draft.json in the workbook
  templates/examples/example-open-banking-L2.xlsx       examples/l2-open-banking.json in the workbook
  templates/examples/example-profile-lite-inventory.xlsx the two example Profiles as Lite rows
All data in the examples is fictional.
"""
import json, sys, tempfile
from pathlib import Path
HERE = Path(__file__).resolve().parent; KIT = HERE.parent
sys.path.insert(0, str(HERE))
import arp_xlsx, arp_lite

def main():
    ex = lambda n: json.loads((KIT / "examples" / n).read_text(encoding="utf-8"))
    out = []
    def save(wb, path): wb.save(path); out.append(path)
    save(arp_xlsx.build_template(), HERE / "arp-profile-template.xlsx")
    arp_lite.template_xlsx(HERE / "arp-profile-lite-template.xlsx"); out.append(HERE / "arp-profile-lite-template.xlsx")
    arp_lite.template_csv(HERE / "arp-profile-lite-template.csv"); out.append(HERE / "arp-profile-lite-template.csv")
    (HERE / "examples").mkdir(exist_ok=True)
    save(arp_xlsx.from_profile(ex("l1-aml-alert-triage.draft.json")), HERE / "examples" / "example-aml-alert-triage-L1.xlsx")
    save(arp_xlsx.from_profile(ex("l2-open-banking.json")), HERE / "examples" / "example-open-banking-L2.xlsx")
    inv = HERE / "examples" / "example-profile-lite-inventory.xlsx"
    arp_lite.template_xlsx(inv)
    for name, status in (("l1-aml-alert-triage.issued.json", "production"), ("l2-open-banking.json", "pilot")):
        arp_lite.append(inv, arp_lite.from_profile(ex(name), status, "no", "2026-10-22"))
    out.append(inv)
    for p in out: print(f"wrote {p.relative_to(KIT)}")

if __name__ == "__main__":
    main()
