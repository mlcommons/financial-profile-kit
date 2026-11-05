# What each artifact contains, and what to review before you send it

**Status:** release candidate 2 of arp/1.0, prepared by the MLCommons Financial Services Working
Group for pilot use and comment. Not a final MLCommons standard, certification scheme or
endorsement.

The Kit runs locally and sends nothing anywhere. That does not make its outputs safe to share.
A full Profile is a detailed record of how an agent is built and controlled: it is **not** just
a list of hashes. This guide sets out what each artifact contains, who it is for, and the review
it needs before it leaves the team that owns it.

## The four artifacts

| Artifact | What it is | Normally goes to |
|---|---|---|
| **Evidence package** (Profile Package) | The source files a Profile is compiled from: policies, product documents, configuration and registry exports, IAM and entitlement exports, approval records, logs, test traces, assessor reports | Stays inside the institution. An independent assessor (Level 3) sees what it needs, on site or under its engagement terms |
| **Full Profile** (`spec/profile.schema.json`) | One JSON record per deployment: the bounded claim, assurance levels, results, floors, findings, provenance and the evidence manifest | Internal: owner, risk, model risk, audit. A supervisor, **on request**, after disclosure review |
| **Supervisory submission** (`spec/FEED.md`) | An inventory snapshot: one Profile Lite record per deployment, plus a hash commitment to each full Profile | The institution's supervisor. Full Profiles follow only when the supervisor asks for one |
| **Peer Profile Summary** (`spec/profile-summary.schema.json`, design only) | A derived summary for the proposed Profile Exchange: coarse fields only | Peers, only if the Exchange is built and only after its own review |

## What a full Profile contains, field by field

| Part of the Profile | What it can reveal | Sensitivity |
|---|---|---|
| `subject` (institution, deployment id and version, description, models, vendor products, platform baseline) | Which models and vendors the institution uses, and where | Commercially sensitive; vendor relationships |
| `issuance` (owner and issuer names and roles, dates) | Named individuals and their roles | Personal data |
| `claim.statement`, autonomy tier and modifiers, approval quality | How much the agent does unsupervised; approval timings and rates | Operationally sensitive |
| `claim.odd` (use case, population, data classes, jurisdictions, cost of failure, operational scope) | Customer segments, data classes handled (for example PII, PCI, MNPI), where the agent operates | Sensitive; may indicate business strategy |
| `claim.actions` and `out_of_scope` | What the agent can and cannot do, including payments, filings and access changes | Security-relevant: an attacker learns what is reachable |
| `claim.controls` | Which controls exist, which are absent, at which layer | **Security-relevant**: a map of the control envelope and its gaps |
| `provenance` (citations with **verbatim quotations** and locators) | Short extracts from policies, configuration files and logs | Can contain configuration values, internal hostnames, identifiers or personal data |
| `evidence` (ids, **file paths**, content hashes, artifact classes) | Internal repository and file names, system names, folder structure | Internal information; paths can name systems, projects or people |
| `results` and `floors` | What was tested, how, and what failed; scenario names | **Security-relevant** for any contradicted or not-established result |
| `status` (open findings, accepted gaps, risk acceptances, exceptions, limitations) | Known weaknesses and who accepted them | **Highly sensitive**: a list of known control failures |
| `conflicts` | Where documents and configuration disagree | Sensitive: shows policy and practice diverging |
| `invalidation`, `assurance` (test environment, fidelity, assessors, reproduction) | How testing was done, by whom, in which environment | Moderately sensitive |
| `signatures`, `evidence_manifest` | Signer names, roles, organisations, public keys | Personal data (names); public keys are not secret |

The skill and the templates try to keep identifiers out (for example the Builder skill quotes the
least text needed and replaces customer, account and staff identifiers with `[redacted]`). **That
is a control that must be checked, not a guarantee.** A model can miss an identifier; a file path
can carry a name; a configuration value can be a secret.

## Disclosure review before anything leaves the owning team

Before a full Profile, a snapshot or a summary is sent outside the team that owns it (to another
department, a supervisor, a vendor, an assessor or a peer), a named reviewer:

1. **Confirms the recipient and purpose**, and that the recipient needs the full Profile rather
   than the Lite record.
2. **Reads every free-text field and citation** for personal data, customer or account
   identifiers, secrets (keys, tokens, passwords, connection strings), internal hostnames and
   anything the institution's information classification does not allow for that recipient.
3. **Checks evidence paths** for system, project or personal names.
4. **Decides on open findings and failed or contradicted results**: they are part of the claim
   and must not be removed, but the recipient's handling must suit their sensitivity
   (confidential supervisory information, for example).
5. **Records the review** (who, when, what was sent, to whom) in the institution's own register.

Where the assistant that runs the Builder skill is hosted outside the institution, the evidence it
reads has already left: use an assistant your institution has approved for that evidence.

## Making a redacted version

A redacted Profile is a **new document**, not an edited copy of the signed one. Editing a signed
Profile in place leaves its signatures behind, and the checker then reports them as no longer
covering the file (ARP-091). Follow these steps (`conformance/test_redaction.py` runs them on both
worked examples):

1. **Start the derivative** from the issued Profile:
   `python3 conformance/arp_conform.py redact-prepare ISSUED.json --out REDACTED.json`
   This copies the Profile without its signatures, makes it a draft, gives it a new `profile_id`
   (suffix `-redacted-1`; change it with `--suffix`) and adds a limitation saying it is a redacted
   derivative. It also writes `REDACTED.json.internal-link.txt` with the original's id and
   canonical hash. **Keep that file internally and do not send it**: it links the two documents
   for you, and a recipient could use the hash to test guesses about the redacted content.
2. **Redact** `REDACTED.json`: replace text with `[redacted]`, and add to `status.limitations` what
   was redacted and why. Never remove an open finding, a failed floor or a contradicted result.
3. **If you changed any evidence entry** (for example an evidence path) **and the Profile has a
   signed evidence manifest** (any Profile with a Level 2 or 3 axis), sign the manifest again,
   or the check fails with ARP-019:
   `python3 conformance/arp_conform.py sign-manifest REDACTED.json --signer "<manifest signer>" --key owner.key --in-place`
4. **Check** it: `python3 conformance/arp_conform.py check REDACTED.json`. It must conform before
   anyone signs.
5. **The accountable owner signs it**, under the name in `issuance.owner.name` (another name is
   refused): `python3 conformance/arp_conform.py sign REDACTED.json --role owner --name "<owner's name>" --key owner.key --out REDACTED.issued.json`.
   Where the Profile names an issuer other than the owner, the issuer signs too (`--role issuer`).
   **For any Level 3 axis, the independent assessor must sign again** (`--role assessor
   --organisation "<assessor>"`); the original assessor signature does not cover the redacted
   document.
6. **Check the signed result** (`check REDACTED.issued.json`) and send only that file.

A redacted Profile carries the same levels and disclosures as the original, but the recipient
can no longer check redacted citations or paths against evidence; the limitation added in step 1
says so.

## In inventory snapshots

A snapshot carries Profile Lite fields only (`spec/FEED.md` §2): status, business line, use
case, tier, action classes, peer-set control statuses, models, vendor, owner role. Those are
already sensitive in aggregate (a supervisor can see every agent that moves funds without a cap),
and they are confidential supervisory information. A full Profile is read only when a supervisor
drills into a deployment, and each read is logged by the firm.
