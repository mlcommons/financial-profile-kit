# Glossary

Terms marked † are from the preprint's glossary (*Agent Reliability Profiles in Financial Services*,
Appendix D, [arXiv:2610.04123](https://arxiv.org/abs/2610.04123)); the others are this Kit's.

## The Profile

| Term | Meaning |
|---|---|
| **Agent Reliability Profile** † | The single record for one deployed agent: the four axis values, the floors, the out-of-scope and validity statements, the provenance map, and pointers to the underlying evidence. Each agent has its own Profile. |
| **Bounded claim** † | The scoped, falsifiable assertion made by fixing the four axes: reliable at this autonomy tier, in this operational design domain, for these action classes, under this control envelope, and nothing else. |
| **Autonomy tier** † | How much the agent decides and acts without a person, and who provides the fallback when it cannot continue: T0 (no action) to T4 (no contemporaneous approval). |
| **Tier U (unprofiled)** | A status, not a tier: the envelope, fallback or action boundaries are unspecified, so no reliability claim is available. It is a finding that needs remediation, suspension or a documented risk acceptance. |
| **Tier basis** | Whether the tier is only *asserted* or *substantiated* by real approval records. |
| **Approval quality** | Evidence from approval records that human review is substantive rather than reflexive: sample size, time to approve, edit and rejection rates, whether the approver saw the affected resource. Decides T2 versus T3. |
| **Autonomy modifiers** | Six properties stated next to the tier: data authority, reversibility profile, customer and market impact, stack composability, integrated-stack accountability, population scope. |
| **Operational design domain (ODD)** † | The defined operating context (use case, data, tool surface, customer population, jurisdiction, cost of failure) that specifies the test environment. The term comes from automated-driving standards. |
| **ODD.1–ODD.52, ODD.x_…** | The 52 catalogued use cases (`spec/vocab/use-cases.json`); `ODD.x_<name>` is a use case not in the catalogue. |
| **Boundary detection** † | Whether the agent recognises that it has left its tested domain and stops; distinct from following an escalation rule it was given. |
| **Action class** † | The type and reversibility of actions the agent may take, A1 (read) to A12 (delegate or spawn). Recorded as a permitted set and a prohibited set. |
| **Control envelope** † | The containment around the agent (approval gates, least-privilege access, rollback, logging, tested safe state) that makes a tier acceptable in a domain. The Kit's catalogue has 55 controls in six layers. |
| **Floor** † | A pass-or-fail condition that cannot be offset by good results elsewhere. |
| **Provenance map** † | Field by field, where each entry came from: *measured*, *configuration_derived*, *document_derived*, *owner_attested* or *absent* (strongest to weakest). |
| **Invalidation list** † | Which changes void a Profile, which need partial retesting, and which are cosmetic. |
| **Out-of-scope statement** | What the claim excludes: domains, actions, controls, users. Usually longer than the claim. |
| **Conflict** | Two sources that disagree about a field (for example a policy and a configuration). Recorded with both citations; only the owner resolves or accepts it. |
| **Open finding** | Something on the Profile that needs attention: an open conflict, a failed floor, a contradicted claim, tier U. |
| **Profile Package** † | The Profile plus the signed inputs, evidence and trace it was compiled from. The Profile is the summary; the Package is its backing, and stays with the institution. |
| **Evidence manifest** | The list of evidence files with their SHA-256 hashes (`manifest.py`). |

## Assurance

| Term | Meaning |
|---|---|
| **Asserted Profile (Level 1)** † | Self-reported: compiled from the institution's own documents and settings; nothing executed; signed by a named owner. |
| **Validated Profile (Level 2)** † | Self-reported and self-tested: the Profile Validator run in-house, with reproducible, hashed, signed inputs. |
| **Verified Profile (Level 3)** † | Self-reported and independently tested: the same Validator operated and signed by a qualified independent assessor. |
| **Headline level** | The lowest of the four axis levels. Strong evidence on one axis cannot lift a weaker one. |
| **Assurance vector** | The four axis levels together (autonomy, ODD, actions, controls). |
| **Benchmarked Profile / comparability flag** † | A separate field, not a level: the Profile Benchmarker ran the agent in a shared environment with a hidden, rotating scenario set, so results are comparable across institutions under reference conditions. It adds no assurance about production behaviour. |
| **Disclosures** | Standard sentences every rendering of a Profile must show, such as "not tested" or "not comparable with other deployments" (`spec/SPEC.md` §6). |
| **Disposition** | The outcome of a test on a claim: *held*, *contradicted*, *held_by_agent_only* (the agent refused but the control was never exercised) or *not_established*. |
| **Accepted gap** | An untested or agent-only result that the owner accepts, with a reason. |
| **Conformant** | The Profile follows the schema and rules, is honestly labelled and, once issued, signed. It does not mean the claims are true or the agent is safe ([CONFORMANCE.md](CONFORMANCE.md)). |
| **Issue / issued** | The accountable owner signs a draft, which makes it an issued Profile. Any later edit invalidates the signature. |

## Platforms

| Term | Meaning |
|---|---|
| **Platform Baseline Profile** † | The Profile carried by an agent-building platform itself: a claim about the ceilings and invariants it enforces for every session, not about any hosted agent's work. |
| **Platform anchor** † | The record, on a hosted agent's Profile, of the Platform Baseline Profile it relies on. The agent's Profile is void if the platform's is. |
| **Autonomy ceiling** † | The highest tier a platform can grant to any agent it hosts, enforced in software and recorded in place of a tier. |
| **Resolved manifest** † | The per-session record of the skills, tools, data and permissions actually granted to a platform-hosted agent. |

## Tools and formats in this Kit

| Term | Meaning |
|---|---|
| **Profile Builder** | Compiles a Level 1 Profile from evidence. Here: the agent skill in `skill/arp-profile-builder/`. |
| **Profile Validator** | Runs scenarios against a deployed agent for Level 2 (or Level 3 when an independent assessor runs it). Planned for Release 2; not in this Kit. |
| **Profile Benchmarker** | Runs agents in the shared reference environment for a Benchmarked Profile. Planned; not in this Kit. |
| **Reference checker** | `conformance/arp_conform.py`: checks a Profile against every rule, signs and hashes. Where it and another tool disagree, the specification decides. |
| **Conformance vectors** | Example Profiles, valid and invalid, with the verdict each must get (`conformance/vectors/`). |
| **Profile Viewer** | A single HTML file that reads, explains and checks a Profile in the browser, offline. |
| **Profile Lite** | One row per agent deployment, for inventories and supervisory data requests (`spec/LITE.md`). As reported; not checked against evidence. |
| **Inventory snapshot** | A firm's signed set of Profile Lite records at one date, chained to the previous snapshot (`spec/FEED.md`). |
| **Supervisory dashboard demo** | A single HTML file in which a supervisor reads firms' inventory snapshots and Profiles (Regulator Kit, preview). |
| **Profile Summary / Profile Exchange** | A derived summary for sharing with peers, and a proposed service for exchanging them. Design only: built only if it passes its decision point ("gate") in the pilot. |
| **Trusted / quarantined snapshot** | A snapshot that passes every feed check is trusted and feeds the supervisory views. One that fails any check (signature, key register, chain, commitments, agreement with its Profile) is quarantined: listed in the Feed view only, never used in totals, trends or outliers (`spec/FEED.md` §6). |
| **Divergence** | A declared, dated difference between an inventory record and its full Profile, for example while a reissued Profile is prepared (INV-023, `spec/LITE.md`). |
| **Disclosure review** | The review a named person makes before a Profile, snapshot or summary leaves the team that owns it ([DISCLOSURE.md](DISCLOSURE.md)). |
| **DEMO-ONLY key** | A public key pair shipped for the fictional examples; a signature made with it proves nothing. |

## Abbreviations

| | |
|---|---|
| **FRN** | Firm reference number (UK FCA register). The sample feed no longer uses this style. |
| **IAM** | Identity and access management. |
| **JCS** | JSON Canonicalization Scheme (RFC 8785), used to hash Profiles. |
| **SAFR** | The Monetary Authority of Singapore's reference work on runtime controls for AI agents, cited in the preprint. |
| **TPP** | Third-party provider (open banking). |
