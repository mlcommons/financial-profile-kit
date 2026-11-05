# ARP Supervisory Feed (arp-inventory/0.1, draft)

**Status: release candidate 2 of arp/1.0, prepared by the MLCommons Financial Services Working Group for pilot use and comment. Not a final MLCommons standard, certification scheme or endorsement.** The feed format is a draft (`arp-inventory/0.1`) and may change more than the Profile specification before 1.0.

How a supervisor sees a firm's agent inventory and its Profiles directly, without template requests or documents sent back and forth.

## 1. The idea in one paragraph

Today a supervisor who wants to know what agents a bank runs sends a template request, the bank fills it in, and the two sides exchange spreadsheets and corrections. The feed replaces that exchange with one standing, machine-readable object: the **inventory snapshot**. The firm keeps the snapshot current, and the supervisor's console reads it. The firm can publish the snapshot for the supervisor to pull, push it to the supervisor, or upload it as a file. The object and its checks are the same every way. Each snapshot is signed by the firm and linked to the one before it, so the supervisor holds a tamper-evident history. Trends, changes and outliers come from that history, not from a new request.

## 2. What is exchanged, and what leaves the institution

| Object | Schema | What it is |
|---|---|---|
| Inventory snapshot | `spec/inventory.schema.json` (`arp-inventory/0.1`) | Every agent deployment the firm runs, in development or retired in this period, as one Profile Lite record each (`spec/profile-lite.schema.json`, rules in `spec/LITE.md`). Where a full Profile exists, the record also carries a commitment to it: id, stage, headline level, validity and canonical hash. Signed by the firm. |
| Full Profile | `spec/profile.schema.json` | Fetched or delivered separately and **addressed by its hash**, so the supervisor can confirm it is exactly the document the firm committed to. |
| Receipt (push only) | §4 | The supervisor's signed acknowledgement of a snapshot's hash. It gives the firm proof of submission. A receipt is a separate document; it is never added to the snapshot. |

**What leaves the institution, and to whom.** Nothing leaves unless the firm sends it or lets its supervisor read it. To its supervisor, a firm sends inventory snapshots and, when the supervisor asks to see one, the full Profile of a deployment. The evidence behind a Profile (the Profile Package: source documents, traces, test outputs) stays with the firm. A full Profile is not just hashes: it contains evidence paths, short verbatim citations, configuration values, people's names and roles, and findings, so it is reviewed before it is sent (`DISCLOSURE.md`). Nothing in the feed goes to MLCommons or to other firms. The Profile Exchange (a separate, gated proposal) would receive only a derived Profile Summary, never a snapshot or a full Profile.

A snapshot is immutable once published. To correct one, the firm publishes a new snapshot with `trigger: "correction"`.

## 3. Pull: the firm publishes and the supervisor reads

The firm hosts a read-only endpoint. The supervisor's console reads it on the supervisor's schedule.

```
GET {base}/arp/v0/inventory                  -> index: firm_id, latest {sequence, as_of, hash}, and every snapshot {sequence, as_of, hash, href}
GET {base}/arp/v0/inventory/{sequence}       -> one snapshot (immutable; long cache; ETag = its hash)
GET {base}/arp/v0/objects/{sha256-hex}       -> a full Profile, addressed by its canonical hash
```

- **Access.** Mutual TLS with a certificate issued to the supervisor, or OAuth 2.0 client credentials with scope `arp.read`. Only named supervisory clients may read.
- **The firm sees every read.** It logs each access, and the log is available to both sides.
- **Polling is cheap.** `If-None-Match` on the index returns `304` when nothing has changed.
- **Integrity.** The console recomputes every hash it fetches. A document whose hash differs from the commitment is rejected.
- **Same origin, same firm.** The console fetches only from the origin of the endpoint in its key register, and refuses a pulled snapshot whose `institution.firm_id` is not the firm being pulled. An index entry pointing elsewhere is refused, not followed.

## 4. Push: the firm submits and the supervisor stores

The supervisor hosts the endpoint. The firm sends each new snapshot as it is produced.

```
PUT  {base}/arp/v0/firms/{firm_id}/objects/{sha256-hex}   -> deposit a full Profile first (idempotent)
POST {base}/arp/v0/firms/{firm_id}/inventory              -> submit a snapshot; returns a receipt
```

The supervisor runs the same checks on receipt (§6) and returns a **receipt**, a separate JSON document (draft format):

```
{ "receipt_spec": "arp-feed-receipt/0.1",
  "firm_id": "...", "snapshot_sequence": 4, "snapshot_hash": "sha256:...",
  "received_at": "2026-10-02T09:14:00Z", "outcome": "accepted" | "rejected",
  "findings": [ {"rule": "INV-031", "severity": "error", "path": "records", "message": "..."} ],
  "signatures": [ {"role": "supervisor", "name": "...", "alg": "ed25519", "public_key": "...", "signed_hash": "sha256:...", "value": "..."} ] }
```

The receipt is signed over its own canonical hash (excluding `signatures`). A rejected snapshot lists exactly what to fix, which replaces the email rounds over template errors. The kit does not yet ship a receipt schema or tool; this format is a draft for pilots.

Push suits supervisors whose legal or security framework prefers the firm to send rather than the supervisor to read. It is also closest to how existing reporting portals work.

## 5. File: the same object, no infrastructure

A firm with neither endpoint can still produce a snapshot. It converts its Profile Lite workbook with `regulator/arp_feed.py build`, then uploads the signed snapshot through an existing secure portal. The console opens the file directly. This gives an adoption ladder (file, then push, then pull) with no change to the data or the checks.

`build` prefers the issued version when a draft and an issued Profile share an id, refuses two issued Profiles with the same id, and does not write a snapshot that fails its own checks.

## 6. Checks (rules INV-001 to INV-040)

Implemented in `regulator/arp_feed.py` (`check` for one snapshot, `chain` for a firm's history) and in the Supervisory dashboard demo. `regulator/console/test_console.mjs` checks that the two agree on the sample feed and on broken feeds. Where they differ, it is listed below the table, and the Python result governs.

| Rule | Requirement |
|---|---|
| INV-001 | The snapshot is valid JSON with no duplicate keys and no `NaN` or `Infinity`, and matches `inventory.schema.json`. Patterns match the whole value (a trailing newline does not match), and dates and date-times must be real calendar values (`2026-99-99` fails). A snapshot that fails INV-001 is listed with its findings and is not used in any view. |
| INV-010 | Every record passes the Profile Lite rules in `spec/LITE.md` (LITE-010 to LITE-013 are errors; LITE-W01 is reported as a warning). |
| INV-011 | Each `inventory_ref` appears once. |
| INV-012 | Every record's `institution` equals the snapshot's institution name. |
| INV-020 | A record that claims a full Profile (`profile_level` L1 to L3) carries a commitment to an **issued** Profile whose `profile_id` equals the record's `full_profile_ref` and whose headline equals the level. A record with `profile_level` `none` must not commit to an issued Profile. |
| INV-021 | When the full Profile document is available: its canonical hash equals the commitment; every commitment field (`profile_id`, `stage`, `headline`, `valid_until`) equals the document's; the document's `subject.institution` is the snapshot's institution and its `subject.deployment_id` is the record's `inventory_ref`; and it passes the Profile checker (`conformance/arp_conform.py`) without errors. The document is looked up by the committed hash and, failing that, by the committed `profile_id`: if a document with that `profile_id` is held but its hash is not the committed one, that is an error (deliver the committed version or correct the commitment), and the record is still checked against the held document (INV-023), so a wrong hash cannot hide a record that contradicts its Profile. A commitment is "not available", and not an error, only when no document with that hash or that `profile_id` is held. |
| INV-022 (warning) | An issued Profile whose `valid_until` is before the snapshot's `as_of` has expired. The document's `valid_until` is used when the document is available, otherwise the commitment's. |
| INV-023 | When the full Profile document is available and matches its commitment, the record agrees with it on every field they share: business line, use case (and catalogued use case id and models when both state them), autonomy tier and tier basis, permitted and prohibited action classes, accountable owner role, `human_approval` for a T2 Profile, and the status of each peer-set control. The Profile's values are derived exactly as `arp_lite.py from-profile` derives a Lite record; several results on one field count as the most severe (SPEC §4). A difference is an error unless the record declares it in `divergence` (the fields, the date it began and the reason), which makes it a labelled warning. A divergence dated after the snapshot's `as_of` is an error. |
| INV-030 | The chain holds: the previous snapshot is for the same `firm_id`; `sequence` is one higher; `previous_hash` equals the previous snapshot's canonical hash; `as_of` is not earlier. Sequence 1 has `previous_hash` null. Checked over a firm's whole feed, one chain per `firm_id` (another firm's snapshot in the same folder or feed never affects this firm's chain): a missing sequence is an error; **two different snapshots claiming the same sequence are a fork**, an error on both, and neither is used as the firm's position. Every later snapshot of that firm is also an error ("follows an unresolved fork") until the supervisor confirms with the firm which snapshot is genuine and removes the other, so no change is ever computed across a fork. An identical copy of a snapshot counts once. When a single snapshot is checked without its predecessor, the chain is reported as not checked (warning). |
| INV-031 | Nothing disappears silently. Every deployment in the previous snapshot that was not already `retired` appears again, marked `retired` if it has stopped. A retired deployment may be dropped from the snapshot after the one that reports it retired. |
| INV-040 | The snapshot carries an `institution` signature that covers its canonical hash and verifies. The signature is made over a signature statement, not the bare hash: the RFC 8785 canonical JSON of `{context: "arp-inventory/0.1 snapshot signature", alg, role, name, public_key, signed_hash}`, so editing the signer's name, role or key after signing breaks it, and the signing key is the firm's key in the supervisor's **key register** (§7): the registered `public_key`, or a `retired_keys` entry whose `last_sequence` is at least this snapshot's sequence. A firm that is not in the register is an error. Without a register, signers are reported as `UNVERIFIED SIGNER` (warning), and a signing key that differs from the previous snapshot's is an error. |

The canonical hash is the same as for Profiles (`spec/SPEC.md` §7), computed over the snapshot without `signatures`.

**Trusted and quarantined snapshots.** A snapshot is **trusted** only when it has no error and no warning other than INV-010 (a Lite catalogue mismatch), INV-022 (an expired Profile) or INV-023 (a declared divergence); those three are labelled wherever the data is shown. Every other snapshot is **quarantined**: a failed or absent signature, a signer not in the key register or a key the register does not allow, a broken chain, a gap or a fork, a commitment that does not match its Profile, a record that contradicts its Profile, a schema failure, or any other error. Without a key register (`--no-register`, or before one is loaded in the console) every signer is unverified, so every snapshot is quarantined. A browser that cannot verify Ed25519 signatures shows "verification unavailable" and treats every snapshot as unverified.

Quarantined snapshots are listed, with their findings, only in the console's Feed view and in a banner. They never feed a firm's position, totals, pivots, trends, outliers, changes or the inventory: each firm is shown at its last trusted snapshot. `arp_feed.py check` ends with `TRUSTED` or `QUARANTINED`; `chain` marks each snapshot, and `chain --json` gives `trusted` and `quarantine_reasons` for each. A firm corrects a quarantined snapshot by publishing a new one (`trigger: "correction"`). When a quarantined snapshot sits between two trusted ones (for example one that fails INV-011 or INV-031 but is authentic and chained), the later snapshot is compared with the last trusted one, and the Changes and firm views say so. A file opened in the console that is not strict JSON, or is neither a snapshot nor a Profile, is listed in the Feed view with an INV-001 finding.

**What the console shows of an unverified firm.** A firm's name, short name and peer group come only from the supervisor's key register. A firm that is not in the register is shown everywhere as "Unregistered firm (<firm_id>)": its self-declared name is unverified and never displayed.

**Known differences between the console and `arp_feed.py`.** A browser that cannot verify Ed25519 signatures, or has no Web Crypto at all, reports an INV-040 warning ("verification unavailable"; use `arp_feed.py check`) instead of a verdict, and treats every snapshot as unverified. The console always works with a register: the sample register when the sample feed is loaded, otherwise the register the user loads; until one is loaded, every signer is unverified and every snapshot is quarantined.

**Exit codes of `arp_feed.py`:** 0 conforms, 1 does not conform, 2 usage error (for example no `--registry` and no `--no-register`), 3 input that could not be read.

## 7. Creating your firm register

The key register is the supervisor's list of firms in scope and the key each firm signs with. It is the trust anchor for INV-040: a signature proves only that someone holding a key signed, and the register says whose key it should be. Keep it under the supervisor's own control. The console loads it with **Load key register…**, separately from snapshot files, and never accepts a register from the snapshot picker or from a firm's endpoint.

```
{ "registry": "arp-feed-registry/0.1",
  "firms": [
    { "firm_id": "<your reference for the firm>",
      "name": "Firm name as it appears in snapshots",
      "short": "Short label", "peer_group": "Large deposit-takers",
      "delivery": "pull" | "push" | "file",
      "endpoint": "https://feed.firm.example/arp/v0",
      "public_key": "<base64 Ed25519 public key>",
      "retired_keys": [ { "public_key": "<base64>", "last_sequence": 12 } ] } ] }
```

`endpoint` is needed only for pull; `retired_keys` only after a key change.

1. Ask each firm for its snapshot signing public key through a channel you already trust (for example the secure portal, or a signed letter from a senior manager), never from a snapshot or the firm's feed endpoint.
2. Record it with the firm's reference number, name, peer group and delivery route.
3. **Key rotation.** When a firm changes its key, move the old key to `retired_keys` with the last sequence it may sign, and add the new key as `public_key`. A snapshot signed with a key not in the register fails INV-040.
4. Re-run `arp_feed.py chain DIR --registry REGISTER.json` after any change to the register.

The kit's `regulator/sample-feed/registry.json` is a **sample** register of five fictional firms (`DEMO-FIRM-01` to `-05`) with DEMO-ONLY keys derived from a public seed. Never use it for real data.

## 8. When a new snapshot is due (policy, set by each supervisor)

The standard fixes the object, not the cadence. A starting point for a supervisor's policy:

- **Scheduled:** at least quarterly, `as_of` the quarter end.
- **Material change:** within a set number of business days of any change that would void or partly void a full Profile under the preprint's §5.3 triggers (identified in `vocab/invalidation-triggers.json`, being added in this release candidate), and of any change to the inventory itself:
  - the deployment's domain widens (a new operational design domain or use case);
  - it newly permits a higher-consequence action class (in particular A8 to A12);
  - a critical control is removed, or a peer-set control becomes `absent` or `tested_not_shown_to_hold`;
  - it gains new access, or its accountable owner changes;
  - its multi-agent topology changes;
  - its model or harness changes;
  - the Platform Baseline Profile it is anchored to is voided;
  - a deployment enters production, or its autonomy tier increases;
  - a full Profile is withdrawn or expires.
- **On request:** the supervisor asks for a snapshot outside the schedule.

## 9. Governance

- **Bilateral and confidential.** Data flows only between the firm and its supervisor and is confidential supervisory information. The Working Group intends to publish the format, the checks and the open-source console; it never receives inventory data.
- **No new powers.** The feed is a format and a delivery channel for information a supervisor can already request. Whether the supervisor pulls or the firm pushes is the supervisor's choice under its existing framework.
- **Minimum necessary.** The snapshot carries Profile Lite fields only. A full Profile is read when a supervisor drills into a deployment, and each read is logged.
- **Reported, not verified.** A Lite record is what the firm reports. The feed proves who said it, when, and that it has not been altered since. It does not prove that it is true. The full Profile's levels and disclosures say what was tested.

## 10. What the console derives (and does not)

From the snapshot history, the Supervisory dashboard demo derives:

- the portfolio and firm overviews;
- pivot cuts by any field;
- trends across snapshots;
- the changes between any two snapshots;
- rule-based deployment flags;
- firm-level outliers against a peer group the supervisor defines.

All of these are derived from **trusted snapshots only** (§6). Data that is usable but carries a labelled warning (an expired Profile, a declared divergence between a record and its Profile) is shown with that label in the deployment view.

The flags and outlier tests are **supervisory heuristics configured in the console, not part of the standard**. They point a supervisor to where to look. They are not findings.

The console opens empty. **Load sample (fictional) feed** loads the sample, which stays badged as sample data while it is loaded and is cleared before any real register or snapshot is opened.
