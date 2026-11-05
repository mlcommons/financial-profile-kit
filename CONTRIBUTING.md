# Contributing

Thank you for helping build the Agent Reliability Profile. This Kit is a release candidate: the
best contributions now are evidence from real use.

**Licence:** the Kit is licensed under the Apache License 2.0 ([LICENSE](LICENSE)). Contributions are
accepted under the same licence (inbound = outbound, as in section 5 of the License), with no extra
terms. Whether MLCommons also requires a contributor licence agreement (CLA) is for MLCommons to
confirm; until it does, please send contributions through the Working Group
(participation@mlcommons.org). New source files should start with `SPDX-License-Identifier: Apache-2.0`.

## Most wanted

1. **Pilot findings.** Hours to compile a Level 1 Profile; what was hard; what Level 2 testing found
   that you did not expect; fields that two teams described differently.
2. **Evidence parsers** that turn a platform's exports (tool registries, IAM, approval logs) into
   evidence-manifest entries and citations.
3. **Runtime adapters** for the Profile Validator (Release 2), against the evidence event schema
   when it is published.
4. **Domain packs:** floors, scenarios and out-of-scope statements for a use case (ODD.1–ODD.52).
5. **Independent implementations** of the checker or generators that pass the conformance vectors:
   `python3 conformance/run_suite.py --impl "your-tool check {file}"`.

## Where to propose what

| Change | Where |
|---|---|
| A tier, modifier, business line, use case, action class or control | The [taxonomy repository](https://github.com/mlcommons/agent-reliability-profile-taxonomy), which owns the shared vocabulary |
| A rule, schema, conformance vector or specification-owned vocabulary | A *Specification change* issue here; needs Working Group approval |
| A tool fix or improvement | A pull request here; Kit maintainers review it |
| A security problem | Privately, per [SECURITY.md](SECURITY.md) |

Details: [governance/review-process.md](governance/review-process.md).

## How changes are made

- The preprint ([arXiv:2610.04123](https://arxiv.org/abs/2610.04123)) defines the concepts; `spec/SPEC.md`
  makes them testable. A change to a rule changes `spec/`, the schema, the vectors and the reference
  checker together, with a CHANGELOG entry (`spec/SPEC.md` §1).
- Every change keeps all tests passing (README, *Tests*) and regenerates derived files
  (`templates/build_workbooks.py`, the Viewer and dashboard demo build scripts).
- Example data must be fictional and labelled "(fictional)". Never commit real evidence, real
  institution names, personal data or real keys.
- Write plainly. Rules use MUST, MUST NOT and SHOULD as in RFC 2119.
