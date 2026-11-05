#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check that the Kit's shared vocabulary matches the pinned taxonomy release.

The taxonomy repository (mlcommons/financial-profile-taxonomy) is the single official source of
autonomy tiers and modifiers, business lines, use cases, action classes and the control catalogue. Its
scripts/export_vocab.py writes them to vocab/ in the format of spec/vocab/. spec/taxonomy.lock.json names
the release this Kit pins and which files and fields the taxonomy owns.

  python3 tools/check_taxonomy_vocab.py --taxonomy <taxonomy checkout or its vocab/ folder>
  python3 tools/check_taxonomy_vocab.py --taxonomy <...> --strict     # label differences fail too

Exit 1 when an identifier, an assignment (business line, layer, ordinal, reversibility) or the pinned
release number differs. Label and definition differences are listed; with --strict they also fail.
Known label differences awaiting reconciliation are recorded in COMPATIBILITY.md.
"""
import argparse, json, sys
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
LOCK = KIT / "spec" / "taxonomy.lock.json"
STRUCTURAL = {"use-cases.json": ["business_line"], "action-classes.json": ["reversibility"],
              "control-catalogue.json": ["layer", "ordinal"]}


def rd(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def norm(v):
    return " ".join(json.dumps(v, ensure_ascii=False, sort_keys=True).split())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--taxonomy", required=True, help="taxonomy repository checkout, or its vocab/ folder")
    ap.add_argument("--strict", action="store_true", help="treat label and definition differences as failures")
    a = ap.parse_args()

    lock = rd(LOCK)
    tdir = Path(a.taxonomy)
    if (tdir / lock["taxonomy_vocab_dir"]).is_dir():
        tdir = tdir / lock["taxonomy_vocab_dir"]
    errors, notes = [], []

    for fname, fields in lock["taxonomy_owned"].items():
        tp, kp = tdir / fname, KIT / "spec" / "vocab" / fname
        if not tp.exists():
            errors.append(f"{fname}: not in the taxonomy release folder {tdir}")
            continue
        t, k = rd(tp), rd(kp)
        if str(t.get("version")) != lock["taxonomy_release"]:
            errors.append(f"{fname}: taxonomy file is version {t.get('version')}, lock pins {lock['taxonomy_release']}")
        if fname == "business-lines.json":
            if t["terms"] != k["terms"]:
                errors.append(f"{fname}: business-line IDs or order differ: taxonomy {t['terms']} | Kit {k['terms']}")
            for bid, lab in t.get("labels", {}).items():
                if k.get("labels", {}).get(bid) != lab:
                    notes.append(f"{fname} {bid}: label taxonomy '{lab}' | Kit '{k.get('labels', {}).get(bid)}'")
            continue
        for group, gfields in fields.items():
            tt, kk = t.get(group, []), k.get(group, [])
            tid, kid = [x["id"] for x in tt], [x["id"] for x in kk]
            if tid != kid:
                only_t, only_k = sorted(set(tid) - set(kid)), sorted(set(kid) - set(tid))
                errors.append(f"{fname} {group}: IDs differ" + (f"; only in taxonomy {only_t}" if only_t else "")
                              + (f"; only in Kit {only_k}" if only_k else "") + ("; order differs" if not (only_t or only_k) else ""))
            kmap = {x["id"]: x for x in kk}
            for x in tt:
                y = kmap.get(x["id"])
                if y is None:
                    continue
                for f in gfields:
                    if f == "id" or (f not in x and f not in y):
                        continue
                    if norm(x.get(f)) != norm(y.get(f)):
                        msg = f"{fname} {x['id']}.{f}: taxonomy {json.dumps(x.get(f), ensure_ascii=False)} | Kit {json.dumps(y.get(f), ensure_ascii=False)}"
                        (errors if f in STRUCTURAL.get(fname, []) else notes).append(msg)

    for e in errors:
        print(f"MISMATCH  {e}")
    for n in notes:
        print(f"{'MISMATCH' if a.strict else 'label   '}  {n}")
    print(f"\npinned taxonomy release {lock['taxonomy_release']}: {len(errors)} identifier/assignment mismatch(es), "
          f"{len(notes)} label/definition difference(s){' (failing: --strict)' if a.strict and notes else ''}")
    return 1 if errors or (a.strict and notes) else 0


if __name__ == "__main__":
    sys.exit(main())
