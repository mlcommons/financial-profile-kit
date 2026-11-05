#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build the downloadable Kit zip from this folder, from an explicit list of shipped files.

  python3 tools/make_release_zip.py [--out DIR] [--allow-unlicensed]
  python3 tools/make_release_zip.py --write-manifest     # maintainers: rewrite the list from a clean folder

Only the files named in tools/RELEASE-MANIFEST.txt are shipped. Before building, the script inspects
every shipped folder and refuses (printing the paths) if it finds:
  - a file that is not on the list (for example a Profile, workbook or evidence you made while trying
    the Kit);
  - a private key (*.key) anywhere except examples/demo-keys/;
  - a symbolic link (links are never followed or packed);
  - a listed file that is missing.
Folders that are never shipped (history/, _retired/, caches, OS junk) are ignored.

Writes <out>/arp-profile-kit-<version>.zip (default out: the folder above the Kit) and prints its SHA-256.
Names are stored as UTF-8 with a fixed timestamp, so the same files always give the same zip.
The Kit is licensed under the Apache License 2.0. The script refuses to build if LICENSE or NOTICE is
missing (both must travel with every copy), or if a LICENSE-PENDING.md is present. --allow-unlicensed
overrides this for an internal build only.
"""
import argparse, hashlib, json, os, sys, zipfile
from pathlib import Path, PurePosixPath

KIT = Path(__file__).resolve().parent.parent
MANIFEST = KIT / "tools" / "RELEASE-MANIFEST.txt"
NEVER_SHIPPED_DIRS = {"history", "_retired", "CHANGELOG.d", "__pycache__", ".pytest_cache", "node_modules", "__MACOSX", ".git"}
JUNK_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini"}
DEMO_KEY_DIR = "examples/demo-keys/"
# Maintainer-only files kept in the working folder but never shipped (review notes addressed to the Working Group,
# and repository housekeeping files).
INTERNAL_FILES = {"REVIEW-rc2.md", ".gitignore", ".gitattributes"}
FIXED = (2026, 1, 1, 0, 0, 0)

def version(kit=KIT):
    v = kit / "VERSION"
    if v.exists(): s = v.read_text(encoding="utf-8").strip()
    else: s = json.loads((kit / "spec" / "profile.schema.json").read_text(encoding="utf-8"))["properties"]["spec"].get("const", "arp/1.0-rc2")
    return s.split("/", 1)[-1].replace("/", "-")      # arp/1.0-rc2 -> 1.0-rc2

def ignorable(rel: PurePosixPath) -> bool:
    """Paths the inspection skips entirely: never-shipped folders, hidden folders, caches, OS junk."""
    if any(p in NEVER_SHIPPED_DIRS or p.startswith(".") for p in rel.parts[:-1]): return True
    n = rel.name
    if rel.as_posix() in INTERNAL_FILES: return True
    return n in JUNK_NAMES or n.startswith("~$") or n.endswith((".pyc", ".pyo"))

def walk(kit=KIT):
    """Yield (relative posix path, Path) for everything under the Kit without following symlinks."""
    for dirpath, dirnames, filenames in os.walk(kit, followlinks=False):
        d = Path(dirpath)
        reld = PurePosixPath(d.relative_to(kit).as_posix()) if d != kit else PurePosixPath()
        keep = []
        for dn in sorted(dirnames):
            full = d / dn; rel = reld / dn
            if dn in NEVER_SHIPPED_DIRS or dn.startswith("."): continue
            if full.is_symlink(): yield rel, full; continue          # reported as a symlink, never entered
            keep.append(dn)
        dirnames[:] = keep
        for fn in sorted(filenames):
            yield reld / fn, d / fn

def read_manifest(kit=KIT):
    p = kit / "tools" / "RELEASE-MANIFEST.txt"
    if not p.exists(): return None
    return [l.strip() for l in p.read_text(encoding="utf-8").splitlines() if l.strip() and not l.lstrip().startswith("#")]

def inspect(kit=KIT):
    """Return (listed files, problems). Problems are human-readable strings."""
    listed = read_manifest(kit)
    problems = []
    if listed is None:
        return [], [f"missing list of shipped files: {MANIFEST.relative_to(KIT).as_posix()} (run --write-manifest on a clean folder)"]
    allow = set(listed)
    for rel, full in walk(kit):
        r = rel.as_posix()
        if ignorable(rel): continue
        if full.is_symlink():
            problems.append(f"symbolic link (never packed): {r}"); continue
        if r.endswith(".key") and not r.startswith(DEMO_KEY_DIR):
            problems.append(f"private key outside {DEMO_KEY_DIR}: {r}"); continue
        if r not in allow:
            problems.append(f"not on the shipped list: {r}")
    for r in listed:
        f = kit / r
        if f.is_symlink(): problems.append(f"listed file is a symbolic link: {r}")
        elif not f.is_file(): problems.append(f"listed file is missing: {r}")
    return listed, problems

def write_manifest(kit=KIT):
    files, problems = [], []
    for rel, full in walk(kit):
        r = rel.as_posix()
        if ignorable(rel): continue
        if full.is_symlink(): problems.append(f"symbolic link: {r}"); continue
        if r.endswith(".key") and not r.startswith(DEMO_KEY_DIR): problems.append(f"private key outside {DEMO_KEY_DIR}: {r}"); continue
        files.append(r)
    if problems:
        print("refused: clean the folder first:\n  " + "\n  ".join(problems)); return 1
    rel_manifest = "tools/RELEASE-MANIFEST.txt"
    if rel_manifest not in files: files.append(rel_manifest)
    (kit / rel_manifest).write_text("# Files shipped in the Kit download, one per line. Generated by\n"
                                    "# tools/make_release_zip.py --write-manifest from a clean folder; review the diff before committing.\n"
                                    + "\n".join(sorted(files)) + "\n", encoding="utf-8")
    print(f"wrote {rel_manifest} ({len(files)} files)")
    return 0

def build(out_dir, allow_unlicensed=False, kit=KIT):
    if not allow_unlicensed:
        missing = [n for n in ("LICENSE", "NOTICE") if not (kit / n).is_file()]
        if missing:
            print("refused: " + " and ".join(missing) + " missing; the Kit ships under the Apache License 2.0 and both files must be included. Use --allow-unlicensed only for an internal build.")
            return 1, None
        if (kit / "LICENSE-PENDING.md").exists():
            print("refused: LICENSE-PENDING.md is present; remove it once the licence is decided. Use --allow-unlicensed only for an internal build.")
            return 1, None
    listed, problems = inspect(kit)
    if problems:
        print("refused: the Kit folder holds files that must not be shipped or is missing listed files:\n  " + "\n  ".join(problems))
        return 1, None
    root = f"arp-profile-kit-{version(kit)}"
    out = Path(out_dir) / f"{root}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for r in sorted(listed):
            f = kit / r
            info = zipfile.ZipInfo(f"{root}/{r}", FIXED)
            info.flag_bits |= 0x800                       # names are UTF-8
            info.external_attr = (0o755 if f.suffix in (".py", ".mjs") else 0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, f.read_bytes())
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    print(f"wrote {out} ({len(listed)} files)\nsha256 {digest}")
    return 0, out

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(KIT.parent)); ap.add_argument("--allow-unlicensed", action="store_true")
    ap.add_argument("--write-manifest", action="store_true", help="rewrite tools/RELEASE-MANIFEST.txt from this (clean) folder")
    a = ap.parse_args()
    if a.write_manifest: return write_manifest()
    return build(a.out, a.allow_unlicensed)[0]

if __name__ == "__main__":
    sys.exit(main())
