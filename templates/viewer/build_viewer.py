#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build the self-contained Profile Viewer from the kit's spec files (keeps it in step with the spec).
Writes templates/ARP Profile Viewer.html (open directly in a browser; makes no network requests)
and templates/viewer/artifact-body.html (the same page without the document wrapper, for hosting)."""
import json
from pathlib import Path
HERE = Path(__file__).resolve().parent; KIT = HERE.parent.parent
VOCABS = ("action-classes", "autonomy-tiers", "business-lines", "conflict-kinds", "control-catalogue",
          "dispositions", "invalidation-triggers", "provenance-classes", "use-cases")
rd = lambda p: p.read_text(encoding="utf-8")
v = lambda n: json.loads(rd(KIT / "spec" / "vocab" / f"{n}.json"))
ex = lambda n: json.loads(rd(KIT / "examples" / n))
data = {"spec": rd(KIT / "VERSION").strip(), "schema": json.loads(rd(KIT / "spec" / "profile.schema.json")),
        "vocab": {"tiers": v("autonomy-tiers")["terms"], "actions": v("action-classes")["terms"], "controls": v("control-catalogue")["terms"],
                  "business_lines": v("business-lines")["terms"], "use_cases": v("use-cases")["terms"]},
        "vocab_versions": {n: v(n)["version"] for n in VOCABS},
        "examples": {"l1": ex("l1-aml-alert-triage.issued.json"), "l2": ex("l2-open-banking.json")}}
src = rd(HERE / "viewer.src.html")
body = src.replace("/*__ARP_DATA__*/null", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
(HERE / "artifact-body.html").write_text(body, encoding="utf-8")
full = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src \'unsafe-inline\'; style-src \'unsafe-inline\'; img-src data:">\n'
        + body.replace("<style>", "<style>\n:root{color-scheme:light}", 1).replace("</style>", "</style>\n</head>\n<body>", 1) + "\n</body>\n</html>\n")
(KIT / "templates" / "ARP Profile Viewer.html").write_text(full, encoding="utf-8")
print("built", len(full), "bytes")
