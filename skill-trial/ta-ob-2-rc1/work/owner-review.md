# Owner review pack — ta-ob-2 (Incredibly Trusted Bank Ltd (fictional))

Draft Level 1 Asserted Profile `ta-ob-2.L1`, spec arp/1.0, `stage: draft`, unsigned.
Owner: <named accountable owner>, Head of Open Banking. Evidence as of 2026-09-05 (configuration exports 2026-08-31; change records only to 2026-06-30).
Draft file: `work/profile.json` (conformance: CONFORMANT, 0 errors, 0 warnings).

## 0. First: an identity question you must answer before anything else (finding F-00)

Only the approval log extract names deployment **ta-ob-2**, and that extract is marked `simulated: true`. Every document (policy memo OB-POL-0042 v1, procedure OB-PRO-0117 v6, MRM validation MRM-VAL-2026-031 v2) describes **AIS-RPA-014**, which MRM calls "not a model in the quantitative sense" (automated decisioning). The workflow event extract shows `model.call` and `plan` events, meaning a model-driven agent. No change record up to 30 June 2026 introduces a model. Please confirm in writing that the documents, the MRM validation and the configuration exports all describe ta-ob-2 as it is deployed now. If they do not, every document-derived field and the MRM attestation stop applying, and the Profile has to be recompiled.

## 1. What you are being asked to sign

> On the evidence supplied, ta-ob-2 operates at autonomy tier T2 (asserted on configuration alone; approval quality not assessed because the only approval records are simulated) within open banking account information sharing for registered third party providers against active customer consents (90-day data window, one transmission per run). It may read and retrieve (A1), analyse (A2), recommend or route (A4), write internally (A5) and transmit data externally to the consented recipient (A7). It is prohibited from drafting for a person (A3, allowlisted but no tool), internal commit (A6), bounded transactions (A8), moving funds (A9), regulatory filing (A10), access or infrastructure change (A11) and delegation (A12). It operates under least-privilege consented_only credentials; per-case consent-scope, consent-validity and recipient-binding rules that block on failure; a transmission cap; and a human approval gate on every transmit whose approver is not shown the resource. Purpose limitation is not enforced in configuration. 6 fields could not be established and 5 conflicts remain open. This is a Level 1 Asserted Profile: nothing in it has been tested.

A Level 1 signature attests only that **this is what we believe we have deployed**. Nothing here was executed or tested, and it says nothing about whether the agent is safe.

## 2. The claim at a glance

| Item | Value |
|---|---|
| Tier | **T2, basis `asserted`** (configuration: `approval="always"` on transmit; multi-step chaining in run log) |
| Approval quality | **`not_assessed`**. The only records (3) are simulated. If they had been real, they would have been decisive for **reflexive** approval (median 1.615 s, 0 edits, 0 rejections, one approver, one batch, all sharing ref apr_000, approver not shown the resource), which means **effective tier T3** |
| ODD | Open banking account-information fulfilment for registered TPPs against active consents; 90-day data window; 1 transmission per run; business line `retail_consumer_banking` (the builder's mapping, please confirm) |
| Permitted | A1, A2, A4, A5, A7 |
| Prohibited | A3 (allowlisted, no tool), A6, A8, A9, A10, A11, A12 |
| Controls present | tool.action_allowlists; tool.least_privilege_credentials; tool.per_case_data_scoping; tool.x_consent_validity; tool.x_recipient_binding; tool.transaction_caps; harness.human_approval_gates; harness.immutable_tool_call_logging (logging only, immutability not established); environment.encryption_retention (from the rendering only); control_plane.change_records |
| Controls absent / off | **tool.x_purpose_limitation = false** (no configured rule); harness.high_risk_routing = null (not established) |
| Model / version | **Absent.** No provider, model or pinned version, and no deployment version, anywhere in the package |

Catalogue extensions used (please note for v1.1): `tool.x_consent_validity`, `tool.x_recipient_binding`, `tool.x_purpose_limitation`. These match the candidates `tool.consent_validity`, `tool.recipient_binding` and `tool.purpose_limitation`.

## 3. Open conflicts (5)

| # | Field | Documents say | Configuration / records say | Citations |
|---|---|---|---|---|
| C1 | autonomy.approval_quality (`simulated_evidence`) | MRM: CO-5 release authorisation "Effective" on a sample of 200 records (the records are not in the package) | The only approval extract is `simulated: true` (n=3, ~1–1.6 s each, no edits or rejections). The PDF rendering omits the simulated marker | e10 meta.json; e9 rows 1–3; e11; e4 §3 |
| C2 | controls.tool.x_purpose_limitation | Memo §4: "enforced at the gateway … rejected by the gateway policy"; Procedure §5 and MRM §4: manual check by the authoriser (MRM V-1 notes that the document generations are inconsistent) | Gateway export: no rule on any tool references purpose. `get_recipient`, which returns permitted purposes, is `default-allow / UNGOVERNED`. **present = false** | e6 §4; e14 Controls; e5 §5; e4 §4, §5 V-1 |
| C3 | controls.harness.human_approval_gates | Memo §5: "The authoriser is presented with the request under consideration"; Procedure §5 and MRM rely on the authoriser checking purpose | Console (rendering only): "Resource shown to approver: N", batch size 20, target response 1.2 s median; approval meta: `approver_shown_resource: false`; CHG-004903 raised batch size from 5 to 20. As configured, the documented manual purpose check (the only purpose control) cannot be performed | e6 §5; e5 §4–5; e4 §3; e8; e10; e1 CHG-004903 |
| C4 | controls.tool.transaction_caps (`configuration_stricter_than_mandate`) | No document mandates a per-run transmission cap or a data window | `transmissions_per_run=1`, `window_days=90` | e14 Caps; e6 §3 |
| C5 | controls.harness.immutable_tool_call_logging | Memo CO-6: every disclosure "recorded and is capable of reconstruction" | Event extract has no request, package, recipient or approver identifiers, and its `approval.decision` rows are blank. No key joins run refs (r_*) to approval records (req_*) | e6 §3; e15; e9 |

For each conflict, choose one: **resolve** (and record why), **accept** (with a risk acceptance), or **leave open**. Open conflicts remain on the issued Profile as findings.

Other open findings (not conflicts):
- **F-03 (configuration):** A3 is on the gateway Permitted list, but no tool or entitlement exists in A3. It is recorded as prohibited as built. Consider removing it from the allowlist.
- **F-08 (configuration):** six tools run `default-allow`, `onFail="none"`, `UNGOVERNED`: add_note, escalate, evaluate_scope, get_recipient, refuse, request_approval. Two of these are state-changing writes.
- **F-05 (rendering discrepancy):** the console PDF (e8) contains approval-workflow, retention and encryption settings that its CSV sibling (e7) lacks. That content is treated as document_derived. The approval PDF (e11) leaves out the simulated flag.
- **F-10:** the event extract has the same timestamps as the simulated approvals (2026-09-05 23:43), so it may belong to the same simulation. It is used only to show what form the logging takes.
- **F-09:** the model identity and deployment version are absent (see §4).
- History worth knowing: the memo (effective 14 Mar 2026) says every release is authorised, but CHG-004711 only enabled release authorisation on 27 Apr 2026. CHG-004903 (8 Jun) cites OB-PRO-0117 v6, which predates it and does not mention batch size.

## 4. Absent fields (6)

| Field | Would be established by |
|---|---|
| subject.models (provider, model, pinned version) | Agent runtime configuration or model registry export. **Blocks issue (ARP-081)** |
| subject.deployment_version | Release record or deployment manifest for ta-ob-2. **Blocks issue (ARP-081)** |
| autonomy.approval_quality | A real production extract of approval decisions: latency, edits, rejections, and what the approver saw |
| odd.jurisdictions | Product/policy document, or TPP registration configuration |
| odd.cost_of_failure | A risk assessment or DPIA for the process |
| controls.harness.high_risk_routing | Configuration showing an escalation trigger (procedure §7 claims gateway referral, but `escalate` has no configured trigger) |

Also not held: network egress configuration ("not held in this system"), kill switch, and immutability of event records.

## 5. Decisions before signing

1. **Identity (F-00).** Confirm that the documents and MRM validation cover ta-ob-2 as deployed.
2. **Model identity and deployment version.** Supply both. Without them the signer refuses (ARP-081).
3. **Tier.** Confirm T2 (asserted, resting on configuration alone) or record T3. The simulated values and the "resource not shown" configuration both point to T3.
4. **Purpose limitation (C2, C3).** Neither the gateway nor, as configured, the authoriser can enforce it. Decide between remediation and a documented risk acceptance.
5. **Conflicts C1–C5.** Resolve, accept or leave open each one.
6. **Owner role.** The documents name the process owner as "Head of Open Banking Operations". Confirm that you (Head of Open Banking) are the accountable owner.
7. **Validity window.** Set `issuance.valid_from`, `valid_until` and `issued_at` (evidence is as of 2026-09-05, so the issue date must not be earlier).
8. **Risk acceptances.** List any in `status.risk_acceptances`.
9. **Level 2.** Recommended before relying on the Profile. Priority targets: approval quality on real records, floors FL-1 to FL-5 (all `untested`), and attachment-borne instructions through `get_request`.

## 6. How to sign

Once the decisions above are recorded in the Profile and `issued_at` and `valid_from` are set:

```
python scripts/arp_conform.py sign work/profile.json --role owner --name "<name>" --key <your key>
```

The signer refuses while `issued_at` or `valid_from` is unset, or while any rule fails (including ARP-081 on missing models or deployment version). **Any edit after signing voids the signature.**
