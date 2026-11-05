#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Keep the Profile Builder skill's bundled copies of the spec and checker identical to the kit's.

The skill ships its own copy (skill/arp-profile-builder/spec/ and scripts/arp_conform.py,
scripts/arp_summary.py) so that it works when installed on its own. Never edit those copies:
edit spec/ and conformance/, then run this script.

  python3 tools/sync_skill_bundle.py           # copy the kit's files into the skill bundle
  python3 tools/sync_skill_bundle.py --check   # drift test: exit 1 if any copy differs (use in CI)
"""
import argparse, sys
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
SKILL = KIT / "skill" / "arp-profile-builder"


def pairs():
    yield KIT / "spec" / "SPEC.md", SKILL / "spec" / "SPEC.md"
    yield KIT / "spec" / "profile.schema.json", SKILL / "spec" / "profile.schema.json"
    yield KIT / "spec" / "profile-summary.schema.json", SKILL / "spec" / "profile-summary.schema.json"
    for f in sorted((KIT / "spec" / "vocab").glob("*.json")):
        yield f, SKILL / "spec" / "vocab" / f.name
    for n in ("arp_conform.py", "arp_summary.py"):
        yield KIT / "conformance" / n, SKILL / "scripts" / n


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    drift = []
    for src, dst in pairs():
        if not dst.exists() or dst.read_bytes() != src.read_bytes():
            drift.append(dst.relative_to(KIT))
            if not a.check:
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(src.read_bytes())
    stale = [f.relative_to(KIT) for f in (SKILL / "spec" / "vocab").glob("*.json") if not (KIT / "spec" / "vocab" / f.name).exists()]
    if a.check:
        for d in drift: print(f"DRIFT {d}")
        for s in stale: print(f"STALE {s} (not in spec/vocab)")
        print("skill bundle in step with the kit" if not drift and not stale else f"{len(drift) + len(stale)} file(s) out of step: run python3 tools/sync_skill_bundle.py")
        return 1 if drift or stale else 0
    for d in drift: print(f"updated {d}")
    for s in stale: print(f"note: {s} is not in spec/vocab; move it to a _retired/ folder if it is obsolete")
    print("skill bundle in step with the kit")
    return 0


if __name__ == "__main__":
    sys.exit(main())
