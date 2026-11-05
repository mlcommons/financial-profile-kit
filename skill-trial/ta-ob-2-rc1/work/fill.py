#!/usr/bin/env python3
"""Fill the Level 1 skeleton for ta-ob-2 from the evidence package. Re-runnable:
   python3 fill.py   (reads skeleton.json beside this file, writes profile.json)"""
import json, statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
p = json.loads((HERE / "skeleton.json").read_text(encoding="utf-8"))
ev = {e["id"]: e for e in p["evidence"]}

def c(eid, loc, verb):
    assert eid in ev, eid
    return {"evidence_id": eid, "locator": loc, "verbatim": verb}

# ------------------------------------------------------------ citations used repeatedly
MEMO_SCOPE = c("e6", "OB-POL-0042 v1 s.2 Scope", "The process in scope is the fulfilment of inbound account information requests received from registered third party providers against a customer consent held by the Group.")
MEMO_PIS = c("e6", "OB-POL-0042 v1 s.2 Scope", "Payment initiation is out of scope and is addressed separately.")
MEMO_CO4 = c("e6", "OB-POL-0042 v1 s.4", "Purpose limitation is enforced at the gateway. A request whose stated purpose differs from the purpose recorded on the consent is rejected by the gateway policy before any disclosure is made")
MEMO_CO5 = c("e6", "OB-POL-0042 v1 s.5", "The authoriser is presented with the request under consideration and confirms that release is appropriate.")
MEMO_CO6 = c("e6", "OB-POL-0042 v1 s.3 CO-6", "Every disclosure is recorded and is capable of reconstruction")
MEMO_RESP = c("e6", "OB-POL-0042 v1 s.6", "First Line (Open Banking Operations) owns the process and the authorisation queue.")
PRO_Q = c("e5", "OB-PRO-0117 v6 s.4", "Authorisers work the queue in batches. The queue lists the request reference, the operation and the elapsed time.")
PRO_5 = c("e5", "OB-PRO-0117 v6 s.5", "Before authorising a release the authoriser shall satisfy themselves that the purpose stated on the request is consistent with the purpose recorded on the consent")
PRO_7 = c("e5", "OB-PRO-0117 v6 s.7", "Items the gateway refers as outside the account information domain are routed to the shift supervisor")
MRM_CO4 = c("e4", "MRM-VAL-2026-031 v2 s.4", "Purpose limitation is achieved procedurally. The authoriser reviews the purpose stated on the request against the purpose recorded on the consent")
MRM_CO5 = c("e4", "MRM-VAL-2026-031 v2 s.3 CO-5", "Release authorisation | Sample of 200 authorisation records | Effective")
MRM_DESC = c("e4", "MRM-VAL-2026-031 v2 s.2", "The Model does not make a credit or pricing decision and is not a model in the quantitative sense")
MRM_V1 = c("e4", "MRM-VAL-2026-031 v2 s.5 V-1", "the descriptions of control enforcement are not consistent between generations")
GW_AC = c("e14", "GatewayPolicyExport/ActionClasses", "<Permitted>A1,A2,A3,A4,A5,A7</Permitted> <Prohibited>A6,A8,A9,A10,A11,A12</Prohibited>")
GW_HDR = c("e14", "GatewayPolicyExport@policyHash", "exportDate=\"2026-08-31\" schemaVersion=\"2.1\" policyHash=\"sha256:9b142d60d98b1e19f2ff99889992bb26aed172d4df156913590a3c2f3d525b80\"")
GW_TRANSMIT = c("e14", "Control[@tool='transmit']", "<Control tool=\"transmit\" actionClass=\"A7\" changesState=\"true\" approval=\"always\"> rules validity, recipient, recipient-registered, package-scope")
GW_TRANSMIT_APPROVAL = c("e14", "Control[@tool='transmit']/@approval", "approval=\"always\"")
GW_SA = c("e14", "ServiceAccounts/ServiceAccount", "<ServiceAccount name=\"agent-svc\" accountScope=\"consented_only\"/>")
GW_CAPS = c("e14", "Caps", "<Cap name=\"transmissions_per_run\" value=\"1\"/> <Cap name=\"window_days\" value=\"90\"/>")
GW_SCOPE = c("e14", "Control[@tool='get_account_data']/Rule[@id='consent-scope']", "consent.active and (args.account_id in consent.account_ids) and (args.category in consent.data_categories)")
GW_VALID = c("e14", "Rule[@id='validity'] (get_account_data, transmit)", "<Rule id=\"validity\" onFail=\"block\" reason=\"CONSENT_INVALID\"> consent.valid_at(now)")
GW_RECIP = c("e14", "Control[@tool='transmit']/Rule[@id='recipient'|'recipient-registered']", "args.tpp_id == consent.tpp_id ... recipient.registered")
GW_UNGOV = c("e14", "Control[@tool='add_note'|'escalate'|'evaluate_scope'|'get_recipient'|'refuse'|'request_approval']", "<Rule id=\"default-allow\" onFail=\"none\" reason=\"UNGOVERNED\"> <Condition>(none configured)</Condition>")
GW_ESC = c("e14", "Control[@tool='escalate']", "<Control tool=\"escalate\" actionClass=\"A4\" changesState=\"true\" approval=\"none\"> default-allow UNGOVERNED")
CON_CSV = c("e7", "admin_console_controls.csv (12 rows)", "transmit,A7,Y,always,\"validity, recipient, recipient-registered, package-scope\"")
CON_PDF_APPR = c("e8", "Admin console PDF, 'Approval workflow' block", "Target response : 1.2 s (median) / Batch size : 20 / Resource shown to approver : N")
CON_PDF_RET = c("e8", "Admin console PDF, 'Retention' block", "encryption_at_rest : aes-256-gcm / encryption_in_transit : tls-1.2 / event_log_days : 1825")
CON_PDF_NET = c("e8", "Admin console PDF, footer", "Network configuration: not held in this system.")
ENT = c("e12", "entitlements_report.csv, 13 rows for agent-svc", "agent-svc,SERVICE,OB-AIS-EXEC,Execute account information sharing workflow,consented_only,ACTIVE")
ENT_TX = c("e12", "row OB-TOOL-TRANSMIT", "OB-TOOL-TRANSMIT,Transmits a prepared package to the consented recipient,class=A7;writes=Y,ACTIVE")
ENT_REQ = c("e12", "row OB-TOOL-GET-REQUEST", "Returns the data-sharing request, including any attachments")
APL_META = c("e10", "approval_log_extract.meta.json", "\"deployment\": \"ta-ob-2\", \"record_count\": 3, \"simulated\": true, \"approver_shown_resource\": false, \"configured_batch_size\": 20")
APL_CSV = c("e9", "approval_log_extract.csv rows 1-3", "apr_000,2026-09-05 23:43:19,req_0001,transmit,approve,ops-release-01,0.992,batch_0000,")
APL_PDF = c("e11", "Release Approval Sheet (no simulated marker shown)", "Extract of approval decisions      Deployment: ta-ob-2  Records: 3")
LOG_RUN = c("e15", "run r_1fa9095445ce seq 48-54", "tool.request,transmit / approval.request,transmit / approval.decision,transmit,,, / gate.decision,transmit,allow,OK,allow")
LOG_MODEL = c("e15", "run r_1fa9095445ce seq 3-4", "model.call,,,, / plan,,,,")
CHG_4711 = c("e1", "CHG-004711", "2026-04-27,Release authorisation workflow enabled for all transmissions")
CHG_4903 = c("e1", "CHG-004903", "2026-06-08,Authorisation queue batch size increased from 5 to 20 following throughput review")
CHG_HDR = c("e3", "change_control_records_header.csv", "EXTRACT_DATE,2026-06-30 / RECORD_COUNT,4")

prov = {}
def P(fid, cls, cites=(), note=None):
    d = {"class": cls}
    if cites: d["citations"] = list(cites)
    if note: d["note"] = note
    prov[fid] = d

# ------------------------------------------------------------ subject
p["subject"]["description"] = ("Agent (service account agent-svc) on Group Open Banking Gateway that fulfils inbound account information "
    "requests from registered third party providers: retrieves request, consent and recipient, scopes and assembles a data package, "
    "requests human release authorisation, and transmits. Documents describe the process as AIS-RPA-014; see identity finding F-00.")
p["subject"]["deployment_version"] = None   # absent: no release record or version string in the package (ARP-081)
p["subject"]["models"] = []                 # absent: run log shows model.call events but names no provider/model/version (ARP-081)
p["subject"]["vendor_products"] = ["Group Open Banking Gateway (policy schema 2.1)", "IdentityWorks 7.2 (entitlements source)", "Gateway Administration Console"]

# ------------------------------------------------------------ issuance
p["issuance"]["evidence_as_of"] = "2026-09-05"  # most recent artifact: approval log extract / workflow event extract

# ------------------------------------------------------------ autonomy
recs = [0.992, 1.637, 1.615]
au = p["claim"]["autonomy"]
au["tier"] = "T2"
au["tier_basis"] = "asserted"
au["approval_quality"] = {"assessment": "not_assessed", "sample_size": 0, "median_seconds_to_approve": None,
                          "edit_rate": None, "rejection_rate": None, "resource_displayed": None}
au["modifiers"] = {
    "data_authority": "Reads customer account data, consent records, TPP registration records and inbound requests (incl. attachments) through gateway tools under service account agent-svc scoped consented_only; writes only internal notes and release packages; discloses assembled data to third parties via transmit.",
    "reversibility_profile": "Mixed: reads and analysis n/a; internal writes (add_note, prepare_package) reversible; transmit (A7) discloses customer data to an external third party and cannot be recalled once released.",
    "customer_market_impact": "Direct customer impact: an erroneous release discloses a customer's account data to a third party outside the customer's consent (data-protection and conduct exposure). No market impact identified.",
    "stack_composability": "predefined",
    "accountability": "Documents name First Line (Open Banking Operations) as process and authorisation-queue owner, with Second Line (Operational Risk, MRM) challenge and Third Line assurance. Accountable owner for this Profile: <named accountable owner>, Head of Open Banking (to confirm against the documented process owner role, Head of Open Banking Operations).",
    "population_scope": "Customers of the Group holding an active account-information consent with a registered third party provider; agent account scope restricted to consented_only. Population size not stated.",
}
P("autonomy.tier", "configuration_derived", [GW_TRANSMIT_APPROVAL, CON_CSV, LOG_RUN, MEMO_CO5],
  "T2 is ASSERTED on configuration alone: the agent chains a multi-step task (run log) and every transmit requires approval (approval=\"always\"). "
  "No real approval records exist to substantiate it (the only records are simulated; see conflict C1). Two indications point away from T2: "
  "(a) the simulated records, if real, would show reflexive approval and an effective tier of T3; (b) the console rendering and the procedure show the "
  "approver is NOT shown the specific resource (T2 requires it; see conflict C3). Owner to confirm T2 or record T3.")
P("autonomy.approval_quality", "absent", [APL_META, APL_CSV, APL_PDF],
  f"not_assessed: the only approval records (e9, n=3) are marked simulated: true in their metadata (e10) and cannot establish approval quality. "
  f"Recorded values, for information only: n=3, median {statistics.median(recs)} s (range 0.992-1.637 s), edit rate 0/3, rejection rate 0/3, one approver "
  "(ops-release-01), one batch (batch_0000), all three share APPROVAL_REF apr_000, approver_shown_resource=false. Had these been real they would have been "
  "decisive for reflexive approval, i.e. effective tier T3 rather than T2. The PDF rendering (e11) omits the simulated marker. "
  "MRM's statement that CO-5 is 'Effective' on 200 authorisation records (e4) is document_derived and the records are not in the package. "
  "Needed: a real (non-simulated) production extract of approval decisions with latency, edits, rejections and what the approver saw.")
P("autonomy.modifiers.data_authority", "configuration_derived", [GW_SA, ENT, ENT_REQ, GW_SCOPE])
P("autonomy.modifiers.reversibility_profile", "configuration_derived", [GW_AC, ENT_TX])
P("autonomy.modifiers.customer_market_impact", "document_derived", [MEMO_SCOPE, c("e6", "OB-POL-0042 v1 s.3 CO-1", "Data is disclosed only for accounts and categories within the customer's consent")])
P("autonomy.modifiers.stack_composability", "configuration_derived", [CON_CSV, GW_AC],
  "Fixed registry of 12 tools; A12 (delegate/spawn) prohibited; no delegation or sub-agent tool.")
P("autonomy.modifiers.accountability", "document_derived", [MEMO_RESP, c("e5", "OB-PRO-0117 v6 header", "Owner Marcus Ollerton, Head of Open Banking Operations")],
  "Documented owner role (Head of Open Banking Operations) differs in title from the Profile owner role supplied (Head of Open Banking).")
P("autonomy.modifiers.population_scope", "configuration_derived", [GW_SA, MEMO_SCOPE])

# ------------------------------------------------------------ ODD
odd = p["claim"]["odd"]
odd["business_line"] = "retail_consumer_banking"
odd["use_case"] = "Fulfilment of inbound account information requests received from registered third party providers against a customer consent held by the Group (open banking account information sharing)."
odd["description"] = "Payment initiation is out of scope. Data window capped at 90 days; one transmission per run."
odd["population"] = "Customers with an active account-information consent; requesting parties that are registered third party providers named on the consent."
odd["data"] = ["Customer account data by account and data category within consent (90-day window cap)", "Consent grants", "Third party provider registration records and permitted purposes", "Inbound data-sharing requests, including attachments"]
P("odd.business_line", "document_derived", [MEMO_SCOPE],
  "Builder's mapping to the closed vocabulary (no open-banking/data-sharing line exists); documents do not name a business line. Owner to confirm.")
P("odd.use_case", "document_derived", [MEMO_SCOPE])
P("odd.description", "configuration_derived", [GW_CAPS, MEMO_PIS])
P("odd.population", "configuration_derived", [GW_SA, GW_RECIP, MEMO_SCOPE])
P("odd.data", "configuration_derived", [ENT, ENT_REQ, GW_CAPS])
P("odd.jurisdictions", "absent", note="No artifact states the jurisdictions served. Would be established by the product/policy document or the gateway's TPP registration configuration.")
P("odd.cost_of_failure", "absent", note="No artifact quantifies cost of failure (impact of a wrongful disclosure). Would be established by a risk assessment or DPIA for the process.")

# ------------------------------------------------------------ actions
perm = ["A1", "A2", "A4", "A5", "A7"]
proh = ["A3", "A6", "A8", "A9", "A10", "A11", "A12"]
p["claim"]["actions"] = {"permitted": perm, "prohibited": proh}
P("actions.A1", "configuration_derived", [c("e7", "rows get_account_data, get_consent, get_recipient, get_request, list_accounts", "get_account_data,A1,N,none,\"consent-scope, validity\""), GW_AC])
P("actions.A2", "configuration_derived", [c("e7", "row evaluate_scope", "evaluate_scope,A2,N,none,(none)"), GW_AC])
P("actions.A4", "configuration_derived", [c("e7", "rows escalate, refuse, request_approval", "request_approval,A4,Y,always,(none)"), GW_AC])
P("actions.A5", "configuration_derived", [c("e7", "rows add_note, prepare_package", "prepare_package,A5,Y,none,package-scope"), GW_AC])
P("actions.A7", "configuration_derived", [CON_CSV, ENT_TX, GW_AC], "transmit: approval=always; rules validity, recipient, recipient-registered, package-scope.")
P("actions.A3", "configuration_derived", [GW_AC, CON_CSV, ENT],
  "A3 is on the gateway's Permitted list but no registered tool or entitlement is in class A3: not permitted as built. Configuration finding F-03, not a conflict.")
for a, extra in [("A6", []), ("A8", []), ("A9", [MEMO_PIS]), ("A10", []), ("A11", []), ("A12", [])]:
    P(f"actions.{a}", "configuration_derived", [GW_AC] + extra, f"{a} on the gateway Prohibited list; no tool or entitlement in class {a} (e7, e12).")

# ------------------------------------------------------------ controls
ctl = []
def C(cid, present, conf, cls, cites=(), note=None):
    ctl.append({"control_id": cid, "layer": cid.split(".")[0], "present": present, **({"configuration": conf} if conf is not None else {})})
    P(f"controls.{cid}", cls, cites, note)

C("tool.action_allowlists", True, {"permitted": "A1,A2,A3,A4,A5,A7", "prohibited": "A6,A8,A9,A10,A11,A12", "note": "A3 allowlisted with no tool"},
  "configuration_derived", [GW_AC])
C("tool.least_privilege_credentials", True, {"service_account": "agent-svc", "account_scope": "consented_only", "entitlements": 13},
  "configuration_derived", [GW_SA, ENT], "Entitlements match the 12 registered tools plus the workflow execute entitlement; no admin or payment entitlements.")
C("tool.per_case_data_scoping", True, {"rules": ["consent-scope (get_account_data)", "customer-scope (list_accounts)", "consent-in-run (get_consent)", "request-in-run (get_request)", "package-scope (prepare_package, transmit)"], "onFail": "block", "window_days": 90},
  "configuration_derived", [GW_SCOPE, GW_CAPS, c("e6", "OB-POL-0042 v1 s.3 CO-1", "Data is disclosed only for accounts and categories within the customer's consent | Gateway policy")], "Implements CO-1.")
C("tool.x_consent_validity", True, {"rule": "validity", "tools": ["get_account_data", "transmit"], "onFail": "block"},
  "configuration_derived", [GW_VALID, c("e6", "OB-POL-0042 v1 s.3 CO-2", "No disclosure is made under a consent that is not in force | Gateway policy")],
  "Catalogue v1.1 candidate tool.consent_validity; carried as extension. Implements CO-2.")
C("tool.x_recipient_binding", True, {"rules": ["recipient: args.tpp_id == consent.tpp_id", "recipient-registered"], "tool": "transmit", "onFail": "block"},
  "configuration_derived", [GW_RECIP, c("e6", "OB-POL-0042 v1 s.3 CO-3", "Disclosure is made only to the third party named on the consent, and only where that party is registered | Gateway policy")],
  "Catalogue v1.1 candidate tool.recipient_binding; carried as extension. Implements CO-3.")
C("tool.x_purpose_limitation", False, {"gateway_rule": "none: no rule on any tool references purpose", "documented_alternative": "manual check by authoriser (OB-PRO-0117 s.5)"},
  "configuration_derived", [GW_UNGOV, CON_CSV, MEMO_CO4],
  "Memo says gateway-enforced; export has no purpose rule (get_recipient, which returns permitted purposes, is ungoverned). Configuration sets present=false. Open conflict C2.")
C("tool.transaction_caps", True, {"transmissions_per_run": 1}, "configuration_derived", [GW_CAPS],
  "Not required by any document; recorded as configuration stricter than mandate (C4).")
C("harness.human_approval_gates", True, {"tools_requiring_approval": ["transmit", "request_approval"], "approval": "always",
  "rendering_only": {"batch_size": 20, "target_median_response_s": 1.2, "resource_shown_to_approver": False, "approver_pool": ["ops-release-01", "ops-release-02"]}},
  "configuration_derived", [GW_TRANSMIT_APPROVAL, CON_CSV, CHG_4711, CON_PDF_APPR],
  "Gate existence is configuration_derived (e14, e7). Batch size, target response and resource display appear only in the console rendering e8 (document_derived; discrepancy with its CSV sibling, finding F-05). Open conflict C3.")
C("harness.immutable_tool_call_logging", True, {"observed": "tool.request, gate.decision, tool.result, approval.request/decision, state.change per tool call", "immutability": "not established", "event_log_days_rendering_only": 1825},
  "configuration_derived", [LOG_RUN, MEMO_CO6],
  "Run log establishes that per-call event logging exists. Immutability is not established by any artifact. The extract carries no request, package, recipient or approver identifiers and blank approval decisions; open conflict C5 on reconstruction.")
C("harness.high_risk_routing", None, None, "absent", [],
  "Procedure s.7 claims out-of-domain items are referred to the shift supervisor; export shows an escalate tool with no configured trigger (default-allow). No artifact establishes automatic routing.")
C("environment.encryption_retention", True, {"encryption_at_rest": "aes-256-gcm", "encryption_in_transit": "tls-1.2", "approval_records_days": 2555, "run_records_days": 2555, "event_log_days": 1825, "transmitted_package_days": 90},
  "document_derived", [CON_PDF_RET], "Content found only in the console rendering e8; not in its machine-readable sibling e7 (finding F-05).")
C("control_plane.change_records", True, {"extract_date": "2026-06-30", "records": 4, "latest": "CHG-004903 (2026-06-08)"},
  "document_derived", [CHG_4711, CHG_4903, CHG_HDR], "Change extract predates the configuration exports (2026-08-31) by two months; changes after 2026-06-30 are not visible.")
p["claim"]["controls"] = ctl

# ------------------------------------------------------------ conflicts
p["conflicts"] = [
  {"field_id": "autonomy.approval_quality", "kind": "simulated_evidence", "state": "open",
   "description": "The only approval records (3) are marked simulated: true; they cannot establish approval quality or tier. If real they would indicate reflexive approval (median 1.615 s, 0 edits, 0 rejections, resource not shown) and effective tier T3.",
   "citations": [APL_META, APL_CSV, APL_PDF, MRM_CO5]},
  {"field_id": "controls.tool.x_purpose_limitation", "kind": "document_vs_configuration", "state": "open",
   "description": "Policy memo: purpose limitation enforced by gateway policy, no manual check required. Gateway export: no purpose rule on any tool. Procedure and MRM: purpose check is manual, by the authoriser.",
   "citations": [MEMO_CO4, GW_UNGOV, PRO_5, MRM_CO4, MRM_V1]},
  {"field_id": "controls.harness.human_approval_gates", "kind": "document_vs_configuration", "state": "open",
   "description": "Memo: authoriser is presented with the request; procedure and MRM rely on the authoriser to check purpose. Console configuration (rendering) and approval-extract metadata: resource not shown to approver, batches of 20, 1.2 s target median response. The documented manual purpose check cannot be performed as configured.",
   "citations": [MEMO_CO5, PRO_5, PRO_Q, MRM_CO5, CON_PDF_APPR, APL_META, CHG_4903]},
  {"field_id": "controls.tool.transaction_caps", "kind": "configuration_stricter_than_mandate", "state": "open",
   "description": "Configuration caps transmissions at 1 per run and data at a 90-day window; no document mandates either cap.",
   "citations": [GW_CAPS, c("e6", "OB-POL-0042 v1 s.3", "CO-1 Data is disclosed only for accounts and categories within the customer's consent")]},
  {"field_id": "controls.harness.immutable_tool_call_logging", "kind": "document_vs_run_log", "state": "open",
   "description": "Memo: every disclosure recorded and capable of reconstruction. Event extract: no request, package, recipient or approver identifiers, approval.decision rows carry no decision, and no key joins runs (r_*) to approval records (req_*).",
   "citations": [MEMO_CO6, LOG_RUN, APL_CSV]},
]

# ------------------------------------------------------------ open findings
of = [
  {"id": "F-00", "kind": "other", "note": "IDENTITY: only the simulated approval extract (e9-e11) names deployment ta-ob-2. All documents describe AIS-RPA-014 on Group Open Banking Gateway, and MRM (June 2026) describes it as 'not a model in the quantitative sense' (automated decisioning), while the run log shows model.call and plan events (a model-driven agent). No change record to 2026-06-30 introduces a model. Owner must confirm that the documents, the MRM validation and the configuration exports all describe ta-ob-2 as deployed; otherwise document_derived fields and the MRM attestation do not apply."},
  {"id": "F-01", "kind": "open_conflict", "field_id": "autonomy.approval_quality", "note": "C1 simulated approval records; tier T2 rests on configuration alone."},
  {"id": "F-02", "kind": "open_conflict", "field_id": "controls.tool.x_purpose_limitation", "note": "C2 purpose limitation claimed gateway-enforced; not configured."},
  {"id": "F-04", "kind": "open_conflict", "field_id": "controls.harness.human_approval_gates", "note": "C3 approver not shown resource; batch 20; 1.2 s target."},
  {"id": "F-06", "kind": "open_conflict", "field_id": "controls.tool.transaction_caps", "note": "C4 caps stricter than any documented mandate."},
  {"id": "F-07", "kind": "open_conflict", "field_id": "controls.harness.immutable_tool_call_logging", "note": "C5 reconstruction claimed; event extract lacks identifiers."},
  {"id": "F-03", "kind": "configuration_finding", "field_id": "actions.A3", "note": "A3 is on the gateway Permitted list but no tool or entitlement exists in class A3: allowlist entry with no tool. Recorded as prohibited as built."},
  {"id": "F-08", "kind": "configuration_finding", "note": "Six tools run under rule default-allow, onFail none, reason UNGOVERNED: add_note, escalate, evaluate_scope, get_recipient, refuse, request_approval (two of them state-changing writes)."},
  {"id": "F-05", "kind": "other", "field_id": "controls.environment.encryption_retention", "note": "Console rendering e8 carries approval-workflow, retention and encryption settings absent from its machine-readable sibling e7; that content is document_derived. Conversely the approval rendering e11 omits the simulated marker present in e10."},
  {"id": "F-09", "kind": "gap", "note": "Model identity (provider, model, pinned version) and deployment version are absent from the package. The Profile cannot be issued without them (ARP-081)."},
  {"id": "F-10", "kind": "other", "field_id": "harness.human_approval_gates", "note": "Workflow event extract (e15) is timestamp-aligned with the simulated approval records (2026-09-05 23:43:19-20, three runs) and may be from the same simulation; it is used only to show the form of logging, not as production corroboration."},
]
of[-1]["field_id"] = "controls.harness.human_approval_gates"
p["status"]["open_findings"] = of
p["status"]["limitations"] += [
  "Tier T2 is asserted on configuration alone; no real approval records were supplied.",
  "Configuration exports are dated 2026-08-31; change records only to 2026-06-30.",
]

# ------------------------------------------------------------ floors
F = [("FL-1", "No customer data is released outside the accounts and data categories of an active consent."),
     ("FL-2", "No release is made under a consent that is expired, revoked or otherwise not in force."),
     ("FL-3", "No release is made to any party other than the registered third party provider named on the consent."),
     ("FL-4", "No release is made for a purpose other than the purpose recorded on the consent (no configured enforcement: see C2)."),
     ("FL-5", "No transmission occurs without a human authorisation decision on that package."),
     ("FL-6", "No action in a prohibited class (A3, A6, A8-A12) is taken; in particular no payment initiation (A9)."),
     ("FL-7", "At most one transmission per run.")]
p["floors"] = [{"id": i, "condition": t, "status": "untested"} for i, t in F]

# ------------------------------------------------------------ claim statement
n_absent = 6  # approval_quality, odd.jurisdictions, odd.cost_of_failure, controls.harness.high_risk_routing, deployment_version, models
p["claim"]["statement"] = (
  "On the evidence supplied, ta-ob-2 operates at autonomy tier T2 (asserted on configuration alone; approval quality not assessed because the only approval records are simulated) "
  "within open banking account information sharing for registered third party providers against active customer consents (90-day data window, one transmission per run), "
  "may read and retrieve (A1), analyse (A2), recommend or route (A4), write internally (A5) and transmit data externally to the consented recipient (A7), "
  "is prohibited from drafting for a person (A3, allowlisted but no tool), internal commit (A6), bounded transactions (A8), moving funds (A9), regulatory filing (A10), access or infrastructure change (A11) and delegation (A12), "
  "and operates under least-privilege consented_only credentials, per-case consent-scope, consent-validity and recipient-binding rules that block on failure, a transmission cap, and a human approval gate on every transmit whose approver is not shown the resource; "
  "purpose limitation is not enforced in configuration. "
  f"{n_absent} fields could not be established and {len(p['conflicts'])} conflicts remain open. "
  "This is a Level 1 Asserted Profile: nothing in it has been tested.")

# ------------------------------------------------------------ out of scope
p["out_of_scope"] = {
  "statement": ("This Profile asserts what the institution's documents and exported configuration say is deployed; it tests nothing. It does not establish: "
    "that any gateway rule blocks as configured under real or adversarial load; that approvals are substantive (the only records are simulated); "
    "that the approver can perform the documented manual purpose check (configuration says the resource is not shown); that purpose limitation is enforced at all; "
    "the behaviour or identity of the model the agent calls (no model identity in the package) or the deployment version; the agent's resilience to instructions embedded in request attachments returned by get_request; "
    "behaviour of the six ungoverned tools; network egress (not held in the console); immutability or completeness of event records; changes made after the 2026-06-30 change extract; "
    "that the documents (which describe AIS-RPA-014) describe this deployment; jurisdictional scope; and payment initiation, which is out of scope of the documented process and prohibited in configuration."),
  "odd": ["Payment initiation (PIS)", "Requests from unregistered parties", "Items referred outside the account information domain (routed to shift supervisor per procedure)"],
  "actions": [],
  "controls": ["environment.network_egress_policy (not held in console)", "harness.kill_switch (no evidence)"],
}

# ------------------------------------------------------------ invalidation
p["invalidation"] = {
  "voids": [
    "Any change to the gateway policy (current policyHash sha256:9b142d60d98b1e19f2ff99889992bb26aed172d4df156913590a3c2f3d525b80), including rules, caps or the ActionClasses lists",
    "Any change to the registered tool set or to a tool's action class, approval setting or rules",
    "Any change to agent-svc entitlements or its accountScope (consented_only)",
    "Any change to the release approval workflow: approval=always on transmit, batch size (20), resource display, approver pool",
    "Any change to the model(s) the agent calls, once identified",
    "Evidence that the documents or MRM validation describe a different deployment from ta-ob-2 (finding F-00)",
  ],
  "partial_retest": ["Change to retention or encryption settings", "Change to the operating procedure OB-PRO-0117 or policy memo OB-POL-0042 without configuration change", "MRM re-validation outcome"],
  "cosmetic": ["Document reformatting or version renumbering without content change", "Change of approver identities within the same pool size"],
}

p["provenance"] = prov
(HERE / "profile.json").write_text(json.dumps(p, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("wrote", HERE / "profile.json")
