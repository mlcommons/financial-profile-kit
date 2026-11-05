# Compatibility

The Agent Reliability Profile has three governed parts, each with its own version number:

| Part | Where it lives | Current version | Who approves changes |
|---|---|---|---|
| **Taxonomy** (shared vocabulary: autonomy tiers and modifiers, business lines, use cases, action classes, controls) | [mlcommons/financial-profile-taxonomy](https://github.com/mlcommons/financial-profile-taxonomy) | 0.1.0 | Financial Services Working Group |
| **Profile specification** (rules for a valid Profile, schemas, specification-owned vocabularies) | this repository, `spec/` | `arp/1.0-rc2` | Financial Services Working Group |
| **Reference tools** (checker, Builder skill, workbooks, Viewer, Regulator Kit preview) | this repository | Kit release `1.0-rc2` | Kit maintainers |

## What this Kit release supports

| Kit release | Profile specification | Taxonomy release (pinned) | Status |
|---|---|---|---|
| 1.0-rc2 | `arp/1.0-rc2` | 0.1.0 | Release candidate, pilot use |

The pinned taxonomy release is recorded in [`spec/taxonomy.lock.json`](spec/taxonomy.lock.json). The checker validates codes against the vocabulary bundled in `spec/vocab/`, and reports (ARP-003) when a Profile names a vocabulary version different from its own.

## Rules

1. **Every Profile names its versions.** An issued Profile records `spec` and `vocab_versions` (`spec/SPEC.md`, ARP-003), so a reader knows which definitions and rules apply.
2. **Codes are permanent.** A taxonomy code is never renumbered or given a new meaning. A changed meaning gets a new code; the old one is retired, never reused, and a mapping from old to new is published with the taxonomy release.
3. **Old releases stay available.** Each tagged taxonomy and Kit release remains downloadable. This table states which combinations each Kit release supports.
4. **Migration is a reissue.** An issued Profile is never rewritten. Moving it to a new specification or taxonomy version means re-checking it and having its owner sign it again. Profiles issued under a release candidate must be re-checked, and reissued if needed, once 1.0 is published (`spec/SPEC.md`, preamble).
5. **After 1.0**, a minor specification version may add optional fields and warnings but must not make a conformant Profile non-conformant (`spec/SPEC.md`, preamble).

## How the Kit takes a taxonomy release

1. The taxonomy repository tags a release and its `scripts/export_vocab.py` writes the vocabulary files in this Kit's format.
2. A Kit maintainer copies the taxonomy-owned content into `spec/vocab/`, updates `spec/taxonomy.lock.json`, runs `python3 tools/sync_skill_bundle.py`, regenerates the derived files (README, *Tests*), and adds a CHANGELOG entry.
3. `python3 tools/check_taxonomy_vocab.py --taxonomy <checkout>` must report no identifier or assignment mismatches. CI runs it against the pinned tag.

## Known differences awaiting reconciliation (taxonomy 0.1.0, Kit 1.0-rc2)

Identifiers and assignments match exactly. Seven wording differences remain; the check lists them without failing until the next Kit release candidate, which should run it with `--strict`.

| Vocabulary | Term | Taxonomy 0.1.0 | Kit 1.0-rc2 | Proposed resolution |
|---|---|---|---|---|
| Business lines | `markets` | Markets and capital markets | Markets | Kit adopts the taxonomy label (preprint §4.2) |
| Business lines | `internal_corporate` | Internal / corporate functions | Internal functions | Kit adopts the taxonomy label (preprint §4.2) |
| Modifiers | `data_authority`, `reversibility_profile`, `accountability`, `population_scope` | Preprint wording | Kit's edited wording | Taxonomy adopts the Kit's wording, as it did for the autonomy tiers |
| Modifiers | `stack_composability` values | `predefined`, `dynamic` | adds `not_assessed` | Decide whether "not assessed" is a taxonomy value or a Profile recording state owned by the specification |
