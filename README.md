# Agent Reliability Profile Kit — arp/1.0 release candidate 2

> **Status: release candidate 2 of arp/1.0, prepared by the MLCommons Financial Services Working Group for pilot use and comment. Not a final MLCommons standard, certification scheme or endorsement. Field names and rules may change before 1.0. Conformance means a Profile is well-formed, consistent, honestly labelled and signed. It does not mean its claims are true or the agent is safe.**
>
> **Public pilot: Level 1 (Asserted) only.** Anyone may use the Kit to inventory agents and compile, sign and exchange Level 1 Profiles. Level 2 (Validated) and Level 3 (Verified) tooling and the Level 2 example are included for **Working Group pilots with assessment support**, pending use-case assessment policies that set minimum coverage and critical-boundary floors. Until those exist, a "Validated" label on its own does not tell a reader which boundaries were tested or what happened: read the level, the coverage and the results together (`spec/SPEC.md` §4).
>
> Licence: [Apache License 2.0](LICENSE). Copyright 2026 MLCommons; see [NOTICE](NOTICE).

The Kit lets you write, check, read and receive **Agent Reliability Profiles**: one record per deployed AI agent that states what it may do, under which controls, and how strongly that has been tested. The Profile is defined in the preprint *Agent Reliability Profiles in Financial Services* ([arXiv:2610.04123](https://arxiv.org/abs/2610.04123)). Where this Kit and the preprint differ, the preprint's concepts govern and the Kit's rules make them testable. Terms are explained in [GLOSSARY.md](GLOSSARY.md); what "conformant" means and does not mean is in [CONFORMANCE.md](CONFORMANCE.md).

Everything runs locally and the Kit sends nothing anywhere. Its outputs are another matter: a full Profile contains evidence paths, short verbatim citations, configuration values, names and findings, so it needs a disclosure review before it leaves the team that owns it ([DISCLOSURE.md](DISCLOSURE.md)).

## Start here

| I am… | Start with | Then |
|---|---|---|
| **An engineer** who builds or runs agents | [Install](#install), then [Your first Level 1 Profile](#your-first-level-1-profile) | The Builder skill ([below](#the-profile-builder-skill)), `spec/SPEC.md` |
| **A risk, model-risk or governance lead** who does not code | Open `templates/ARP Profile Viewer.html` in a browser and load an example from `examples/` | Fill `templates/arp-profile-template.xlsx`; one conversion step needs a colleague who can run Python ([details](#for-non-coders)) |
| **A supervisor** who receives Profiles | Open `regulator/ARP Supervisory Dashboard Demo.html` and choose "Load sample (fictional) feed" | `spec/FEED.md` (how firms deliver inventories) and [What a Profile does and does not tell you](CONFORMANCE.md) |

## Which file do I need?

| Task | File | Needs code? | Maturity |
|---|---|---|---|
| Know the rules | `spec/SPEC.md`, `spec/profile.schema.json`, `spec/vocab/` | No | Normative, release candidate |
| Check a Profile | `conformance/arp_conform.py check` | Python | Reference implementation |
| Test your own checker or generator | `conformance/run_suite.py --impl "…"`, `conformance/vectors/` | Python | Reference implementation |
| Sign (issue) a Profile | `conformance/arp_conform.py keygen` and `sign` | Python | Reference implementation |
| Compile a Level 1 Profile from evidence with an AI assistant | `skill/arp-profile-builder/` | An assistant that runs Python | Reference tool, prototype (skill 0.2) |
| Write a Profile by hand | `templates/arp-profile-template.xlsx` | One conversion step in Python | Tool |
| Read a Profile, check it, see its disclosures | `templates/ARP Profile Viewer.html` | No (opens in a browser, offline) | Tool |
| Keep a one-row-per-agent inventory | `templates/arp-profile-lite-template.xlsx` or `.csv`, `spec/LITE.md` | No (checking needs Python) | Draft (`arp-lite/0.1`) |
| Send an inventory to a supervisor; receive one | `spec/FEED.md`, `regulator/arp_feed.py`, `regulator/ARP Supervisory Dashboard Demo.html` | Python to build; the dashboard demo needs none | **Preview** (`arp-inventory/0.1`, draft) |
| Share a Profile summary with peers | `spec/profile-summary.schema.json`, `conformance/arp_summary.py` | Python | Design only (`arp-summary/0.3-draft`) |
| See worked examples | `examples/`, `templates/examples/` (the Level 2 example, `examples/l2-open-banking.json`, is an illustrative Working Group example) | No | Fictional demo data |
| Decide what to send, and to whom | [DISCLOSURE.md](DISCLOSURE.md) | No | Guidance |
| Make a redacted copy to send | `conformance/arp_conform.py redact-prepare`, then `check` and `sign` ([DISCLOSURE.md](DISCLOSURE.md)) | Python | Reference implementation |

The Regulator Kit (`regulator/`, `spec/FEED.md`) is a preview: it is included so supervisors can try it, but it is less mature than the Profile Specification and may change more.

## Install

Python 3.10 or later. From the Kit folder:

```
python3 -m pip install -r requirements.txt        # Windows: py -m pip install -r requirements.txt
```

The browser tools (`templates/ARP Profile Viewer.html`, `regulator/ARP Supervisory Dashboard Demo.html`) need nothing: open them in a current browser. Nothing you load into them is uploaded. The JavaScript tests need Node 18 or later. On Windows use `py` where this README says `python3`.

Check that everything works:

```
python3 conformance/arp_conform.py check examples/l2-open-banking.json   # expected: CONFORMANT
python3 conformance/run_suite.py                                         # expected: every vector "behaves as specified"
```

## Your first Level 1 Profile

A Level 1 (Asserted) Profile records what you believe you have deployed. Nothing is executed.

1. **Collect the evidence** for one deployment in a folder: policy and product documents, configuration and tool-registry exports, IAM or entitlement exports, approval records, logs.
2. **Compile a draft**, either with the Builder skill in your AI assistant ([below](#the-profile-builder-skill)) or by filling `templates/arp-profile-template.xlsx`. For the workbook, hash the evidence first:
   `python3 skill/arp-profile-builder/scripts/manifest.py <evidence folder> --out evidence.json` and copy the rows into sheet 7.
3. **Convert and check** a workbook: `python3 templates/arp_xlsx.py to-json MyProfile.xlsx MyProfile.json`. It names the sheet, row and column of anything it cannot read, then lists anything that does not conform by rule. Fix and repeat. (The skill checks its own output.)
4. **Owner review.** The accountable owner reads the draft and the review pack, resolves or accepts conflicts, and sets *Issued at*, *Valid from* and *Valid until* (sheet 1, or `issuance` in the JSON).
5. **Create a signing key**, once: `python3 conformance/arp_conform.py keygen owner.key`. Keep it under your institution's key policy ([Keys and signing](#keys-and-signing)).
6. **Sign** to issue: `python3 conformance/arp_conform.py sign MyProfile.json --role owner --name "<owner's name>" --key owner.key --out MyProfile.issued.json`. The signer refuses while any rule fails or a required issuance field is missing, and says which.
7. **Check** the result: `python3 conformance/arp_conform.py check MyProfile.issued.json`.

### For non-coders

Everything except two steps is done in Excel: hashing evidence files for sheet 7, and converting the finished workbook to JSON (steps 2 and 3 above) need someone who can run Python. The Viewer opens, explains and checks a Profile in the browser without any installation. The workbook's *Start here* sheet explains each sheet; select any yellow cell to see its guidance.

## The Profile Builder skill

`skill/arp-profile-builder/` is the Profile Builder packaged as an agent skill: an AI assistant that can run Python follows `SKILL.md` to compile a Level 1 draft from an evidence package, cite the source of every value, keep conflicts open and leave unknown fields blank. It never signs, never tests, never resolves conflicts and never installs anything.

- **Install:** copy `skill/arp-profile-builder/` into your assistant's skills folder (or point the assistant at it). It needs Python 3.10+ with this Kit's requirements already installed.
- **Data:** the skill makes no network calls, but whether evidence stays inside your institution depends on where your assistant runs. Use an assistant your institution has approved for this evidence.
- **Personal data:** the skill is instructed to quote the least text needed and to replace customer, account and staff identifiers with `[redacted]`, and it lists files that contain personal data in the owner review pack. Treat this as a control to check, not a guarantee: the owner's review and the disclosure review ([DISCLOSURE.md](DISCLOSURE.md)) confirm it.
- **Trial run:** `skill-trial/ta-ob-2-rc1/` is one illustrative run on a fictional deployment. It predates the final edit to the tier rule and is not a validation of the skill; see its `RUN-NOTE.md`. A reference run on at least two model families is required before 1.0.
- The skill carries its own copy of `spec/` and the checker so that it works on its own; the copies are kept identical to the Kit's.

## What leaves your institution

The Kit sends nothing. What you choose to send, and what it contains, is set out field by field in [DISCLOSURE.md](DISCLOSURE.md).
- **The evidence package** (documents, exports, logs) stays with you. A Profile identifies it by hash, but the Profile also carries evidence paths, short verbatim citations, configuration values, people's names and roles, and findings.
- **To your supervisor:** an inventory snapshot (one Profile Lite record per agent) and, if asked, full Profiles (`spec/FEED.md`), each after a disclosure review.
- **To peers or a Profile Exchange** (proposed, not built): only a derived Profile Summary, never the full Profile or evidence.
- **If your AI assistant is hosted outside the institution**, the evidence the Builder skill reads has left already: use an assistant approved for that evidence.
- **A redacted Profile is a new document**: start it with `arp_conform.py redact-prepare`, redact, re-sign the evidence manifest if you changed evidence entries, check it, and have the named owner (and, for a Level 3 axis, the assessor) sign it again; the original signature does not cover edited content ([DISCLOSURE.md](DISCLOSURE.md)).

## Keys and signing

`keygen` creates an unencrypted private key file (Ed25519, file permissions 0600). For pilots, keep it in your institution's secrets store; for production signing, use your KMS or HSM. A valid signature proves possession of a key, not who holds it (`spec/SPEC.md` §7). Keys in `examples/demo-keys/` are public, **DEMO-ONLY** keys for the fictional examples; never sign a real Profile with them ([examples/demo-keys/README.md](examples/demo-keys/README.md)).

## Sample and demo data

All institutions, deployments, people, models and keys in `examples/`, `templates/examples/`, `skill-trial/` and `regulator/sample-feed/` are **fictional**, and are labelled "(fictional)". Some evidence hashes in the examples are placeholders. Problems are planted in the sample feed on purpose, so the dashboard has something to find:
- **Lumen Digital (DEMO-FIRM-03):** in its latest snapshot (4, trusted) three T2 deployments move to T3 with less human approval and no reissued Profile (autonomy creep), alongside ten new deployments and two moves into production; it also runs a funds-moving agent at T3 with no human approval and no transaction caps, and an unprofiled (tier U) agent.
- **Northbridge (DEMO-FIRM-01):** one agent's tier rises, with less human approval, in snapshot 3.
- **Meridian (DEMO-FIRM-05):** four tier T4 agents, including execution and algorithm selection, and customer-facing portfolio rebalancing; in snapshot 4 a deployment disappears without being retired (INV-031), so snapshot 4 is quarantined and Meridian is shown at snapshot 3.
- **Harbour & Vale (DEMO-FIRM-04):** two full Profiles that expired before snapshot 4 (INV-022, labelled warnings) and a single model provider for every deployment.
- **Example Bank (DEMO-FIRM-02):** its records are derived from the two worked Profiles, with one declared divergence (INV-023, labelled warning).

Other gaps (for example transacting agents without enforced caps at other firms) arise from the generator's random draws. The dashboard builds its figures from **trusted snapshots only**: a snapshot that fails a check is quarantined, listed in the Feed view, and the firm is shown at its last trusted snapshot (`spec/FEED.md` §6).

## Tests

```
python3 conformance/run_suite.py                 # every conformance vector behaves as specified
python3 templates/test_roundtrip.py              # workbook round trips and workbook edits: all pass
python3 templates/test_lite.py                   # Profile Lite tool: all pass
node templates/viewer/test_viewer.mjs            # the Viewer's checker agrees with the reference checker
python3 regulator/test_schemas.py                # embedded schemas and vocabularies have not drifted
node regulator/console/test_console.mjs          # console and arp_feed.py agree (rendering tests need: npm install jsdom@24)
python3 conformance/test_redaction.py            # the redaction procedure in DISCLOSURE.md, on both examples
python3 tools/test_release_zip.py                # the download zip ships only listed files (refuses keys, stray files, links)
python3 regulator/arp_feed.py chain regulator/sample-feed/DEMO-FIRM-05 --objects regulator/sample-feed/objects --registry regulator/sample-feed/registry.json
# expected: reports the planted INV-031 error in snapshot 4 (a deployment that disappeared without being retired), so snapshot 4 is QUARANTINED
```

After any change to `spec/` or `examples/`, regenerate the derived files: `python3 templates/build_workbooks.py`, `python3 templates/viewer/build_viewer.py`, `python3 regulator/gen_sample.py`, `python3 regulator/console/build_console.py`.

## This repository and the taxonomy

The Profile has three governed parts. The **taxonomy** (autonomy tiers and modifiers, business lines, use cases, action classes, controls) lives in its own repository, [mlcommons/agent-reliability-profile-taxonomy](https://github.com/mlcommons/agent-reliability-profile-taxonomy), and is the official source of that vocabulary. This repository holds the **Profile specification** (`spec/`) and the **reference tools**. Each Kit release pins one taxonomy release ([`spec/taxonomy.lock.json`](spec/taxonomy.lock.json)); supported combinations are in [COMPATIBILITY.md](COMPATIBILITY.md).

- Propose vocabulary changes in the taxonomy repository; specification changes and tool fixes here ([governance/review-process.md](governance/review-process.md)).
- Releases follow one checklist shared with the taxonomy ([governance/release-checklist.md](governance/release-checklist.md)).
- The download zip and the Builder skill zip are attached to each GitHub release, with SHA-256 checksums.

## Versions and changes

| Component | Version | Maturity |
|---|---|---|
| Profile Specification, schema, vocabularies | `arp/1.0-rc2` | Normative, release candidate |
| Shared vocabulary (pinned taxonomy release) | taxonomy `0.1.0` | Draft for comment ([COMPATIBILITY.md](COMPATIBILITY.md)) |
| Reference checker and conformance vectors | follows the spec | Reference implementation |
| Profile Builder skill | 0.2 | Reference tool, prototype |
| Workbook template | `arp/1.0-rc2 workbook 0.2` | Tool |
| Profile Lite | `arp-lite/0.1` | Draft |
| Inventory snapshot and feed (Regulator Kit) | `arp-inventory/0.1` | Preview, draft |
| Profile Summary | `arp-summary/0.3-draft` | Design only |

Profiles made under a release candidate carry `"spec": "arp/1.0-rc2"` and must be re-checked when 1.0 is published. The versioning policy is in `spec/SPEC.md` §1; changes are listed in [CHANGELOG.md](CHANGELOG.md).

## Contributing, support, security

- **Contribute** adapters, evidence parsers, domain packs or fixes: [CONTRIBUTING.md](CONTRIBUTING.md).
- **Questions and support:** the MLCommons Financial Services Working Group, participation@mlcommons.org.
- **Report a checker bug or a security problem:** [SECURITY.md](SECURITY.md).
- **Licence:** [Apache License 2.0](LICENSE), copyright 2026 MLCommons. Third-party sources and the fictional-data policy: [NOTICE](NOTICE).
