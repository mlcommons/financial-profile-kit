#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Checks that the release zip ships only listed files.

  python3 tools/test_release_zip.py

Copies the Kit to a temporary folder, then: (1) a clean copy builds and the zip holds exactly the listed
files, including LICENSE (Apache-2.0) and NOTICE, and a copy without LICENSE is refused; (2) a planted owner.key, a MyProfile.json and a symbolic link each make the build refuse and are
named in the output; (3) a missing listed file makes it refuse. Nothing in the real Kit is changed.
"""
import contextlib, io, os, shutil, sys, tempfile, zipfile
from pathlib import Path
KIT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT / "tools"))
import make_release_zip as M

def run(kit, out):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): code, z = M.build(out, kit=kit)
    return code, z, buf.getvalue()

def main():
    ok = fail = 0
    def t(name, cond, detail=""):
        nonlocal ok, fail
        print(("PASS  " if cond else "FAIL  ") + name + ("" if cond else f"\n      {detail}"))
        ok += cond; fail += (not cond)
    with tempfile.TemporaryDirectory(prefix="arp zip test ") as tmp:
        tmp = Path(tmp); kit = tmp / "kit copy"; out = tmp / "out"; out.mkdir()
        shutil.copytree(KIT, kit, symlinks=True, ignore=shutil.ignore_patterns("__pycache__", "_retired", "history", "node_modules"))
        listed = M.read_manifest(kit)
        code, z, msg = run(kit, out)
        names = set(n.split("/", 1)[1] for n in zipfile.ZipFile(z).namelist()) if z else set()
        t("clean copy builds", code == 0, msg)
        t("zip holds exactly the listed files", names == set(listed), sorted(set(listed) ^ names)[:10])
        t("internal review notes (REVIEW-rc2.md) are not shipped", "REVIEW-rc2.md" not in names and "REVIEW-rc2.md" not in listed, "REVIEW-rc2.md shipped")
        t("LICENSE and NOTICE are in the zip", {"LICENSE", "NOTICE"} <= names, sorted(names)[:5])
        t("LICENSE is the Apache License 2.0", z is not None and "Apache License" in zipfile.ZipFile(z).read(f"{zipfile.ZipFile(z).namelist()[0].split('/')[0]}/LICENSE").decode("utf-8")[:200])
        lic = kit / "LICENSE"; lic_data = lic.read_bytes(); lic.unlink()
        code, z2, msg = run(kit, out)
        t("missing LICENSE refused", code == 1 and "LICENSE" in msg and "missing" in msg, msg)
        lic.write_bytes(lic_data)
        t("no private key outside examples/demo-keys", all(not n.endswith(".key") or n.startswith("examples/demo-keys/") for n in names))
        for plant, label in [("owner.key", "private key"), ("templates/MyProfile.json", "not on the shipped list")]:
            p = kit / plant; p.write_text("x", encoding="utf-8")
            code, z, msg = run(kit, out)
            t(f"planted {plant} refused", code == 1 and plant in msg and label in msg, msg)
            p.unlink()
        link = kit / "examples" / "hostname"
        try:
            os.symlink("/etc/hostname", link); made = True
        except (OSError, NotImplementedError): made = False
        if made:
            code, z, msg = run(kit, out)
            t("planted symlink refused", code == 1 and "symbolic link" in msg and "examples/hostname" in msg, msg)
            link.unlink()
        else:
            print("SKIP  planted symlink (this system cannot create symbolic links)")
        victim = kit / listed[0]; data = victim.read_bytes(); victim.unlink()
        code, z, msg = run(kit, out)
        t("missing listed file refused", code == 1 and "missing" in msg, msg)
        victim.write_bytes(data)
        code, z, msg = run(kit, out)
        t("clean again after removing plants", code == 0, msg)
    print(f"\n{ok}/{ok+fail} release-zip checks pass")
    return 0 if fail == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
