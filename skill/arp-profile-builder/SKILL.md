---
name: arp-profile-builder
description: Compile a Level 1 (Asserted) Agent Reliability Profile for ONE AI-agent deployment from the institution's own evidence package (policy docs, configuration exports, IAM, approval records, logs). Use when asked to profile an agent, build an Agent Reliability Profile for a deployment, or prepare a Profile for owner sign-off. For a one-row agent inventory use Profile Lite instead. Never signs, never tests, never resolves conflicts, never installs anything.
---

# Agent Reliability Profile Builder (Level 1)

You compile a **Level 1 Asserted Profile** (spec `arp/1.0` release candidate 2; this is skill
version 0.2) for one deployment from the files in an evidence package, then hand it to a named owner. You work the way an examiner
works a file: read everything, cite the artifact behind every value, reconcile documents
against configuration, and record what is absent or contradictory rather than smoothing it over.

You are a compiler, not a summarizer. An unsupported field stays visibly blank.

## Requirements and setup

* **An assistant that can run Python 3.10 or later** on the machine that holds the evidence, with
  `jsonschema` and `cryptography` already installed (the kit's `requirements.txt`). Check first:
  `python3 -c "import jsonschema, cryptography"`. If that fails, **stop and tell the user**. Never
  install packages yourself and never fetch anything from the network.
* **Install:** copy this folder (`skill/arp-profile-builder/`) into your assistant's skills folder,
  or point the assistant at it. Below, `<skill>` is the full path to this folder.
* **A working folder outside the skill and outside the evidence package**, chosen with the user,
  e.g. `mkdir -p <workdir>`. Everything you write goes there; never write inside `<skill>` or the
  evidence package. Run every script by its full path: `python3 <skill>/scripts/manifest.py …`.

## Guardrails (never break these)

1. **Input is the evidence package only.** Read nothing else about the deployment: not the
   web, not other deployments, not your own assumptions about the vendor. Make no network calls
   of your own and install nothing. This skill cannot itself keep evidence inside the institution:
   that depends on how the assistant running it is deployed. Before starting, confirm that the user is working
   in an environment their institution has approved for this evidence; if they are not sure, stop.
2. **Never upgrade provenance.** A policy memo is `document_derived` however confident it
   sounds. Only configuration exported from the running system is `configuration_derived`.
   You never write `measured`: you execute nothing.
3. **Absent beats inferred.** If no artifact is entitled to establish a field (see
   `references/authority-map.md`), record it as `absent` with a note naming what would.
4. **Conflicts stay open.** When two artifacts disagree, record a conflict with both
   citations, `state: open`, and an open finding. The authority map may decide which source
   sets the field's *value* (configuration over a memo for what is deployed), but precedence
   never *closes* the conflict. Only the owner resolves or accepts it.
5. **Never sign and never issue.** Your output has `stage: draft` and no signatures. Only the
   named owner signs, with their own key, after reviewing the pack.
6. **Level 1 only.** Every axis level is 1, `results` is empty, the comparability flag is false.
7. **Keep personal data out of the Profile.** Quote the least text that establishes a field.
   Never copy customer, account, transaction, employee or other personal identifiers into a
   citation or note: replace them with `[redacted]` and cite the locator instead. List in the
   review pack every evidence file that contains personal data, so the owner can decide who may
   see the evidence package. Also keep secrets (keys, tokens, passwords, connection strings) and
   internal hostnames out of citations. Tell the owner in the review pack that redaction is a
   control they must check before the Profile is shared: you may miss an identifier, and evidence
   paths and configuration values can themselves be sensitive (`DISCLOSURE.md` in the Kit).

## Procedure

1. **Locate the package.** Ask for the folder path and the owner's name and role if not given.
   Confirm the deployment id.
2. **Inventory and hash.** Run
   `python3 <skill>/scripts/manifest.py <package> --out <workdir>/evidence.json`. This hashes every
   file and proposes an artifact class for each, listing on screen the word that triggered each
   guess. Correct any class the script got wrong by reading the file, and record every correction
   (file, proposed class, your class, why) for the review pack.
3. **Start from the skeleton.** Run
   `python3 <skill>/scripts/skeleton.py --deployment <id> --institution "<name>" --owner "<name>" --role "<role>" --evidence <workdir>/evidence.json --run-on "<assistant> / <model> / <version>" --out <workdir>/skeleton.json`.
   `--run-on` records which assistant and model compiled the Profile (in `assurance.method`).
   Fill it with a small script (`<workdir>/fill.py`) that loads the skeleton and writes
   `<workdir>/profile.json`, so the fill can be re-run as you read. Every `TODO` must be replaced;
   the checker rejects any that survive (ARP-002). Set `evidence_as_of` to the date of the most
   recent artifact, not today.
4. **Read every artifact.** For each, note which fields it may speak to, using the authority map.
   Record citations as `{evidence_id, locator, verbatim}` with a short verbatim quote.
5. **Fill the four axes** following `references/axis-extraction.md`:
   * autonomy tier, `tier_basis` and approval quality (sample approval records decide T2 vs
     T3; `substantiated` only when real, non-simulated records show substantive review);
   * the six modifiers, each with provenance (usually `owner_attested` or `document_derived`);
   * ODD: business line, use case, population, data, jurisdictions, cost of failure. Every
     field you populate needs provenance (ARP-050); leave a field out rather than guess;
   * model identity in `subject.models` (provider, model, pinned version) and the deployment
     version, from configuration or release records. If absent, say so in the review pack: the
     owner cannot issue without them (ARP-081);
   * actions: map every tool, scope and entitlement to A1–A12; state all twelve as
     permitted, prohibited or out of scope;
   * controls: map each claimed or configured control to the catalogue in
     `spec/vocab/control-catalogue.json`; use `<layer>.x_<name>` only for a control the catalogue lacks.
6. **Reconcile.** Compare every document claim with the configuration that should implement
   it. Each disagreement becomes a conflict and an open finding. A configured control that is
   *stricter* than the policy is still recorded (kind `configuration_stricter_than_mandate`).
7. **Write the bounded claim** in `claim.statement` using the pattern in
   `references/axis-extraction.md` §5, ending "This is a Level 1 Asserted Profile: nothing in it has been tested."
8. **Floors, out of scope, invalidation.** Floors come from the domain and the prohibited set;
   all are `untested`. The out-of-scope statement is usually longer than the claim. The void
   list names the changes that would falsify the configuration evidence you relied on.
9. **Check conformance and loop.** Run `python3 <skill>/scripts/arp_conform.py check <workdir>/profile.json`.
   Fix every error. Do not fix an error by weakening the evidence rule; fix the Profile.
10. **Produce the owner review pack** (`references/owner-review-pack.md`): the draft Profile, a
    one-page summary, every open conflict and absent field, and the decisions the owner must
    make before signing. Tell the owner how to sign:
    `python3 <skill>/scripts/arp_conform.py sign <workdir>/profile.json --role owner --name "<name>" --key <their key>`
    (the signer refuses while `issued_at` or `valid_from` is unset or any rule fails).

## Output

* `<workdir>/profile.json` — conformant draft, `stage: draft`.
* `<workdir>/owner-review.md` — the review pack.
* A short chat summary: tier, permitted and prohibited sets, number of absent fields, number of
  open conflicts. No verdict on whether the agent is safe: Level 1 tests nothing.

## Hard cases

* **Simulated or sample-marked records** (e.g. `simulated: true`) cannot establish approval
  quality or tier. Record the values in the note, set the assessment to `not_assessed`, and open
  a `simulated_evidence` conflict. Where the values would have been decisive, say which way.
* **Document and configuration disagree on a control.** Configuration sets `present` (it
  outranks a document on what is deployed), and the disagreement is still an open conflict.
  Use `null` only when no artifact can establish the control.
* **An allowlist entry with no tool behind it.** The class is not permitted as built (no tool can
  exercise it). Record it as prohibited with a configuration finding, not a conflict: the two
  artifacts do not disagree about what is deployed.
* **A rendering that says more or less than its machine-readable sibling.** Extra content is
  `document_derived`, cited to the rendering; anything the rendering omits (for example a
  `simulated` marker) is a `rendering_vs_source` conflict.
* **Records that look synthetic but are not marked** (identical timestamps, repeated ids): record a
  `suspected_simulated_evidence` conflict and do not use them to substantiate anything.
  `evidence_as_of` is then the date of the most recent artifact you did rely on.
* **Conflict kinds.** Use the values in `spec/vocab/conflict-kinds.json`; `other` with a description
  for anything else.
* **A control the catalogue lacks.** Use `<layer>.x_<name>` and list it in the review pack.
  `spec/vocab/control-catalogue.json` lists candidates already proposed for v1.1.

## When to stop and ask

* The package has no configuration exports at all (everything would be `document_derived`):
  say so; the Profile is still valid but the owner should know it rests on documents alone.
* You cannot tell which deployment an artifact belongs to. If you can proceed, carry it as an
  open finding (kind `other`) naming the identity question, and put it first in the review pack.
* The tier cannot be determined (fallback or envelope unspecified): record tier **U** with an
  `unprofiled` open finding. That is a legitimate result, not a failure.
