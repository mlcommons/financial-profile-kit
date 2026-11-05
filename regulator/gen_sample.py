#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Generate the sample supervisory feed: five FICTIONAL firms (DEMO-FIRM-01 to -05), four quarterly snapshots each.

Everything here is synthetic. Firms, deployments, models ("Provider A") and vendors are invented;
keys are DEMO-ONLY and derived from a public seed, so anyone can forge them. Except for Example Bank's
two worked Profiles (examples/), the Profile hashes are placeholders for documents that do not exist.
Some problems are planted on purpose so the Supervisory dashboard demo has something to find.

  python gen_sample.py            # writes regulator/sample-feed/
"""
import datetime as dt, hashlib, json, random, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; KIT = HERE.parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(KIT / "conformance")); sys.path.insert(0, str(KIT / "templates"))
import arp_feed, arp_lite  # noqa: E402
from arp_conform import canonical_hash  # noqa: E402

OUT = HERE / "sample-feed"
QUARTERS = ["2025-12-31", "2026-03-31", "2026-06-30", "2026-09-30"]
UC = {t["id"]: t for t in arp_lite.vocab("use-cases")["terms"]}
CONTROLS = arp_lite.PEER
A = lambda s: [f"A{i}" for i in s]
# use case -> (tier choices, permitted action classes, customer facing)
T = {"ODD.1": (["T1", "T2", "T3"], A([1, 2, 3, 7]), "yes"), "ODD.2": (["T2"], A([1, 2, 3, 4]), "no"),
     "ODD.3": (["T2", "T3"], A([1, 2, 3, 4, 5]), "no"), "ODD.4": (["T2", "T3"], A([1, 2, 5, 6, 7]), "yes"),
     "ODD.5": (["T2", "T3"], A([1, 2, 4, 5]), "no"), "ODD.6": (["T2", "T3"], A([1, 2, 3, 4, 7]), "yes"),
     "ODD.7": (["T1", "T2"], A([1, 2, 3, 4, 7]), "yes"), "ODD.9": (["T2"], A([1, 2, 3, 4]), "no"),
     "ODD.10": (["T1", "T2"], A([1, 2, 3, 4]), "no"), "ODD.12": (["T3", "T4"], A([1, 2, 6, 8]), "no"),
     "ODD.14": (["T2"], A([1, 2, 3, 4, 5]), "no"), "ODD.16": (["T3"], A([1, 2, 5, 6, 9]), "no"),
     "ODD.17": (["T2"], A([1, 2, 3, 4]), "no"), "ODD.18": (["T3"], A([1, 2, 6, 7, 8]), "no"),
     "ODD.19": (["T4"], A([1, 2, 6]), "no"), "ODD.20": (["T2"], A([1, 2, 3, 4]), "no"),
     "ODD.22": (["T2"], A([1, 2, 3, 4]), "no"), "ODD.23": (["T1", "T2"], A([1, 2, 3]), "no"),
     "ODD.24": (["T2"], A([1, 2, 3, 5]), "no"), "ODD.25": (["T2"], A([1, 2, 4]), "no"),
     "ODD.26": (["T2", "T3"], A([1, 2, 4, 5]), "no"), "ODD.27": (["T1"], A([1, 2, 3]), "no"),
     "ODD.30": (["T2"], A([1, 2, 3, 7]), "yes"), "ODD.31": (["T3", "T4"], A([1, 2, 8]), "no"),
     "ODD.32": (["T3"], A([1, 2, 5, 6]), "no"), "ODD.33": (["T2", "T3"], A([1, 2, 5, 6]), "no"),
     "ODD.34": (["T3"], A([1, 2, 6, 7]), "yes"), "ODD.35": (["T2"], A([1, 2, 3, 5]), "yes"),
     "ODD.36": (["T3", "T4"], A([1, 2, 8]), "yes"), "ODD.37": (["T2"], A([1, 2, 3, 4]), "no"),
     "ODD.38": (["T2"], A([1, 2, 4]), "no"), "ODD.43": (["T0", "T1"], A([1, 2]), "no"),
     "ODD.44": (["T3"], A([1, 2, 5, 6]), "no"), "ODD.45": (["T2"], A([1, 2, 3]), "no"),
     "ODD.46": (["T2", "T3"], A([1, 2, 5, 11, 12]), "no"), "ODD.47": (["T3", "T4"], A([1, 2, 5, 11]), "no"),
     "ODD.48": (["T2", "T3"], A([1, 2, 4, 5]), "no"), "ODD.49": (["T1", "T2"], A([1, 2, 3]), "no"),
     "ODD.50": (["T1"], A([1, 2, 3]), "no"), "ODD.52": (["T1", "T2"], A([1, 2, 3, 7]), "no")}
OWNER = {"retail_consumer_banking": "Managing Director, Retail Banking", "lending_credit": "Chief Credit Officer",
         "payments": "Head of Payments Operations", "financial_crime_compliance": "MLRO", "markets": "Head of Markets Technology",
         "wealth_asset_management": "Head of Wealth", "treasury_finance": "Group Financial Controller",
         "insurance": "Head of Claims", "internal_corporate": "Chief Operating Officer"}
SUFFIX = ["", " (mobile app)", " (contact centre)", " (UK)", " (business banking)", " (premier)", " v2", " (EU)", " (back office)"]
F = [  # firm parameters
 dict(firm_id="DEMO-FIRM-01", name="Northbridge Bank plc (fictional)", short="Northbridge", peer="Large deposit-takers", delivery="pull",
      endpoint="https://arp-feed.northbridge.example/arp/v0", lei=None, n=62, maturity=.8, appetite=0,
      ucs="1 2 4 5 6 9 10 12 14 16 17 19 20 22 23 24 27 32 37 38 43 44 45 46 47 48 49 50 52".split(),
      cov=[.10, .18, .28, .40], l2=.35, months=12, review=(.6, 110), models={"Provider A frontier 2026-03": .45, "Provider B general 4.1": .35, "In-house model nb-lm-2": .2},
      vendor="In-house agent platform"),
 dict(firm_id="DEMO-FIRM-02", name="Example Bank plc (fictional)", short="Example Bank", peer="Large deposit-takers", delivery="pull",
      endpoint="https://arp.examplebank.example/arp/v0", lei=None, n=28, maturity=.65, appetite=0,
      ucs="1 2 5 6 9 14 16 17 22 23 27 37 44 45 46 47 52".split(), cov=[0, .06, .12, .2], l2=.2, months=12, review=(.45, 150),
      models={"Provider A frontier 2026-03": .5, "Provider C open-weights 70b": .5}, vendor="In-house agent platform"),
 dict(firm_id="DEMO-FIRM-03", name="Lumen Digital Bank Ltd (fictional)", short="Lumen Digital", peer="Large deposit-takers", delivery="push",
      endpoint=None, lei=None, n=36, maturity=.3, appetite=.45, ucs="1 1 2 3 4 4 5 6 6 7 7 16 16 19 46 47 48".split(),
      cov=[0, .02, .03, .04], l2=0, months=6, review=(.25, 210), models={"Provider A frontier 2026-03": .8, "Provider B general 4.1": .2},
      vendor="Vendor P agent builder"),
 dict(firm_id="DEMO-FIRM-04", name="Harbour & Vale Building Society (fictional)", short="Harbour & Vale", peer="Large deposit-takers", delivery="file",
      endpoint=None, lei=None, n=10, maturity=.55, appetite=-.4, ucs="1 2 10 14 20 44 52".split(), cov=[0, .15, .2, .2], l2=0, months=5,
      review=(.12, 430), models={"Provider B general 4.1": 1.0}, vendor="Vendor Q core-banking assistant"),
 dict(firm_id="DEMO-FIRM-05", name="Meridian Capital Markets LLP (fictional)", short="Meridian", peer="Investment firms", delivery="pull",
      endpoint="https://feeds.meridian-cm.example/arp/v0", lei=None, n=23, maturity=.75, appetite=.1,
      ucs="25 26 30 31 31 32 33 34 35 36 37 38 46 47 48".split(), cov=[.1, .2, .3, .42], l2=.5, months=12, review=(.55, 130),
      models={"Provider A frontier 2026-03": .9, "Provider C open-weights 70b": .1}, vendor="In-house agent platform"),
]

def day(s): return dt.date.fromisoformat(s)
def iso(d): return d.isoformat()
def key_for(fid): return hashlib.sha256(b"ARP DEMO-ONLY sample key " + fid.encode()).digest()
def pick(rng, weights): return rng.choices(list(weights), weights=list(weights.values()))[0]
def shift_tier(t, k):
    if t == "U": return t
    order = ["T0", "T1", "T2", "T3", "T4"]; return order[max(0, min(4, order.index(t) + k))]

def approval(tier, rng): return {"T0": "every_material_action", "T1": "every_material_action", "T2": "every_material_action",
                                 "T3": "some_actions", "T4": "none", "U": "some_actions"}[tier]

def controls(rng, m, tier, perm, level, lumen):
    out = {}
    writes = any(a not in ("A1", "A2", "A3", "A4") for a in perm)
    for c in CONTROLS:
        if (c == "harness.human_approval_gates" and tier in ("T0", "T4")) or (c == "tool.transaction_caps" and not {"A8", "A9"} & set(perm)) \
           or (c == "environment.rollback_snapshot" and not writes) or (c == "harness.kill_switch" and tier == "T0"):
            out[c] = "not_applicable"; continue
        if level == 2 and rng.random() < .65:
            out[c] = "tested_not_shown_to_hold" if rng.random() < .1 else "tested_held"; continue
        out[c] = rng.choices(["configured", "documented_only", "absent", "unknown"],
                             weights=[.3 + .55 * m, .2, .12 * (1 - m) + (.08 if lumen else 0), .15 * (1 - m) + (.1 if lumen else 0)])[0]
    return out

def deployments(f, idx):
    rng = random.Random(1000 + idx); out = []
    for k in range(f["n"]):
        u = rng.choice(f["ucs"]); uid = f"ODD.{u}"
        tiers, perm, cf = T[uid]
        tier = rng.choice(tiers)
        if f["appetite"] > 0 and rng.random() < f["appetite"]: tier = shift_tier(tier, 1)
        if f["appetite"] < 0 and rng.random() < -f["appetite"]: tier = shift_tier(tier, -1)
        start = rng.choices([-1, 0, 1, 2, 3], weights=[.45, .12, .14, .15, .14] if f["short"] != "Lumen Digital" else [.2, .15, .2, .22, .23])[0]
        prod = start + rng.choices([0, 1, 2, 9], weights=[.35, .3, .15, .2])[0] if start >= 0 else rng.choice([-1, -1, 0, 1])
        retire = rng.choice([1, 2, 3]) if rng.random() < .06 and start < 0 else 99
        name = UC[uid]["label"] + rng.choice(SUFFIX if cf == "yes" else ["", "", " (UK)", " (group)", " v2", " (back office)"])
        out.append(dict(ref=f"{f['short'][:3].upper()}-AG-{k + 1:03d}", uid=uid, name=name, tier=tier, perm=list(perm), cf=cf, start=start,
                        prod=prod, retire=retire, u=rng.random(), u2=rng.random(), model=pick(rng, f["models"]),
                        seed=rng.random(), creep=None, last=None))
    return out

def ensure(deps, uid, avoid=()):
    d = next((d for d in deps if d["uid"] == uid and d not in avoid), None)
    if d is None:
        d = next(d for d in reversed(deps) if d["uid"] not in ("ODD.16", "ODD.31", "ODD.36") and d not in avoid)
        tiers, perm, cf = T[uid]; d.update(uid=uid, perm=list(perm), cf=cf, tier=tiers[-1], name=UC[uid]["label"])
    return d

def plant(f, deps):
    """Deliberate problems, so the console has something to find."""
    if f["short"] == "Lumen Digital":
        pay = ensure(deps, "ODD.16"); pay.update(tier="T3", start=-1, prod=0, appr="none", caps="absent")
        n = 0
        for d in deps:  # autonomy creep in the latest quarter, no Profile update
            if d["tier"] == "T2" and d["prod"] <= 1 and d["start"] < 2 and n < 3: d["creep"] = 3; n += 1
        u = ensure(deps, "ODD.7", (pay,)); u.update(tier="U", start=1, prod=2, creep=None)
        # Lumen's latest snapshot (4) is TRUSTED and carries the main story: autonomy creep (tier up, human approval down,
        # no Profile reissued), new deployments and moves to production.
    if f["short"] == "Northbridge":
        d = ensure(deps, "ODD.47"); d.update(tier="T3", creep=2, u=.01, u2=.01, prod=-1)
    if f["short"] == "Meridian":
        d = ensure(deps, "ODD.31"); d.update(tier="T4", u=.01, u2=.01, start=-1, prod=-1)
        d2 = ensure(deps, "ODD.36", (d,)); d2.update(tier="T4", start=-1, prod=0, u=.99)
        # Meridian's latest snapshot (4) silently drops a deployment (INV-031), so that snapshot is QUARANTINED on its own:
        # the dashboard shows Meridian at snapshot 3 and lists snapshot 4 in the Feed view.
        drop = next(x for x in deps if x["start"] < 0 and x not in (d, d2) and x["retire"] == 99); drop["silent_drop"] = 3
    if f["short"] == "Example Bank":
        deps[:] = [d for d in deps if d["uid"] not in ("ODD.20",)]

def state(f, d, q, as_of, rng, prev):
    if q < d["start"] or q > d["retire"] or d.get("silent_drop") == q: return None
    if prev and prev["deployment_status"] == "retired": return None
    status = "retired" if q == d["retire"] else "production" if q >= d["prod"] else ("pilot" if q == d["prod"] - 1 else "in_development")
    tier = shift_tier(d["tier"], 1) if d["creep"] is not None and q >= d["creep"] else d["tier"]
    cov = f["cov"][q] if status in ("production", "retired") else 0
    level = 0
    if d["u"] < cov: level = 2 if d["u2"] < f["l2"] else 1
    if d["creep"] is not None and q >= d["creep"] and f["short"] == "Lumen Digital": level = 0 if not prev else int(prev["profile_level"][1:] or 0) if prev["profile_level"] != "none" else 0
    appr = d.get("appr") if d.get("appr") and q >= 0 else approval(tier, rng)
    crng = random.Random(int(d["seed"] * 1e9) + 7 * level)
    ctl = controls(crng, f["maturity"], tier, d["perm"], level, f["short"] == "Lumen Digital")
    if d.get("caps"): ctl["tool.transaction_caps"] = d["caps"]
    if appr == "none" and ctl.get("harness.human_approval_gates") not in (None, "not_applicable"): ctl["harness.human_approval_gates"] = "absent"
    basis = "substantiated" if level == 2 or (tier == "T2" and f["maturity"] > .6 and d["u2"] < .5) else "asserted"
    if appr == "none" and basis == "substantiated": basis = "asserted"
    # review dates: reviewed when something changes, otherwise at the firm's usual rate
    p_rev, age = f["review"]
    if d["last"] is None: d["last"] = day(as_of) - dt.timedelta(days=int(rng.expovariate(1 / age)))
    elif rng.random() < p_rev or (prev and prev["autonomy_tier"] != tier and f["short"] != "Lumen Digital"): d["last"] = day(as_of) - dt.timedelta(days=rng.randint(5, 80))
    model = d["model"]; bl = UC[d["uid"]]["business_line"]
    rec = {"lite_spec": "arp-lite/0.1", "institution": f["name"], "inventory_ref": d["ref"], "agent_name": d["name"],
           "deployment_status": status, "business_line": bl, "use_case_id": d["uid"], "use_case": UC[d["uid"]]["label"],
           "customer_facing": d["cf"], "autonomy_tier": tier, "tier_basis": basis, "human_approval": appr,
           "permitted_actions": d["perm"], "prohibited_actions": [a for a in A(range(1, 13)) if a not in d["perm"]],
           "controls": ctl, "models": model,
           "vendor_or_platform": "Vendor R surveillance suite" if d["uid"] in ("ODD.25", "ODD.26") else f["vendor"],
           "profile_level": f"L{level}" if level else "none", "accountable_owner_role": OWNER[bl], "last_reviewed": iso(d["last"])}
    if level:
        issue_q = d.setdefault("issue_q", q)
        if prev is None or prev["profile_level"] == "none": d["issue_q"] = issue_q = q
        rec["full_profile_ref"] = f"{f['short'].split()[0].lower()}.{d['ref'].lower()}.v{1 + (q >= (d['creep'] or 99))}.L{level}"
        d["profile"] = {"profile_id": rec["full_profile_ref"], "stage": "issued", "headline": level,
                        "valid_until": iso(day(QUARTERS[issue_q]) + dt.timedelta(days=30 * f["months"] + 5)),
                        "sha256": "sha256:" + hashlib.sha256(f"placeholder|{rec['full_profile_ref']}|{issue_q}".encode()).hexdigest()}
    return rec

def example_bank_real(q):
    """Example Bank's two worked Profiles, from examples/, enter the feed when they were issued (Q3 2026)."""
    out, docs = [], {}
    # The feed is a history: its latest snapshot is as of 2026-09-30, so it carries the two examples as first
    # issued (L1 2026-09-22, L2 2026-09-24; frozen copies in regulator/sample-sources/), not the re-issued examples/ files (2026-10-22).
    sources = {"l1-aml-alert-triage.issued.json": KIT / "regulator" / "sample-sources" / "l1-aml-alert-triage.issued-2026-09-22.json",
               "l2-open-banking.json": KIT / "regulator" / "sample-sources" / "l2-open-banking.issued-2026-09-24.json"}
    for fn, status_hist in (("l1-aml-alert-triage.issued.json", ["production"] * 4), ("l2-open-banking.json", ["in_development", "pilot", "pilot", "production"])):
        p = json.loads(sources[fn].read_text(encoding="utf-8"))
        rec = arp_lite.from_profile(p, status_hist[q], "no" if "aml" in fn else "yes", "2026-09-22" if q == 3 else QUARTERS[q])
        rec["institution"] = "Example Bank plc (fictional)"
        # The record is derived from its full Profile (INV-023), models included. One declared divergence is planted:
        # the open-banking agent's owner role changed after its Profile was issued, and the reissue is in preparation.
        if q < 3: rec["profile_level"] = "none"; rec.pop("full_profile_ref", None)
        else:
            docs[p["profile_id"]] = p
            if "ob-" in rec["inventory_ref"]:
                rec["accountable_owner_role"] = "Head of Open Banking and Payments"
                rec["divergence"] = {"fields": ["accountable_owner_role"], "as_of": "2026-09-28",
                                     "reason": "The owner role was reorganised after the Profile was issued; a reissued Profile is in preparation."}
        out.append(rec)
    return out, docs

def main():
    OUT.mkdir(exist_ok=True); (OUT / "objects").mkdir(exist_ok=True)
    registry = {"registry": "arp-feed-registry/0.1", "sample": True, "note": "SAMPLE register of FICTIONAL firms (spec/FEED.md, Creating your firm register): peer groups, delivery mode and each firm's registered signing key. DEMO-ONLY keys derived from a public seed: anyone can forge them. Never use these keys or firm ids for real data.", "firms": []}
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    import base64
    for idx, f in enumerate(F):
        pub = base64.b64encode(Ed25519PrivateKey.from_private_bytes(key_for(f["firm_id"])).public_key().public_bytes_raw()).decode()
        registry["firms"].append({k: f[k] for k in ("firm_id", "name", "short")} | {"peer_group": f["peer"], "delivery": f["delivery"],
                                  "endpoint": f["endpoint"], "public_key": pub})
        deps = deployments(f, idx); plant(f, deps)
        rng = random.Random(77 + idx); prev, prevrec = None, {}
        fdir = OUT / f["firm_id"]; fdir.mkdir(exist_ok=True)
        for q, as_of in enumerate(QUARTERS):
            recs, attach = [], {}
            for d in deps:
                r = state(f, d, q, as_of, rng, prevrec.get(d["ref"]))
                if r: recs.append(r); prevrec[d["ref"]] = r
                if r and r["profile_level"] != "none": attach[r["full_profile_ref"]] = d["profile"]
            docs = {}
            if f["short"] == "Example Bank":
                extra, docs = example_bank_real(q); recs += extra
            produced = f"{iso(day(as_of) + dt.timedelta(days=2 + idx))}T09:{10 + idx:02d}:00Z"  # all before the sample's "today" (7 Oct 2026)
            trig, note = "scheduled", None
            snap = arp_feed.build(recs, f["firm_id"], as_of, prev, docs, trig, produced_at=produced, lei=f["lei"], jurisdictions=["GB"],
                                  attestation={"name": "Sample Signer (fictional)", "role": "Chief Operating Officer", "statement": arp_feed.ATTEST},
                                  change_note=note)
            for e in snap["records"]:
                ref = e["record"].get("full_profile_ref")
                if ref and "profile" not in e and ref in attach: e["profile"] = attach[ref]
            snap = arp_feed.sign(snap, key_for(f["firm_id"]), "Sample Signer (fictional)")
            for p in docs.values(): (OUT / "objects" / f"{canonical_hash(p)[7:]}.json").write_text(json.dumps(p, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            (fdir / f"inventory-{q + 1}.json").write_text(json.dumps(snap, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            prev = snap
    (OUT / "registry.json").write_text(json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote", OUT)

if __name__ == "__main__":
    main()
