# Agent Reliability Profile — Specification arp/1.0-rc2

**Status:** release candidate 2 of arp/1.0, prepared by the MLCommons Financial Services Working
Group for pilot use and comment. Not a final MLCommons standard, certification scheme or
endorsement. Field names and rules may change before 1.0.

**Source.** The concepts come from the preprint *Agent Reliability Profiles in Financial
Services* (arXiv:2610.04123v1, October 2026): Levels 1–3 plus a separate benchmark comparability
flag; autonomy tiers T0–T4 plus the residual status U; action classes A1–A12; the 55-control
catalogue. The preprint is the conceptual source. This document is normative for files: where
the preprint describes and this document specifies, this document governs what a conformant
file contains.

**Identifier.** A Profile written against this candidate carries `"spec": "arp/1.0-rc2"`.
Checkers MUST reject any other value. A Profile issued under a release candidate is not a 1.0
Profile; it MUST be re-checked, and re-issued if needed, once 1.0 is published.

**Schema identifiers.** The schemas' `$id` values are plain URNs (`urn:arp:1.0-rc2:<name>`) and stay so
through the pilot. They move to mlcommons.org URLs at 1.0 only if MLCommons commits to hosting them permanently.

**Path to 1.0.** This candidate freezes as arp/1.0 once (a) at least two independent
implementations pass the conformance vectors and (b) the pilot cohort has produced and reviewed
real Profiles. Until then, changes are allowed, each with a changelog entry and regenerated vectors.
After 1.0, a minor version may add optional fields and warnings but MUST NOT make a conformant
Profile non-conformant.

The key words MUST, MUST NOT, SHOULD and SHOULD NOT are used as in RFC 2119. Lowercase "may"
and "should" are not requirements. Text in this document that carries no rule id and no
RFC 2119 keyword is explanatory.

## 1. Precedence

1. **This document is normative.** Where anything else disagrees with it, this document wins.
2. **The schema and the conformance vectors implement it.** A disagreement between them and
   this document is a defect in them.
3. **Reference tools** (the checker, the Builder skill, a Validator, the Viewer) are one
   implementation among many and carry no authority of their own.

The same order applies to the companion formats in this folder (`profile-summary.schema.json`,
and, in their own documents, Profile Lite and the inventory feed).

## 2. What this specification governs

* **The artifact.** A Profile is one JSON document per agentic deployment, valid against
  `profile.schema.json` and the rules in §5. Its shape is the same at every level.
* **The vocabularies** in `vocab/`: autonomy tiers and their six modifiers, action classes, the
  55-control catalogue, use cases (ODD.1–ODD.52), business lines, provenance classes,
  dispositions, conflict kinds, invalidation triggers, and the peer control set used by the
  Profile Summary. Each vocabulary file carries its own `version`. An issued Profile records the
  versions it was written against (ARP-003).
* **Document conformance.** A Profile conforms when it meets every rule in §5.

Document conformance says the Profile is well-formed, internally consistent, honestly
labelled and signed. It does **not** say the assertions are true, the tests were adequate, the
agent is safe or compliant, or that the signer is who they say they are. A conformant Level 2
Profile may disclose a contradicted control. See `CONFORMANCE.md` at the kit root.

Not governed yet: tool conformance for Builders and Validators (golden evidence packages and
reference deployments with known answers), and any certification of assurance quality. A tool
can show that the Profiles it produces pass the conformance suite; that is not a certification
of the tool.

**Out of scope for this candidate: Platform Baseline Profiles.** The preprint (§2.5) describes a
Profile carried by an agent platform whose claim is a ceiling on every hosted session. This
schema cannot express that claim (an autonomy ceiling in place of a tier, the six platform
properties). A platform MUST NOT issue a Platform Baseline Profile with this schema. A
deployment Profile MAY anchor to a platform's baseline through `subject.platform_baseline`; such
an anchored Profile is void if the parent claim is void (ARP-083).

## 3. Field ids

Every assertable field has a dotted id whose first segment is its axis: `autonomy.tier`,
`autonomy.approval_quality`, `autonomy.modifiers.<name>`, `odd.<key>`, `actions.A1`–`actions.A12`,
`controls.<control_id>`. The **claim fields** of a Profile are its populated fields: the tier,
the six modifiers, approval quality where present, every non-empty ODD key, every action class
stated as permitted or prohibited, and every listed control. The statement is not a field.

## 4. Assurance and provenance

* `assurance.axes` holds one production level per axis; `assurance.headline` is their minimum.
  Level 1 (Asserted): compiled from institutional evidence, nothing executed. Level 2
  (Validated): the institution ran tests against its own deployment. Level 3 (Verified): the same
  Validator and the same conformance requirements, operated and signed by a qualified
  independent assessor, with its own signed report.
* `assurance.assessors` records, for each axis separately, who stands behind that axis's level:
  `institution` for Levels 1 and 2, `independent_assessor` (named organisation and report) for
  Level 3. An institution may obtain independent verification for one axis while self-testing
  the rest (preprint §6.2).
* `assurance.coverage` shows, for each axis at Level 2 or 3, how many claim fields it has, how
  many were tested and how many were judged. The level says who tested and how; coverage says
  how much. Minimum coverage is a matter for policy, not for this specification.
* The benchmark comparability flag is separate from the levels and never enters the headline.
  It adds comparability under reference conditions, not assurance about production behaviour.
* Every claim field carries one provenance class, weakest first: `absent` < `owner_attested` <
  `document_derived` < `configuration_derived` < `measured`. Only an executed test confers
  `measured` (ARP-011). `document_derived` means extracted from a signed institutional document.
* **Precedence of sources is not resolution of conflicts** (ARP-100). Where the Builder's
  authority map ranks one source above another (configuration over a policy memo for what is
  deployed), the higher source sets the field's value, and the disagreement is still recorded as
  an open conflict for the owner.
* **Tier basis.** `asserted` means the tier as configured or documented. `substantiated` means
  approval-quality evidence supports it. In this candidate `substantiated` is defined for T2
  only. Simulated or sample-marked records cannot substantiate (ARP-041).
* **Floors** are pass-or-fail conditions set before any run. They cannot be offset by good
  results elsewhere: a failed floor blocks issuance (ARP-061).
* **Several results on one field.** A field may be tested more than once (several scenarios, a
  re-run). Its disposition is the most severe of its results, in this order: `contradicted`,
  then `held_by_agent_only`, then `not_established`, then `held`. A later `held` never hides an
  earlier `contradicted`. Every tool that summarises a field (a viewer, an inventory row, a peer
  summary) MUST use this aggregation and MUST show that other results exist; every result stays
  in `results` (ARP-071).
* **Evidence identifiers** are unique within a Profile, so each citation resolves to exactly one
  file (ARP-055).
* **The level is not the outcome.** The assurance level says how the evidence was produced and
  who stands behind it; coverage says how much was tested; the results, floors and open findings
  say what happened. A Level 2 Profile can carry a contradicted control as an open finding, and
  readers must see all three. Use-case assessment policies that set minimum coverage and
  critical-boundary floors are pilot work (README, "Public pilot: Level 1"); until they exist,
  Level 2 and 3 Profiles are for Working Group pilots with assessment support.

## 5. Conformance rules

Severity is **error** unless the rule says warning. A Profile conforms when no error applies.

| Rule | Requirement |
|---|---|
| ARP-001 | The document MUST be a JSON object encoded as UTF-8 (a leading byte-order mark is ignored), with no duplicate member names, no `NaN` or `Infinity`, no unpaired surrogates, and no number whose magnitude is 2^53 or more. It MUST validate against `profile.schema.json`, with `date` values as `YYYY-MM-DD` calendar dates and `date-time` values as RFC 3339 timestamps with an offset, both checked as real dates. Patterns match the whole string. |
| ARP-002 | No string may contain the placeholder words `TODO`, `TBD` or `FIXME` (any case, bounded by non-alphanumeric characters). A string that is only an angle-bracket placeholder such as `<named accountable owner>` MUST NOT appear in an issued Profile (warning on a draft). |
| ARP-003 | An issued Profile MUST carry `vocab_versions` naming the version of every vocabulary in §2. (Warning) A version different from the checker's own is reported. |
| ARP-010 | `assurance.headline` MUST equal the minimum of the four axis levels. |
| ARP-011 | A field MUST NOT be `measured` on an axis at Level 1. A `measured` field MUST be the `field_id` of at least one result. (Warning) A field with a judged result SHOULD be `measured`. |
| ARP-012 | An axis at Level 2 or 3 MUST carry at least one judged result (`held` or `contradicted`) and a `coverage` entry that matches the results. A Profile that judged nothing is a Level 1 with a signature block. |
| ARP-013 | Every result MUST test a claim field, on an axis at Level 2 or 3, and every evidence reference MUST resolve to the manifest. A judged result MUST cite evidence. |
| ARP-014 | For each axis: Level 3 if and only if `assurance.assessors.<axis>.role` is `independent_assessor`; that assessor MUST be named (`organisation`) and MUST cite its report (`report`), an evidence item of class `assessor_report`. Once issued, each assessor organisation behind a Level 3 axis MUST have signed with role `assessor` and that `organisation`, using a key different from the owner's. A signature with role `assessor` MUST name the assessor of a Level 3 axis. `issuance.issuer.independent` records whether the issuing organisation is independent of the deployment; it does not make any axis Level 3. |
| ARP-015 | `assurance.disclosures` MUST contain exactly the disclosures the assurance vector requires: `level1_untested` if any axis is at Level 1, `self_tested` if any is at Level 2, `independently_verified` if any is at Level 3, `not_comparable` always, and `benchmark_not_production` if the comparability flag is set. |
| ARP-016 | Every result MUST record how it was decided: method (`deterministic`, `model_judged`, `expert_review`, `hybrid`), tool and version, the model judge where one was used (`judge_model` with provider, model and pinned version), evidence basis and review status. A judged result on an `actions.*` or `controls.*` field MUST NOT be decided by a model judge alone and MUST rest on control-decision or state evidence. A model judge may propose findings; it does not substantiate an enforceable boundary. |
| ARP-017 | If any axis is at Level 2 or 3, `assurance.reproduction` MUST point, through the evidence manifest, to the executable test cases, the initial state, the deployment and policy configuration, the evaluator configuration and rerun instructions. Hashes give integrity; this gives reproducibility. |
| ARP-018 | If any axis is at Level 2 or 3, `assurance.test_environment` MUST be stated and `assurance.fidelity` MUST say how closely the test setting matched the deployment (tools, data, policies, permissions, response times, failure conditions, population) and list known differences. |
| ARP-019 | If any axis is at Level 2 or 3, `evidence_manifest` MUST be present: `content_hash` MUST equal the canonical hash (§7) of the `evidence` array, and its signature MUST verify. This is the signed source manifest of preprint Table 4. |
| ARP-020 | `benchmark` MUST be absent or null unless the comparability flag is set. A set flag MUST name the environment version, the hidden-set version and a fidelity statement, and `benchmark` MUST name an independent assessor (non-blank `organisation` and `accreditation_ref`, `independent: true`) and at least one result. The flag MUST NOT be set on a Profile whose production axes are all at Level 1: the flag is set by an independent assessor who runs the agent (preprint Table 4), and a Level 1 Profile executes nothing. |
| ARP-030 | An action class MUST NOT be both permitted and prohibited. |
| ARP-031 | Every class A1–A12 MUST be stated as permitted, prohibited or out of scope on an issued Profile (warning on a draft). Out of scope means the class lies outside the assessed claim and is not asserted either way; the preprint's prohibited set A− is `claim.actions.prohibited`. |
| ARP-032 | An action class MUST NOT be both out of scope and permitted, or both out of scope and prohibited. |
| ARP-040 | Tier U MUST be carried as an open finding of kind `unprofiled`, with no results, headline Level 1, tier basis `asserted` and no `approval_quality`, and the statement MUST say that no reliability claim is made (contain the words "no reliability claim"). An issued U Profile MUST record a risk acceptance in `status.risk_acceptances`, or give its `unprofiled` finding the `response` `remediation` or `suspension`. |
| ARP-041 | Tier T2 MUST carry `approval_quality`, which MUST NOT be `reflexive`. A `substantiated` T2 needs a `substantive` assessment on configuration-derived or measured evidence, with `resource_displayed: true` and `sample_size` above 0, and MUST NOT rest on autonomy evidence that has a `simulated_evidence` or `suspected_simulated_evidence` conflict in any state. If the autonomy axis is at Level 2 or 3, T2 MUST be substantiated. `tier_basis: substantiated` MUST NOT be used with any tier other than T2. (Warning) A tested T2 SHOULD record `habituation_catch_rate`. |
| ARP-050 | Every claim field MUST have a provenance entry. (Warning) A provenance entry for a field that is not a claim field SHOULD have class `absent`. |
| ARP-051 | A `document_derived`, `configuration_derived` or `measured` field MUST cite evidence, and every citation MUST resolve to the manifest. |
| ARP-052 | A control MUST come from the catalogue, or be an extension whose id starts `<layer>.x_`, and sit under its own layer. |
| ARP-053 | `odd.use_case_id`, when present, MUST be in `vocab/use-cases.json` or an extension `ODD.x_<name>`; for a catalogued use case, `odd.business_line` MUST be that use case's business line. (Warning) An issued Profile SHOULD carry `use_case_id`. |
| ARP-054 | On an issued Profile, `odd.jurisdictions`, `odd.population`, `odd.data` and `odd.cost_of_failure` MUST each be populated, or carry a provenance entry of class `absent`. |
| ARP-055 | Every evidence item MUST have a unique `id`. (Warning) Two items with the same `path` but different `content_hash`, or the same `content_hash` under different ids, SHOULD be explained or merged. |
| ARP-060 | A failed floor MUST be referenced by an open finding of kind `floor_failure`. Every `floors[].finding_refs` entry MUST name an open finding, and every `open_findings[].floor_ref` MUST name a floor. Floors are never averaged away. |
| ARP-061 | An issued Profile MUST NOT contain a floor with status `failed`. |
| ARP-062 | If any axis is at Level 2 or 3, the Profile MUST state at least one floor. A floor whose `axis` is at Level 2 or 3 MUST NOT be `untested`; a floor with no `axis` applies to the whole Profile and MUST NOT be `untested` when the headline is Level 2 or 3. |
| ARP-070 | A `contradicted` result MUST be an open finding. A `held_by_agent_only` or `not_established` result MUST be an accepted gap or an open finding. Every accepted gap MUST match a result. |
| ARP-071 | (Warning) A field whose results disagree is reported by its most severe disposition (§4, "Several results on one field"); every result is kept and listed. |
| ARP-080 | An issued Profile MUST have `issued_at`, `valid_from`, `valid_until` and `evidence_as_of`. `valid_until` MUST follow `valid_from`; `valid_from` MUST NOT precede the issue date; `evidence_as_of` MUST NOT follow the issue date; no date may be before 2000-01-01. (Warning) Checked against a stated date, a Profile that has expired or is not yet valid is reported. |
| ARP-081 | An issued Profile MUST name `subject.deployment_version` and every model it calls (`subject.models`: provider, model, pinned version), so that changes can invalidate it. |
| ARP-082 | (Warning) An issued Profile SHOULD list, among the changes that void it, the default triggers of preprint §5.3: `model_change`, `harness_change`, `odd_expansion`, `action_class_added`, `critical_control_removed` and `access_or_owner_change`, and `topology_change` where it lists inter-agent controls. |
| ARP-083 | A Profile anchored to a platform baseline (`subject.platform_baseline`) MUST list the trigger `platform_baseline_void` among the changes that void it. |
| ARP-090 | An issued Profile MUST name its issuer and carry the accountable owner's signature, made with the name in `issuance.owner.name`. Where the issuer's name differs from the owner's, the issuer MUST also sign, with role `issuer` and the issuer's name. (Warning) A draft that carries signatures is reported: any edit invalidates them. |
| ARP-091 | Every signature MUST cover this Profile's canonical hash, MUST be valid for its signature statement (§7), and MUST NOT repeat the value of another signature, or the role together with the same signer name or the same public key. Signer names are compared after Unicode NFC normalisation, with runs of whitespace collapsed to one space and leading and trailing whitespace removed; the same comparison applies to the names in ARP-090. A checker that cannot check signatures MUST NOT report an issued Profile as conformant; it reports the result as indeterminate (warning on a draft). |
| ARP-092 | (Warning) A signature made with a published DEMO-ONLY key proves nothing about anyone. |
| ARP-100 | An open conflict on an issued Profile MUST be carried as an open finding on that field. |

## 6. Disclosures

A conforming renderer displays every disclosure in `assurance.disclosures` with this wording,
above the claim. (Rendering is a tool requirement and is not tested by the suite.)

| Code | Standard wording |
|---|---|
| `level1_untested` | Parts of this Profile are Level 1: asserted by the institution and not tested. |
| `self_tested` | Parts of this Profile were tested by the institution itself, without independence. |
| `independently_verified` | Parts of this Profile were tested by an independent assessor. |
| `not_comparable` | Production results in this Profile are specific to this deployment's environment and are not comparable with other deployments. |
| `benchmark_not_production` | The benchmark result is comparable with other deployments under the reference conditions only. It adds no assurance about production behaviour. |

## 7. Canonical form, hash and signatures

**Canonical form.** The canonical form of a JSON value is its RFC 8785 (JSON Canonicalization
Scheme) serialisation: object members sorted by their names' UTF-16 code units, no
insignificant whitespace, strings escaped as ECMAScript `JSON.stringify` does, and numbers
written as ECMAScript writes them (`212.0` is written `212`, `1e-7` is written `1e-7`). ARP-001
excludes the values JCS cannot represent exactly.

**Canonical hash.** `sha256:` followed by the lowercase hex SHA-256 of the UTF-8 canonical form of
the Profile without its `signatures` member.

**Signatures.** Each signature is Ed25519 over the UTF-8 canonical form of its *signature
statement*, the object

```
{"context": "arp-signature/1.0-rc2", "alg": "ed25519", "role": <role>, "name": <name>,
 "organisation": <organisation or null>, "public_key": <public_key>, "signed_hash": <canonical hash>}
```

so the role, name, organisation and key are covered as well as the Profile. Any edit to the
Profile, or to a signature's role, name or organisation, invalidates that signature.
`public_key` is the base64 of the raw 32-byte Ed25519 public key; `value` is the base64 of the
64-byte signature.

The `evidence_manifest` signature (ARP-019) is Ed25519 over the UTF-8 canonical form of
`{"context": "arp-evidence-manifest/1.0-rc2", "content_hash": <hash>, "signer": <signer>, "public_key": <public_key>}`.

A valid signature proves possession of a key. It does **not** prove that the key belongs to the
named owner or to a qualified assessor. Binding keys to people and to assessor qualifications
needs an identity and qualification policy, which this candidate does not define. No
certification mark should rely on signatures until it exists. The DEMO-ONLY keys shipped with
the kit are public; anything signed with them proves nothing (ARP-092).

## 8. Interoperability

Normative requirements name no product. Mappings to specific tools and standards are
non-normative and live in `interop/`. Two cautions apply to any mapping (explanatory; the Builder
and Validator apply them):

* A configuration export counts as `configuration_derived` only with evidence that it is the
  configuration actually deployed (for example a hash matching the running system).
* A control-point event such as a `deny` supports a `held` disposition only when the resulting
  state corroborates that the action did not execute.

## 9. Deferred

* The evidence event schema that agent runtimes emit for Level 2, aligned with OpenTelemetry
  GenAI conventions and SAFR.
* Tool conformance for Builders and Validators.
* Platform Baseline Profiles (out of scope for this candidate, §2): the autonomy ceiling, the six
  platform properties, which controls an anchored Profile may inherit and what
  deployment-specific evidence it still needs.
* Composite (multi-agent) Profiles.
* Value scales for the six autonomy modifiers (today free text with standard definitions).
* Catalogue candidates from the Builder trial: purpose limitation, consent validity, recipient
  binding (tool layer). Until adopted they are `tool.x_` extensions.
* Key identity and assessor qualification policy (§7).
* Monitoring plans and reissuance requirements beyond the validity window (preprint §5.3);
  `invalidation.monitoring` records the institution's own arrangement in free text.
