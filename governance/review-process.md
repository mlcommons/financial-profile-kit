# Review Process

## Where a change goes

| Change | Where to propose it | Who approves |
|---|---|---|
| A term in the shared vocabulary (tier, modifier, business line, use case, action class, control) | The [taxonomy repository](https://github.com/mlcommons/financial-profile-taxonomy) | Working Group; reaches the Kit through a taxonomy release |
| A rule for a valid Profile, a schema, a conformance vector, or a specification-owned vocabulary (provenance classes, invalidation triggers, dispositions, conflict kinds, peer-control sets) | This repository: *Specification change* issue | Working Group |
| A tool fix or improvement that does not change what is conformant | This repository: pull request | Kit maintainers |
| A security problem or a checker that accepts what it should reject | Privately, per [SECURITY.md](../SECURITY.md) | Kit maintainers |

When a change touches both repositories (for example a new control that also needs a new rule), the Working Group approves it once, and the taxonomy release lands first.

## Specification changes

Pipeline: proposal → Working Group discussion → editor's draft (spec, schema, vectors and reference checker together) → Working Group approval → merge with a CHANGELOG entry.

| Criterion | Question |
|---|---|
| Source | Is it consistent with the preprint, or does it record a deliberate departure? |
| Testability | Does the rule have a rule id, an RFC 2119 keyword and at least one conformance vector? |
| Compatibility | After 1.0, does it avoid making a conformant Profile non-conformant? |
| Honesty | Does it keep Profiles from claiming more than their evidence supports? |
| Disclosure | Does it avoid pushing institutions to share more than they need to? |

## Tool changes

Every pull request keeps all tests passing (README, *Tests*), regenerates derived files, and keeps the Builder skill's bundled copy in step (`tools/sync_skill_bundle.py --check`). Example data stays fictional and labelled "(fictional)".
