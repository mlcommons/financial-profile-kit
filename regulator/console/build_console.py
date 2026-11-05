#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build the self-contained Supervisory dashboard demo from the kit (keeps it in step with the spec and the Viewer).

Embeds: the Profile and inventory schemas, vocabularies, the FICTIONAL sample feed (regulator/sample-feed/; loaded only
when the user asks for it, and badged as sample data), and the
Profile checker and Profile rendering from templates/viewer/viewer.src.html, so both tools share one implementation.
Writes regulator/ARP Supervisory Dashboard Demo.html (open directly in a browser) and regulator/console/artifact-body.html.

  python3 regulator/console/build_console.py [--feed DIR]   # the sample feed to embed; default: regulator/sample-feed

Real data is never embedded: supervisors open their key register and snapshot files in the browser.
"""
import argparse, json, re
from pathlib import Path

HERE = Path(__file__).resolve().parent; KIT = HERE.parent.parent

def between(s, start, end, include_start=True):
    i = s.index(start); j = s.index(end, i)
    return s[i if include_start else i + len(start):j]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--feed", default=str(KIT / "regulator" / "sample-feed")); a = ap.parse_args()
    feed = Path(a.feed)
    rd = lambda f: json.loads(Path(f).read_text(encoding="utf-8"))
    v = lambda n: rd(KIT / "spec" / "vocab" / f"{n}.json")
    snaps = [rd(f) for f in sorted(feed.glob("*/inventory-*.json"))]
    objects = [rd(f) for f in sorted((feed / "objects").glob("*.json"))] if (feed / "objects").exists() else []
    data = {"spec": "arp/1.0-rc2", "schema": rd(KIT / "spec" / "profile.schema.json"),
            "inventory_schema": rd(KIT / "spec" / "inventory.schema.json"),
            "vocab": {"tiers": v("autonomy-tiers")["terms"], "actions": v("action-classes")["terms"], "controls": v("control-catalogue")["terms"],
                      "business_lines": v("business-lines")["terms"], "use_cases": v("use-cases")["terms"], "peer_controls": v("peer-control-set")["terms"], "peer_control_status": v("peer-control-status")["terms"]},
            "sample": {"registry": rd(feed / "registry.json") if (feed / "registry.json").exists() else {"firms": []},
                       "snapshots": snaps, "objects": objects}}
    viewer = (KIT / "templates" / "viewer" / "viewer.src.html").read_text(encoding="utf-8")
    css = between(viewer, "<style>", "</style>", include_start=False)
    core = between(viewer, "const D = ARP_DATA, V = D.vocab;", "/* ---------- state ---------- */")
    render = between(viewer, "const chip=", "/* ---------- edit form ---------- */")
    src = (HERE / "console.src.html").read_text(encoding="utf-8")
    body = (src.replace("/*__VIEWER_CSS__*/", css).replace("/*__CONSOLE_JS__*/", (HERE / "console.js").read_text(encoding="utf-8")).replace("/*__ARP_CORE__*/", core).replace("/*__ARP_RENDER__*/", render)
               .replace("/*__ARP_DATA__*/null", json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")))
    assert "/*__" not in body, re.findall(r"/\*__\w+__\*/", body)
    (HERE / "artifact-body.html").write_text(body, encoding="utf-8")
    full = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            + body.replace("<style>", "<style>\n:root{color-scheme:light}", 1).replace("</style>", "</style>\n</head>\n<body>", 1) + "\n</body>\n</html>\n")
    (KIT / "regulator" / "ARP Supervisory Dashboard Demo.html").write_text(full, encoding="utf-8")
    print("built", len(full), "bytes;", len(snaps), "snapshots,", len(objects), "Profile documents")

if __name__ == "__main__":
    main()
