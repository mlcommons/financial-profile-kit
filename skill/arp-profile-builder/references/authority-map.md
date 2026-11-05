# Authority map: what each evidence class may establish

Adapted from the evidence guide written for the Working Group's hackathon Builder (September 2026). A citation from a class that may not establish
a field does not support that field; record the field as `absent` or as a conflict instead.

| Evidence class (`artifact_class`) | May establish | May not establish | Provenance class |
|---|---|---|---|
| `product_documentation` (PRD, policy memo) | Intended tier, intended use and ODD, stated prohibited actions, claimed controls | Anything as-built | `document_derived` |
| `technical_design` | Intended architecture, tool surface, where controls should live | What is deployed | `document_derived` |
| `operational_documentation` (runbook, procedure) | Escalation paths, operating procedures | Whether they are followed | `document_derived` |
| `configuration_export` (policy, tool registry, settings) | As-built permitted and prohibited action surface; rules the control point applies; caps | Whether rules are effective under pressure (Level 2) | `configuration_derived` |
| `identity_entitlements` (IAM, scopes) | As-built scopes per service account; often the strongest action-class evidence | Intent | `configuration_derived` |
| `approval_workflow` config | That an approval gate exists, and where | That approvals are real | `configuration_derived` |
| `approval_workflow` sample records | Approval quality: latency, edit and rejection rates, resource shown. Decisive for T2 vs T3 | Completeness beyond the sample | `configuration_derived` |
| `run_log` | That claimed logging exists in the claimed form; corroboration | Completeness of anything | `configuration_derived` |
| `attestation_governance` | Who stands behind the deployment; whether paperwork matches the deployed version | Technical behaviour | `owner_attested` or `document_derived` |
| `console_rendering` (PDF of an admin screen) | What its machine-readable sibling establishes (cite the sibling). Content found only in the rendering is `document_derived` and noted as a discrepancy | — | as sibling, or `document_derived` |

When two artifacts of different authority disagree, that is a finding with both citations,
never noise to smooth over. Check for markers of simulated or sample data in approval
records and logs; if present, record a `simulated_evidence` conflict.
