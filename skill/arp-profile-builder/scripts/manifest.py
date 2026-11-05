#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Hash every file in an evidence package and propose an artifact class for each.

  python3 <skill>/scripts/manifest.py <package-dir> --out <workdir>/evidence.json

Without --out the manifest is written to standard output. Files and folders whose names start with '.'
(for example .git) are skipped. Files are hashed in chunks, so large files are fine.

The class is a guess from words in the file's path and its extension, matched as whole words or path
segments (so 'exchange_rates.csv' is not read as 'change'). The agent must correct it after reading each
file. Every proposal and the word that triggered it are listed on standard error, so the corrections can
be recorded in the owner review pack.

The manifest is hashed but not signed. The preprint describes a signed source manifest; in this release
the owner's signature on the issued Profile, which covers the evidence hashes, stands in for it.
"""
import argparse, hashlib, json, re, sys
from pathlib import Path

RULES = [  # (words that must appear consecutively in the path, class) - first match wins
    ("event extract", "run_log"), ("mrm", "attestation_governance"), ("validation report", "attestation_governance"),
    ("approval record", "approval_workflow"), ("approval records", "approval_workflow"), ("approvals", "approval_workflow"), ("approval", "approval_workflow"),
    ("iam", "identity_entitlements"), ("entitlement", "identity_entitlements"), ("entitlements", "identity_entitlements"),
    ("scope", "identity_entitlements"), ("scopes", "identity_entitlements"),
    ("registry", "configuration_export"), ("policy export", "configuration_export"), ("export", "configuration_export"),
    ("exports", "configuration_export"), ("config", "configuration_export"), ("configuration", "configuration_export"), ("settings", "configuration_export"),
    ("runbook", "operational_documentation"), ("runbooks", "operational_documentation"), ("procedure", "operational_documentation"), ("procedures", "operational_documentation"),
    ("design", "technical_design"), ("architecture", "technical_design"),
    ("attestation", "attestation_governance"), ("attest", "attestation_governance"), ("risk", "attestation_governance"),
    ("change", "attestation_governance"), ("changes", "attestation_governance"),
    ("log", "run_log"), ("logs", "run_log"), ("trace", "run_log"), ("traces", "run_log"),
    ("prd", "product_documentation"), ("memo", "product_documentation"), ("brief", "product_documentation"),
    ("policy", "product_documentation"), ("policies", "product_documentation"),
]
RENDERING_EXT = (".pdf", ".png", ".jpg", ".jpeg")
MACHINE_EXT = (".csv", ".json", ".xml", ".yaml", ".yml", ".jsonl")

def words(path: str):
    """Lower-case words of a path: split on anything that is not a letter or digit, and at camelCase."""
    path = re.sub(r"([a-z])([A-Z])", r"\1 \2", path)
    return [w for w in re.split(r"[^a-z0-9]+", path.lower()) if w]

def classify(p: str, siblings=frozenset()):
    """-> (class, reason). Whole-word matching on the path; '.jsonl' files are run logs unless a rule says otherwise."""
    low = p.lower(); stem = low.rsplit(".", 1)[0]
    if low.endswith(RENDERING_EXT) and ({"console", "screen", "screenshot"} & set(words(p)) or stem in siblings):
        return "console_rendering", "a rendering of a machine-readable file"
    ws = words(p.rsplit(".", 1)[0] if "." in Path(p).name else p)
    for phrase, cls in RULES:
        ph = phrase.split()
        if any(ws[i:i + len(ph)] == ph for i in range(len(ws))): return cls, f"word '{phrase}'"
    if low.endswith(".jsonl"): return "run_log", "extension .jsonl"
    return "unclassified", "no rule matched"

def sha256(f: Path) -> str:
    h = hashlib.sha256()
    with open(f, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""): h.update(chunk)
    return "sha256:" + h.hexdigest()

def build(root: str):
    base = Path(root)
    if not base.is_dir(): raise SystemExit(f"error: {root} is not a folder")
    files = sorted(f for f in base.rglob("*") if f.is_file() and not any(part.startswith(".") for part in f.relative_to(base).parts))
    machine = {f.relative_to(base).as_posix().lower().rsplit(".", 1)[0] for f in files if f.suffix.lower() in MACHINE_EXT}
    out = []
    for i, f in enumerate(files, 1):
        rel = f.relative_to(base).as_posix(); cls, why = classify(rel, machine)
        out.append({"id": f"e{i}", "path": rel, "content_hash": sha256(f), "artifact_class": cls, "bytes": f.stat().st_size})
        print(f"e{i}\t{cls}\t({why})\t{rel}", file=sys.stderr)
    return out

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("package"); ap.add_argument("--out", help="write the manifest here (folders are created)")
    a = ap.parse_args()
    text = json.dumps(build(a.package), indent=2, ensure_ascii=False) + "\n"
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True); Path(a.out).write_text(text, encoding="utf-8")
        print(f"wrote {a.out}", file=sys.stderr)
    else: sys.stdout.write(text)

if __name__ == "__main__":
    main()
