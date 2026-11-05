#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Agent Reliability Profile <-> Excel workbook.

  python3 arp_xlsx.py template  OUT.xlsx              # blank template, generated from the spec
  python3 arp_xlsx.py from-json PROFILE.json OUT.xlsx # fill the template from a Profile
  python3 arp_xlsx.py to-json   IN.xlsx OUT.json      # read a filled workbook; runs the checker

The workbook is generated from spec/ (schema and vocabularies), so it stays in step with the
standard. Workbooks produce DRAFT Profiles only: signing is done with the checker
(conformance/arp_conform.py sign). Headline level, disclosures and coverage are derived by the
converter from the levels and results you enter, never typed.

Reading a workbook is strict. An unknown drop-down value, a number or date that cannot be read, a
formula in an input cell, a missing sheet or two provenance rows that disagree are reported by sheet,
row and column, and no JSON is written until they are fixed. Grey rows starting 'e.g.' are examples
and are ignored wherever they are.

Round trip (JSON -> workbook -> JSON) keeps every value, with two normalisations: for optional fields,
absent, null and an empty list are treated alike; and controls and action classes come back in
catalogue order. A list whose items contain commas or line breaks, and a control configuration that is
not plain text, is stored in its cell as 'json:' followed by JSON.

Exit codes: 0 converted and conformant; 1 not conformant, or the workbook has problems; 2 usage.
"""
import datetime as dt, json, re, sys
from pathlib import Path
from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import Alignment, Font, PatternFill, Border, Side, Protection
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.workbook.defined_name import DefinedName

HERE = Path(__file__).resolve().parent
KIT = HERE.parent
sys.path.insert(0, str(KIT / "conformance"))
from arp_conform import check, claim_fields, axis_of  # noqa: E402

def _read_json(path): return json.loads(Path(path).read_text(encoding="utf-8"))
def vocab(name): return _read_json(KIT / "spec" / "vocab" / f"{name}.json")

SCHEMA = _read_json(KIT / "spec" / "profile.schema.json")
SP = SCHEMA["properties"]
SPEC_VERSION = SP["spec"].get("const", "arp/1.0-rc2")      # follows the schema, e.g. arp/1.0-rc2
TEMPLATE_VERSION = f"{SPEC_VERSION} workbook 0.2"
STATUS = ("Status: release candidate 2 of arp/1.0, prepared by the MLCommons Financial Services Working Group for pilot use and comment. "
          "Not a final MLCommons standard, certification scheme or endorsement. Field names and rules may change before 1.0. "
          "Conformance means a Profile is well-formed, consistent, honestly labelled and signed. "
          "It does not mean its claims are true or the agent is safe.")

# ---------------------------------------------------------------- styles
F = "Arial"
H1 = Font(name=F, size=14, bold=True)
HB = Font(name=F, size=10, bold=True, color="FFFFFF")
BODY = Font(name=F, size=10)
GUIDE = Font(name=F, size=9, italic=True, color="6B7280")
KEYF = Font(name=F, size=8, color="9CA3AF")
FILL_IN = PatternFill("solid", fgColor="FFF7CC")      # cells to fill in (pale yellow)
FILL_HEAD = PatternFill("solid", fgColor="1F4E79")
FILL_GUIDE = PatternFill("solid", fgColor="F3F4F6")
FILL_DERIVED = PatternFill("solid", fgColor="E8F0FE")
THIN = Side(style="thin", color="D1D5DB")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="top")

YESNO = ["yes", "no"]
LISTS = {
    "tiers": [t["id"] for t in vocab("autonomy-tiers")["terms"]],
    "tier_basis": SP["claim"]["properties"]["autonomy"]["properties"]["tier_basis"]["enum"],
    "stack": SP["claim"]["properties"]["autonomy"]["properties"]["modifiers"]["properties"]["stack_composability"]["enum"],
    "aq": SP["claim"]["properties"]["autonomy"]["properties"]["approval_quality"]["properties"]["assessment"]["enum"],
    "business_lines": vocab("business-lines")["terms"],
    "use_cases": [f'{t["id"]} — {t["label"]}' for t in vocab("use-cases")["terms"]],
    "action_status": ["permitted", "prohibited", "out of scope", "not stated"],
    "control_status": ["present", "absent", "not established", "not applicable", "not listed"],
    "prov": [t["id"] for t in vocab("provenance-classes")["terms"]],
    "artifact": SP["evidence"]["items"]["properties"]["artifact_class"]["enum"],
    "levels": [1, 2, 3],
    "assessor": SCHEMA["definitions"]["assessor"]["properties"]["role"]["enum"],
    "axis": ["autonomy", "odd", "actions", "controls"],
    "effects": ["voids", "partial_retest", "cosmetic"],
    "triggers": [t["id"] for t in vocab("invalidation-triggers")["terms"]],
    "response": SP["status"]["properties"]["open_findings"]["items"]["properties"]["response"]["enum"],
    "disposition": [t["id"] for t in vocab("dispositions")["terms"]],
    "method": SP["results"]["items"]["properties"]["evaluation"]["properties"]["method"]["enum"],
    "review": SP["results"]["items"]["properties"]["evaluation"]["properties"]["review_status"]["enum"],
    "floor_status": SP["floors"]["items"]["properties"]["status"]["enum"],
    "conflict_kinds": [t["id"] for t in vocab("conflict-kinds")["terms"]],
    "conflict_state": SP["conflicts"]["items"]["properties"]["state"]["enum"],
    "finding_kind": SP["status"]["properties"]["open_findings"]["items"]["properties"]["kind"]["enum"],
    "gap_disp": SP["status"]["properties"]["accepted_gaps"]["items"]["properties"]["disposition"]["enum"],
    "yesno": YESNO,
}
ACTIONS = vocab("action-classes")["terms"]
CONTROLS = vocab("control-catalogue")["terms"]
MODS = [m["id"] if isinstance(m, dict) else m for m in vocab("autonomy-tiers")["modifiers"]]
VOCAB_VERSIONS = {f.stem: json.loads(f.read_text(encoding="utf-8")).get("version") for f in sorted((KIT / "spec" / "vocab").glob("*.json"))}
VOCAB_VERSIONS = {k: v for k, v in VOCAB_VERSIONS.items() if v}
AXES = ["autonomy", "odd", "actions", "controls"]
TRIGGER_IDS = set(LISTS["triggers"]) if "triggers" in LISTS else set()
MOD_GUIDE = {  # preprint §4.1 and Appendix B.1
    "data_authority": "Sensitivity of what the agent may access, independent of what it can do (e.g. 'confidential customer PII, read-only').",
    "reversibility_profile": "Whether the agent's actions can be undone without a heavy penalty (e.g. 'all permitted actions fully reversible').",
    "customer_market_impact": "Who is affected (internal, customer, market, regulator, counterparty) and how badly (e.g. 'internal only; indirect customer impact via analyst decisions').",
    "stack_composability": "Whether the tool surface is predefined in advance or assembled at run time. Choose from the list.",
    "accountability": "Integrated-stack accountability: who stands behind model, harness and infrastructure as a whole (e.g. 'bank owns harness; vendor model under contract').",
    "population_scope": "The range of parties the agent can affect (e.g. 'UK retail customers whose alerts are triaged; about 40,000 a year').",
}
AQ_KEYS = ["assessment", "sample_size", "median_seconds_to_approve", "edit_rate", "rejection_rate", "resource_displayed", "consequence_displayed", "sampled_review_quality", "habituation_catch_rate"]
AQ_BOOL = {"resource_displayed", "consequence_displayed"}
AQ_RATE = {"edit_rate", "rejection_rate", "sampled_review_quality", "habituation_catch_rate"}
USE_CASE_IDS = {t["id"] for t in vocab("use-cases")["terms"]}
COL_HELP = {
    ("Models", "Pinned version"): "The exact model version in production, not a family name.",
    ("Actions", "Status"): "permitted, prohibited, out of scope, or not stated. State every class you can.",
    ("Controls", "Status"): "Set only for controls the claim relies on or the evidence shows; leave the rest 'not listed'.",
    ("Controls", "Configuration (text or JSON)"): "Optional. Plain text, or JSON starting with { or [.",
    ("Provenance", "Field id"): "The claim field this row supports, e.g. autonomy.tier or controls.tool.action_allowlists.",
    ("Provenance", "Provenance class"): "Weakest first: absent, owner_attested, document_derived, configuration_derived, measured.",
    ("Provenance", "Evidence id"): "An id from sheet 7. Needed for every class except absent and owner_attested.",
    ("Provenance", "Verbatim quote"): "The least text that establishes the field. Never copy customer, account or personal identifiers.",
    ("Evidence", "Content hash (sha256:…)"): "From manifest.py; Excel cannot compute it.",
    ("Results", "Disposition"): "held, contradicted, held_by_agent_only or not_established.",
    ("Floors", "Status"): "All floors are 'untested' at Level 1. A failed floor blocks issuance.",
    ("Floors", "Axis"): "The axis whose tests decide the floor; leave blank for a Profile-wide floor.",
    ("Findings", "Response"): "remediation, suspension or risk_acceptance (needed for an issued tier U).",
    ("Invalidation", "Trigger"): "An id from the list (preprint §5.3), or x_<name> for one of your own.",
    ("Invalidation", "Effect"): "voids: the Profile is void; partial_retest: retest the affected part; cosmetic: no effect.",
    ("Results", "Model judge (provider / model / version)"): "Only when a model judged the result: three parts separated by ' / '.",
}
TEXT_KEYS = {"subject.description", "issuance.owner.role", "issuance.issuer.role", "claim.statement", "claim.odd.use_case",
             "claim.odd.description", "claim.odd.operational_scope", "claim.odd.population", "claim.odd.cost_of_failure", "assurance.test_environment",
             "invalidation.monitoring", *[f"assurance.fidelity.{k}" for k in ("tools", "data", "policies", "permissions", "response_times", "failure_conditions", "population")],
             "assurance.method", "assurance.comparability.fidelity_statement", "out_of_scope.statement",
             *[f"claim.autonomy.modifiers.{m}" for m in MODS if m != "stack_composability"]}
DISCLOSURE_FORMULA = ('=TRIM(IF(COUNTIF({axes},1)>0,"Parts of this Profile are Level 1: asserted by the institution and not tested. ","")'
                      '&IF(COUNTIF({axes},2)>0,"Parts were tested by the institution itself, without independence. ","")'
                      '&IF(COUNTIF({axes},3)>0,"Parts were tested by an independent assessor. ","")'
                      '&"Production results in this Profile are specific to this deployment\'s environment and are not comparable with other deployments. "'
                      '&IF({flag}="yes","The benchmark result is comparable with other deployments under the reference conditions only. It adds no assurance about production behaviour.",""))')

def derive_disclosures(axes, flag):
    """The standard disclosures that follow from the axis levels and the comparability flag (SPEC §6)."""
    lv = set(v for v in axes.values() if v); d = []
    if 1 in lv: d.append("level1_untested")
    if 2 in lv: d.append("self_tested")
    if 3 in lv: d.append("independently_verified")
    d.append("not_comparable")
    if flag: d.append("benchmark_not_production")
    return d


# ---------------------------------------------------------------- key/value sheet layouts
# (key, label, list-name or None, guidance)
IDENTITY = [
    ("profile_id", "Profile id", None, "e.g. examplebank.fc.alert-triage.v3.L1"),
    ("subject.institution", "Institution", None, "Legal name of the institution"),
    ("subject.deployment_id", "Deployment id", None, "The institution's own identifier for this agent deployment"),
    ("subject.deployment_version", "Deployment version", None, "Required before issue (ARP-081)"),
    ("subject.description", "Description", None, "One or two sentences on what the agent does"),
    ("subject.vendor_products", "Vendor products", None, "One per line (Alt+Enter); leave blank if none"),
    ("subject.platform_baseline.profile_id", "Platform Baseline Profile id", None, "Only if this agent is anchored to a platform baseline"),
    ("subject.platform_baseline.version", "Platform Baseline version", None, ""),
    ("subject.platform_baseline.content_hash", "Platform Baseline hash", None, "sha256:<64 hex>"),
    ("issuance.owner.name", "Accountable owner — name", None, "A named person"),
    ("issuance.owner.role", "Accountable owner — role", None, ""),
    ("issuance.issuer.name", "Issuer — name", None, "Usually the owner at Levels 1–2"),
    ("issuance.issuer.role", "Issuer — role", None, ""),
    ("issuance.issuer.organisation", "Issuer — organisation", None, ""),
    ("issuance.issuer.independent", "Issuer independent of the institution?", "yesno", "'yes' only for a qualified independent assessor (Level 3)"),
    ("issuance.evidence_as_of", "Evidence as of", None, "YYYY-MM-DD: date of the most recent evidence relied on"),
    ("issuance.valid_from", "Valid from", None, "YYYY-MM-DD; set when the owner issues"),
    ("issuance.valid_until", "Valid until", None, "YYYY-MM-DD; required before issue"),
    ("issuance.issued_at", "Issued at", None, "Type as text: YYYY-MM-DDThh:mm:ssZ (UTC); set when the owner signs"),
]
CLAIM = [
    ("claim.statement", "Bounded claim", None, "One paragraph. A Level 1 claim ends: 'This is a Level 1 Asserted Profile: nothing in it has been tested.'"),
    ("claim.autonomy.tier", "Autonomy tier", "tiers", "T0–T4, or U if the envelope, fallback or action boundaries are unspecified"),
    ("claim.autonomy.tier_basis", "Tier basis", "tier_basis", "'substantiated' only if real approval records support the tier"),
] + [(f"claim.autonomy.modifiers.{m}", "Modifier — " + m.replace("_", " "), "stack" if m == "stack_composability" else None, MOD_GUIDE[m]) for m in MODS] + [
    ("claim.autonomy.approval_quality.assessment", "Approval quality — assessment", "aq", "Leave blank if there is no approval-quality block; required for T2"),
    ("claim.autonomy.approval_quality.sample_size", "Approval quality — sample size", None, "Number of usable approval records"),
    ("claim.autonomy.approval_quality.median_seconds_to_approve", "Approval quality — median seconds", None, ""),
    ("claim.autonomy.approval_quality.edit_rate", "Approval quality — edit rate", None, "0–1"),
    ("claim.autonomy.approval_quality.rejection_rate", "Approval quality — rejection rate", None, "0–1"),
    ("claim.autonomy.approval_quality.resource_displayed", "Approval quality — resource shown to approver?", "yesno", "Required 'yes' for a substantiated T2"),
    ("claim.autonomy.approval_quality.consequence_displayed", "Approval quality — consequence shown to approver?", "yesno", "Is the approver shown what the action will do?"),
    ("claim.autonomy.approval_quality.sampled_review_quality", "Approval quality — sampled review quality", None, "0–1: share of sampled approvals judged substantive on review"),
    ("claim.autonomy.approval_quality.habituation_catch_rate", "Approval quality — habituation catch rate", None, "0–1, if seeded-proposal testing was done"),
    ("claim.odd.business_line", "Business line", "business_lines", ""),
    ("claim.odd.use_case", "Use case (in your words)", None, ""),
    ("claim.odd.use_case_id", "Catalogued use case", "use_cases", "Pick the nearest ODD.1–ODD.52, or type ODD.x_<name> for one not in the catalogue"),
    ("claim.odd.description", "ODD description", None, ""),
    ("claim.odd.operational_scope", "Operational scope", None, "Hours, volumes, channels or other operating limits"),
    ("claim.odd.jurisdictions", "Jurisdictions", None, "Comma-separated codes, e.g. GB, US"),
    ("claim.odd.population", "Population served", None, ""),
    ("claim.odd.data", "Data used", None, "One per line (Alt+Enter)"),
    ("claim.odd.cost_of_failure", "Cost of failure", None, ""),
]
ASSURANCE = [
    ("assurance.axes.autonomy", "Level — autonomy axis", "levels", "1 Asserted · 2 Validated (self-tested) · 3 Verified (independent)"),
    ("assurance.axes.odd", "Level — operational design domain axis", "levels", ""),
    ("assurance.axes.actions", "Level — action-class axis", "levels", ""),
    ("assurance.axes.controls", "Level — control-envelope axis", "levels", ""),
] + [row for ax in AXES for row in (
    (f"assurance.assessors.{ax}.role", f"Who tested — {ax} axis", "assessor", "institution at Levels 1–2; independent_assessor at Level 3"),
    (f"assurance.assessors.{ax}.organisation", f"Tester organisation — {ax} axis", None, "Required for an independent assessor"),
    (f"assurance.assessors.{ax}.report", f"Assessor report (evidence id) — {ax} axis", None, "Level 3: the evidence id of the assessor's signed report (sheet 7, class assessor_report)"),
)] + [
    ("assurance.test_environment", "Test environment", None, "Level 2+: where tests ran and how it differs from production"),
    ("assurance.fidelity.tools", "Fidelity — tools", None, "Level 2+: how the test tools matched production (preprint §7.5)"),
    ("assurance.fidelity.data", "Fidelity — data", None, ""),
    ("assurance.fidelity.policies", "Fidelity — policies", None, ""),
    ("assurance.fidelity.permissions", "Fidelity — access permissions", None, ""),
    ("assurance.fidelity.response_times", "Fidelity — response times", None, ""),
    ("assurance.fidelity.failure_conditions", "Fidelity — failure conditions", None, ""),
    ("assurance.fidelity.population", "Fidelity — population covered", None, ""),
    ("assurance.fidelity.known_differences", "Fidelity — known differences", None, "One per line (Alt+Enter); at least one when fidelity is given"),
    ("assurance.method", "Method (tool and version)", None, "Tool and version; for an agent skill, also the assistant and model that ran it"),
    ("assurance.comparability.flag", "Benchmarked (comparability flag)?", "yesno", "'yes' only for a Benchmarked Profile"),
    ("assurance.comparability.environment_version", "Benchmark environment version", None, ""),
    ("assurance.comparability.hidden_set_version", "Benchmark hidden-set version", None, ""),
    ("assurance.comparability.fidelity_statement", "Benchmark fidelity statement", None, ""),
    ("benchmark", "Benchmark result (JSON)", None, "Benchmarked Profiles only, as JSON: {\"assessor\": {\"organisation\": …, \"accreditation_ref\": …, \"independent\": true}, \"results\": [{\"metric\": …, \"value\": …}]}"),
    ("assurance.reproduction.test_cases", "Rerun package — test cases (evidence id)", None, "Level 2+ (ARP-017)"),
    ("assurance.reproduction.initial_state", "Rerun package — initial state (evidence id)", None, ""),
    ("assurance.reproduction.deployment_config", "Rerun package — deployment config (evidence id)", None, ""),
    ("assurance.reproduction.evaluator_config", "Rerun package — evaluator config (evidence id)", None, ""),
    ("assurance.reproduction.rerun_instructions", "Rerun package — rerun instructions (evidence id)", None, ""),
    ("out_of_scope.statement", "Out-of-scope statement", None, "Usually longer than the claim"),
    ("out_of_scope.odd", "Out of scope — domains", None, "One per line (Alt+Enter)"),
    ("out_of_scope.controls", "Out of scope — controls", None, "Comma-separated control ids"),
    ("out_of_scope.users", "Out of scope — users", None, "One per line (Alt+Enter)"),
    ("invalidation.monitoring", "How these changes are detected", None, "Changes that void the Profile are listed on sheet 14"),
    ("status.exceptions", "Exceptions to policy", None, "One per line (Alt+Enter)"),
    ("status.limitations", "Limitations", None, "One per line (Alt+Enter)"),
    ("status.risk_acceptances", "Risk acceptances", None, "One per line (Alt+Enter)"),
    ("vocab_versions", "Vocabulary versions (JSON)", None, "Prefilled with the versions this template was built from; required before issue (ARP-003)"),
    ("evidence_manifest", "Signed evidence manifest (JSON)", None, "Level 2+: produced by 'arp_conform.py sign-manifest'; do not type it by hand"),
]
SEMI = {"subject.vendor_products", "claim.odd.data", "out_of_scope.odd", "out_of_scope.users", "assurance.fidelity.known_differences", "status.exceptions", "status.limitations", "status.risk_acceptances"}
COMMA = {"claim.odd.jurisdictions", "out_of_scope.controls"}
NUMBERS = {"claim.autonomy.approval_quality.sample_size": int, "claim.autonomy.approval_quality.median_seconds_to_approve": float,
           "claim.autonomy.approval_quality.edit_rate": float, "claim.autonomy.approval_quality.rejection_rate": float,
           "claim.autonomy.approval_quality.habituation_catch_rate": float, "claim.autonomy.approval_quality.sampled_review_quality": float}

# ---------------------------------------------------------------- table sheet layouts: (header, width, list or None)
TABLES = {
    "Models": [("Provider", 22, None), ("Model", 24, None), ("Pinned version", 22, None), ("Role", 26, None)],
    "Actions": [("Class", 8, None), ("Label", 30, None), ("Reversibility", 22, None), ("Status", 16, "action_status")],
    "Controls": [("Control id", 40, None), ("Layer", 13, None), ("Label", 44, None), ("Status", 17, "control_status"), ("Configuration (text or JSON)", 40, None)],
    "Provenance": [("Field id", 44, None), ("Provenance class", 22, "prov"), ("Evidence id", 12, None), ("Locator", 32, None), ("Verbatim quote", 36, None), ("Note", 36, None)],
    "Evidence": [("Evidence id", 12, None), ("Path", 46, None), ("Content hash (sha256:…)", 40, None), ("Artifact class", 26, "artifact"), ("Bytes", 10, None)],
    "Results": [("Claim id", 12, None), ("Field id", 36, None), ("Disposition", 18, "disposition"), ("Scenario", 24, None), ("Runs", 7, None), ("Evidence ids", 14, None),
                ("Method", 15, "method"), ("Tool", 18, None), ("Tool version", 10, None), ("Model judge (provider / model / version)", 26, None), ("Evidence basis", 26, None), ("Review status", 15, "review"), ("Note", 32, None)],
    "Floors": [("Floor id", 26, None), ("Condition", 50, None), ("Status", 12, "floor_status"), ("Finding refs", 16, None), ("Axis", 12, "axis")],
    "Conflicts": [("Conflict #", 10, None), ("Field id", 32, None), ("Kind", 28, "conflict_kinds"), ("State", 11, "conflict_state"), ("Description", 36, None), ("Resolution note", 28, None), ("Resolved by", 18, None), ("Evidence id", 12, None), ("Locator", 26, None), ("Verbatim quote", 32, None)],
    "Findings": [("Finding id", 12, None), ("Kind", 22, "finding_kind"), ("Field id", 32, None), ("Floor ref", 14, None), ("Claim id", 12, None), ("Note", 56, None), ("Response", 16, "response")],
    "Gaps": [("Claim id", 12, None), ("Disposition", 20, "gap_disp"), ("Reason", 56, None), ("Accepted by", 26, None)],
    "Invalidation": [("Effect", 16, "effects"), ("Trigger", 26, "triggers"), ("Ref (field id, optional)", 28, None), ("Description", 70, None)],
}
EXAMPLES = {
    "Models": ["e.g. <provider>", "<model name>", "<pinned version>", "planner and drafter"],
    "Provenance": ["e.g. controls.harness.human_approval_gates", "configuration_derived", "e2", "workflow.approvals", "required: true", "One row per citation; repeat the field id for more"],
    "Evidence": ["e.g. e2", "exports/approval_workflow.yaml", "sha256:9f2c…", "approval_workflow", ""],
    "Results": ["e.g. c-a9", "actions.A9", "held", "B-OB-1 alternate path", 5, "t1", "deterministic", "reference Validator", "0.1", "", "control_decisions, state", "unreviewed", ""],
    "Floors": ["e.g. no_funds_movement", "No A9 action executed in any scenario.", "untested", "", "actions"],
    "Conflicts": ["e.g. 1", "actions.A6", "document_vs_configuration", "open", "Policy prohibits case closure; the service account holds cases:write", "", "", "e1", "§4 Prohibited use", "The agent may not close…"],
    "Findings": ["e.g. of-1", "open_conflict", "actions.A6", "", "", "Policy prohibits case closure but the service account holds cases:write."],
    "Gaps": ["e.g. c-gate", "held_by_agent_only", "The approval gate was never exercised.", "Jordan Example (fictional)"],
    "Invalidation": ["e.g. voids", "model_change", "", "A change of model pin."],
}
FIRST_DATA_ROW = 5   # row 3 = headers, row 4 = example ("e.g."), data from row 5
SHEET_NAMES = {"Identity": "1 Identity", "Models": "2 Models", "Claim": "3 Claim", "Actions": "4 Actions", "Controls": "5 Controls",
               "Provenance": "6 Provenance", "Evidence": "7 Evidence", "Assurance": "8 Assurance & scope", "Results": "9 Results",
               "Floors": "10 Floors", "Conflicts": "11 Conflicts", "Findings": "12 Findings", "Gaps": "13 Accepted gaps",
               "Invalidation": "14 Invalidation"}
INTRO = {
    "Identity": "Who and what this Profile is about. Fill the yellow cells.",
    "Models": "Every model the agent calls, pinned. Required before the Profile is issued (ARP-081).",
    "Claim": "The bounded claim and the autonomy and domain axes.",
    "Actions": "State every action class as permitted, prohibited or out of scope. Record the source for each stated class on sheet 6.",
    "Controls": "All 55 catalogue controls are listed. Set a status only for controls the claim relies on or the evidence shows; leave the rest 'not listed'. Add extension controls (layer.x_name) in blank rows below.",
    "Provenance": "One row per citation. Every filled-in claim field (tier, modifiers, ODD fields, each stated action class, each listed control) needs at least one row. Classes other than absent and owner_attested must cite an evidence id from sheet 7.",
    "Evidence": "The hashed evidence manifest. Excel cannot compute hashes: generate them with skill/arp-profile-builder/scripts/manifest.py (needs Python).",
    "Assurance": "Levels per axis, scope and validity. The headline level and the standard disclosures are derived for you (blue cells).",
    "Results": "Level 2 and above only: one row per tested claim.",
    "Floors": "Pass/fail conditions. All are 'untested' at Level 1.",
    "Conflicts": "Disagreements between sources. Give each conflict a number; add more rows with the same number for further citations.",
    "Findings": "Open findings: open conflicts, failed floors, contradicted claims, tier U, gaps.",
    "Gaps": "Untested or agent-only results the owner accepts (Level 2+).",
    "Invalidation": "The machine-readable invalidation list (preprint §5.3): one row per change that voids the Profile, needs a partial retest, or is cosmetic. At least one 'voids' row.",
}

UNLOCKED = Protection(locked=False)

def _lists_sheet(wb):
    ws = wb.create_sheet("Lists")
    for col, (name, vals) in enumerate(LISTS.items(), 1):
        ws.cell(1, col, name).font = BODY
        for r, v in enumerate(vals, 2):
            ws.cell(r, col, v)
        letter = ws.cell(1, col).column_letter
        wb.defined_names[f"L_{name}"] = DefinedName(f"L_{name}", attr_text=f"Lists!${letter}$2:${letter}${len(vals)+1}")
    ws.sheet_state = "hidden"

def _dv(ws, listname, ref, title="", prompt=""):
    dv = DataValidation(type="list", formula1=f"=L_{listname}", allow_blank=True, showErrorMessage=listname not in ("use_cases", "triggers"))
    dv.error = "Choose a value from the list."
    if prompt:
        dv.showInputMessage = True; dv.promptTitle = title[:32]; dv.prompt = prompt[:250]
    ws.add_data_validation(dv); dv.add(ref)

def _prompt(ws, ref, title, prompt):
    """An input message shown when the cell is selected; it does not restrict the value."""
    if not prompt: return
    dv = DataValidation(showInputMessage=True, promptTitle=title[:32], prompt=prompt[:250])
    ws.add_data_validation(dv); dv.add(ref)

def _protect(ws):
    """Lock the sheet (no password) so derived and prefilled cells are not typed over; input cells stay unlocked."""
    ws.protection.sheet = True
    ws.protection.formatColumns = False; ws.protection.formatRows = False; ws.protection.formatCells = False

def _title(ws, key):
    ws["A1"] = SHEET_NAMES[key][SHEET_NAMES[key].index(" ")+1:]; ws["A1"].font = H1
    ws["A2"] = INTRO[key]; ws["A2"].font = GUIDE; ws["A2"].alignment = Alignment(wrap_text=False)

def _kv_sheet(wb, key, rows):
    ws = wb.create_sheet(SHEET_NAMES[key]); _title(ws, key)
    for c, (h, w) in enumerate([("Field", 44), ("Value", 60), ("Guidance", 70), ("Field id (used by the converter; do not edit)", 40)], 1):
        cell = ws.cell(3, c, h); cell.font = HB; cell.fill = FILL_HEAD; ws.column_dimensions[cell.column_letter].width = w
    for i, (k, label, lst, guide) in enumerate(rows, 4):
        ws.cell(i, 1, label).font = BODY
        v = ws.cell(i, 2); v.fill = FILL_IN; v.border = BOX; v.font = BODY; v.alignment = WRAP; v.protection = UNLOCKED
        ws.cell(i, 3, guide).font = GUIDE
        ws.cell(i, 4, k).font = KEYF
        if lst: _dv(ws, lst, f"B{i}", label, guide or "Choose from the list.")
        else: _prompt(ws, f"B{i}", label, guide)
    ws.freeze_panes = "B4"
    return ws

def _table_sheet(wb, key, prefill=None, blank_rows=40):
    ws = wb.create_sheet(SHEET_NAMES[key]); _title(ws, key)
    cols = TABLES[key]
    for c, (h, w, _) in enumerate(cols, 1):
        cell = ws.cell(3, c, h); cell.font = HB; cell.fill = FILL_HEAD; cell.alignment = WRAP
        ws.column_dimensions[cell.column_letter].width = w
    if key in EXAMPLES:
        for c, v in enumerate(EXAMPLES[key], 1):
            cell = ws.cell(4, c, v); cell.font = GUIDE; cell.fill = FILL_GUIDE
    else:
        ws.cell(4, 1, "(no example row: the rows below are prefilled from the spec)").font = GUIDE
    rows = prefill or []
    n = len(rows) + blank_rows
    fixed = 3 if key in ("Actions", "Controls") else 0
    for r in range(FIRST_DATA_ROW, FIRST_DATA_ROW + n):
        for c, (_, _, lst) in enumerate(cols, 1):
            cell = ws.cell(r, c); cell.border = BOX; cell.font = BODY
            editable = not (prefill and r < FIRST_DATA_ROW + len(rows) and c <= fixed)
            if editable: cell.fill = FILL_IN; cell.protection = UNLOCKED
    for i, vals in enumerate(rows):
        for c, v in enumerate(vals, 1):
            if v is not None: _put(ws, FIRST_DATA_ROW + i, c, v)
    for c, (h, _, lst) in enumerate(cols, 1):
        L = ws.cell(3, c).column_letter; ref = f"{L}{FIRST_DATA_ROW}:{L}{FIRST_DATA_ROW + n - 1}"
        help_ = COL_HELP.get((key, h), "")
        if lst: _dv(ws, lst, ref, h, help_ or "Choose from the list.")
        else: _prompt(ws, ref, h, help_)
    ws.freeze_panes = ws.cell(FIRST_DATA_ROW, 1)
    if fixed: _protect(ws)
    return ws

def build_template():
    wb = Workbook(); ws = wb.active; ws.title = "Start here"
    ws.column_dimensions["A"].width = 120
    B11 = Font(name=F, size=11, bold=True)
    lines = [
        ("Agent Reliability Profile — workbook template", H1),
        (f"Spec {SPEC_VERSION} · {TEMPLATE_VERSION} · generated from the kit's spec files", GUIDE),
        (STATUS, GUIDE),
        ("", BODY),
        ("What this is", B11),
        ("A spreadsheet version of one Agent Reliability Profile: one deployment, one workbook. Everything except one step is done in Excel.", BODY),
        ("", BODY),
        ("The one step that needs Python", B11),
        ("Converting the finished workbook to the machine-readable Profile (JSON), and hashing evidence files for sheet 7, need a colleague who can run Python 3.10+:", BODY),
        ("    python3 templates/arp_xlsx.py to-json MyProfile.xlsx MyProfile.json", Font(name="Courier New", size=10)),
        ("    python3 skill/arp-profile-builder/scripts/manifest.py <evidence folder>      (evidence hashes for sheet 7)", Font(name="Courier New", size=10)),
        ("The converter names the sheet, row and column of anything it cannot read, then runs the reference checker and lists anything that does not conform, by rule (spec/SPEC.md).", BODY),
        ("", BODY),
        ("How to fill it in", B11),
        ("• Pale yellow cells are for you to fill in. Grey italic rows starting 'e.g.' are examples and are ignored. Select a cell to see its guidance.", BODY),
        ("• Blue cells are derived for you (headline level, standard disclosures). Sheets with derived or prefilled cells are protected (no password) so they are not typed over.", BODY),
        ("• Use the drop-downs: tiers, action classes, the 55 controls, provenance classes, use cases. A value typed by hand that is not on the list is reported as an error.", BODY),
        ("• Type dates as YYYY-MM-DD and 'Issued at' as text, YYYY-MM-DDThh:mm:ssZ. Type rates as 0.18 or 18%. Do not put formulas in yellow cells.", BODY),
        ("• Do not rename or delete sheets, and do not edit the 'Field id' column: the converter uses them.", BODY),
        ("• Work through the sheets in order. Sheet 6 (Provenance) records where each claim comes from; the checker requires it.", BODY),
        ("• Levels 2 and 3 need test results (sheet 9), coverage is computed from them, and a rerun package (sheet 8).", BODY),
        ("", BODY),
        ("The six autonomy modifiers (sheet 3)", B11),
        *[("• " + m.replace("_", " ").capitalize() + ": " + MOD_GUIDE[m], BODY) for m in MODS],
        ("", BODY),
        ("What a workbook can and cannot do", B11),
        ("• A workbook produces a DRAFT Profile. Only the accountable owner can issue it, by signing with the checker: python3 conformance/arp_conform.py sign …", BODY),
        ("• Passing the checker means the Profile is well-formed, consistent, honestly labelled and (once issued) signed. It does not mean its claims are true or the agent is safe.", BODY),
        ("• Every rendering of a Profile must show its standard disclosures (for example 'not tested', 'not comparable'); sheet 8 shows the ones that apply.", BODY),
        ("", BODY),
        ("Worked example", B11),
        ("templates/examples/example-aml-alert-triage-L1.xlsx is this template filled from the kit's fictional Level 1 example.", BODY),
    ]
    for i, (txt, font) in enumerate(lines, 1):
        c = ws.cell(i, 1, txt); c.font = font
        if font is GUIDE or font is BODY: c.alignment = Alignment(wrap_text=True, vertical="top")
    _lists_sheet(wb)
    _kv_sheet(wb, "Identity", IDENTITY)
    _table_sheet(wb, "Models", blank_rows=10)
    _kv_sheet(wb, "Claim", CLAIM)
    _table_sheet(wb, "Actions", [[a["id"], a["label"], a["reversibility"].replace("_", " "), "not stated"] for a in ACTIONS], blank_rows=0)
    _table_sheet(wb, "Controls", [[c["id"], c["layer"], c["label"], "not listed", None] for c in CONTROLS], blank_rows=10)
    _table_sheet(wb, "Provenance", blank_rows=150)
    _table_sheet(wb, "Evidence", blank_rows=60)
    ws = _kv_sheet(wb, "Assurance", ASSURANCE)
    row = {k: i for i, (k, *_r) in enumerate(ASSURANCE, 4)}
    axes = f"B{row['assurance.axes.autonomy']}:B{row['assurance.axes.controls']}"
    flag = f"B{row['assurance.comparability.flag']}"
    r = len(ASSURANCE) + 5
    ws.cell(r, 1, "Headline level (derived)").font = Font(name=F, size=10, bold=True)
    hc = ws.cell(r, 2, f"=IF(COUNT({axes})=4,MIN({axes}),\"\")"); hc.fill = FILL_DERIVED; hc.font = BODY
    ws.cell(r, 3, "The minimum of the four axis levels (ARP-010)").font = GUIDE
    ws.cell(r + 1, 1, "Standard disclosures (derived)").font = Font(name=F, size=10, bold=True)
    dc = ws.cell(r + 1, 2, DISCLOSURE_FORMULA.format(axes=axes, flag=flag))
    dc.fill = FILL_DERIVED; dc.font = BODY; dc.alignment = WRAP; ws.row_dimensions[r + 1].height = 75
    ws.cell(r + 1, 3, "Must be shown with any rendering of the Profile (SPEC §6). The converter derives the exact list.").font = GUIDE
    _protect(ws)
    _table_sheet(wb, "Results", blank_rows=60)
    _table_sheet(wb, "Floors", blank_rows=20)
    _table_sheet(wb, "Conflicts", blank_rows=40)
    _table_sheet(wb, "Findings", blank_rows=30)
    _table_sheet(wb, "Gaps", blank_rows=20)
    _table_sheet(wb, "Invalidation", blank_rows=20)
    _kv_write(wb[SHEET_NAMES["Assurance"]], {"vocab_versions": "json:" + json.dumps(VOCAB_VERSIONS, ensure_ascii=False)})
    wb.calculation.fullCalcOnLoad = True
    return wb

# ---------------------------------------------------------------- helpers
class WorkbookError(Exception):
    """The workbook cannot be read (missing sheet, unreadable file) or has problems listed in .problems."""
    def __init__(self, msg, problems=()):
        super().__init__(msg); self.problems = list(problems)

def _put(ws, r, c, v):
    """Write a value. Text that starts with '=' is stored as text, never as a live formula."""
    cell = ws.cell(r, c, v)
    if isinstance(v, str) and v.startswith("="): cell.data_type = "s"
    return cell

def _kv_write(ws, values):
    for r in range(4, ws.max_row + 1):
        k = ws.cell(r, 4).value
        if k in values:
            if values[k] is not None: _put(ws, r, 2, values[k])
            elif k == "vocab_versions": ws.cell(r, 2).value = None

def _code(v):
    """A code, id, enum value or date: trimmed text."""
    if v is None: return None
    if isinstance(v, dt.datetime): return v.date().isoformat() if not (v.hour or v.minute or v.second) else v.strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(v, dt.date): return v.isoformat()
    if isinstance(v, bool): return "yes" if v else "no"
    if isinstance(v, float) and v.is_integer(): return str(int(v))
    s = str(v).strip()
    return s or None

def _text(v):
    """Free text: kept exactly as typed (only an all-blank cell counts as empty)."""
    if v is None: return None
    if isinstance(v, str): return v if v.strip() else None
    return _code(v)

def _join(items, sep):
    """A list for one cell: 'a, b' for codes, one item per line for text; 'json:[…]' when items would not survive splitting."""
    items = list(items or [])
    if not items: return None
    joiner = ", " if sep == "," else "\n"
    plain = all(isinstance(x, str) and x and x == x.strip() and "\n" not in x and (sep != "," or "," not in x) for x in items)
    s = joiner.join(items)
    return s if plain and not s.startswith("json:") else "json:" + json.dumps(items, ensure_ascii=False)

def _cfg_out(v):
    if isinstance(v, str) and v and not v.startswith(("{", "[", "json:")): return v
    return "json:" + json.dumps(v, ensure_ascii=False)

def _yn(v): return None if v is None else v == "yes"

def _judge_out(j):
    """A model judge for one cell: 'provider / model / version', or json: when a part would not survive splitting."""
    if j is None: return None
    if isinstance(j, dict) and set(j) == {"provider", "model", "version"} and all(isinstance(x, str) and x and x == x.strip() and " / " not in x for x in j.values()):
        return f'{j["provider"]} / {j["model"]} / {j["version"]}'
    return "json:" + json.dumps(j, ensure_ascii=False)

class Reader:
    """Reads a filled workbook, collecting every problem with its sheet, row and column."""
    def __init__(self, path):
        try: self.wb = load_workbook(path)
        except Exception as e: raise WorkbookError(f"cannot open {path} as an Excel workbook: {e}")
        self.errors, self.warnings = [], []

    def err(self, where, msg): self.errors.append(f"{where}: {msg}")
    def warn(self, where, msg): self.warnings.append(f"{where}: {msg}")

    def sheet(self, key):
        name = SHEET_NAMES[key]
        if name in self.wb.sheetnames: return self.wb[name]
        title = name.split(" ", 1)[1]
        for ws in self.wb.worksheets:
            if ws.cell(1, 1).value == title:
                self.warn(f"sheet '{ws.title}'", f"expected the name '{name}'; read it because its title is '{title}'")
                return ws
        raise WorkbookError(f"sheet '{name}' is missing. Do not rename or delete the workbook's sheets; copy your entries into a fresh template if needed.")

    def cell(self, ws, r, c, where):
        cell = ws.cell(r, c)
        if cell.data_type == "f":
            self.err(where, f"contains a formula ({cell.value}); type the value itself"); return None
        v = cell.value
        return None if isinstance(v, str) and not v.strip() else v

    def enum(self, v, lst, where):
        s = _code(v)
        if s is None: return None
        if lst == "levels":
            m = re.fullmatch(r"(?:level\s*|l)?\s*([123])", s, re.I)
            if m: return int(m.group(1))
        if lst == "yesno":
            if s.lower() in ("yes", "y", "true"): return "yes"
            if s.lower() in ("no", "n", "false"): return "no"
        if lst == "triggers":
            if s in TRIGGER_IDS or re.fullmatch(r"x_[a-z0-9_]+", s): return s
            self.err(where, f"'{s}' is not a trigger id; pick one from the list or type x_<name> (lower case, digits, underscores)")
            return None
        if lst == "use_cases":
            uid = s.split(" — ")[0].strip()
            if uid in USE_CASE_IDS or re.fullmatch(r"ODD\.x_[a-z0-9_]+", uid): return uid
            self.err(where, f"'{s}' is not a catalogued use case; pick one from the list or type ODD.x_<name> (lower case, digits, underscores)")
            return None
        for a in LISTS[lst]:
            if str(a).lower() == s.lower(): return a
        allowed = [str(a) for a in LISTS[lst]]
        self.err(where, f"'{s}' is not an allowed value; choose one of: " + ", ".join(allowed[:14]) + (" …" if len(allowed) > 14 else ""))
        return None

    def num(self, v, kind, where, rate=False):
        if v is None: return None
        if isinstance(v, bool): self.err(where, f"'{v}' is not a number"); return None
        if isinstance(v, (int, float)): x = v
        else:
            s = str(v).strip(); pct = rate and s.endswith("%")
            try: x = float(s[:-1].strip() if pct else s)
            except ValueError:
                self.err(where, f"'{s}' is not a number" + (" (write 0.18 or 18%)" if rate else "")); return None
            if pct: x = round(x / 100, 10)
        if kind is int:
            if float(x) != int(x): self.err(where, f"{x} is not a whole number"); return None
            return int(x)
        return int(x) if isinstance(x, float) and x.is_integer() else x

    def date(self, v, where):
        if v is None: return None
        if isinstance(v, dt.datetime):
            if v.hour or v.minute or v.second: self.warn(where, "a time was entered where a date is expected; the time was dropped")
            return v.date().isoformat()
        if isinstance(v, dt.date): return v.isoformat()
        s = str(v).strip()
        if s == "TODO": self.warn(where, "still TODO"); return s
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
            try: dt.date.fromisoformat(s); return s
            except ValueError: pass
        self.err(where, f"'{s}' is not a date; use YYYY-MM-DD"); return None

    def datetime(self, v, where):
        if v is None: return None
        if isinstance(v, dt.datetime):
            self.warn(where, "Excel stores no time zone, so the time was read as UTC; type it as text (YYYY-MM-DDThh:mm:ssZ) to be exact")
            return v.strftime("%Y-%m-%dT%H:%M:%SZ")
        if isinstance(v, dt.date):
            self.err(where, "a date and time is needed (YYYY-MM-DDThh:mm:ssZ), not a date"); return None
        s = str(v).strip()
        if s == "TODO": self.warn(where, "still TODO"); return s
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?(Z|[+-]\d{2}:\d{2})", s):
            try: dt.datetime.fromisoformat(s.replace("Z", "+00:00")); return s
            except ValueError: pass
        self.err(where, f"'{s}' is not a date-time; use YYYY-MM-DDThh:mm:ssZ"); return None

    def split(self, v, sep, where):
        """A list from one cell: comma-separated codes, or one item per line; 'json:[…]' is read as JSON."""
        if v is None: return []
        if isinstance(v, str) and v.startswith("json:"):
            try: x = json.loads(v[5:])
            except json.JSONDecodeError as e: self.err(where, f"the JSON after 'json:' does not parse ({e.msg})"); return []
            if not (isinstance(x, list) and all(isinstance(i, str) for i in x)):
                self.err(where, "'json:' must be followed by a list of text items"); return []
            return x
        s = _code(v) if sep == "," else _text(v)
        if not s: return []
        return [x.strip() for x in s.split("," if sep == "," else "\n") if x.strip()]

    def config(self, v, where):
        if isinstance(v, str):
            if v.startswith("json:"):
                try: return json.loads(v[5:])
                except json.JSONDecodeError as e: self.err(where, f"the JSON after 'json:' does not parse ({e.msg})"); return None
            if v.strip().startswith(("{", "[")):
                try: return json.loads(v)
                except json.JSONDecodeError as e: self.err(where, f"looks like JSON but does not parse ({e.msg}); fix it, or start the cell with text"); return None
        return v

    def kv(self, key, layout):
        """Key/value sheet -> {field key: value as typed}, plus {field key: location}."""
        ws = self.sheet(key); spec = {k: (label, lst) for k, label, lst, _ in layout}
        out, where = {}, {}
        for r in range(1, ws.max_row + 1):
            k = ws.cell(r, 4).value
            if k not in spec: continue
            label, lst = spec[k]
            w = where[k] = f"sheet '{ws.title}' › {label} (cell B{r})"
            v = self.cell(ws, r, 2, w)
            if v is not None and lst: v = self.enum(v, lst, w)
            out[k] = v
        missing = [spec[k][0] for k in spec if k not in where]
        if missing: self.warn(f"sheet '{ws.title}'", "rows not found, read as blank (use the current template): " + ", ".join(missing))
        return out, where

    def rows(self, key, text_cols=()):
        """Table sheet -> (row number, values) for every non-empty data row; example rows are skipped wherever they are."""
        ws = self.sheet(key); cols = TABLES[key]
        head = next((r for r in range(1, 11) if _code(ws.cell(r, 1).value) == cols[0][0]), None)
        if head is None:
            raise WorkbookError(f"sheet '{ws.title}': header row not found (column A should be headed '{cols[0][0]}')")
        for r in range(head + 1, ws.max_row + 1):
            first = ws.cell(r, 1).value
            if isinstance(first, str) and first.strip().startswith(("e.g.", "(no example row")): continue
            vals = []
            for c, (h, _, lst) in enumerate(cols):
                w = f"sheet '{ws.title}' row {r} column '{h}'"
                v = self.cell(ws, r, c + 1, w)
                if v is not None and c not in text_cols and lst is None and isinstance(v, str): v = v.strip()
                if v is not None and lst: v = self.enum(v, lst, w)
                vals.append(v)
            for c in range(len(cols) + 1, ws.max_column + 1):
                x = ws.cell(r, c).value
                if x is not None and str(x).strip():
                    self.warn(f"sheet '{ws.title}' row {r} column {get_column_letter(c)}",
                              f"text outside the table's columns was not read: \"{str(x).strip()[:60]}\". Move it into a column of the table")
            if any(v is not None for v in vals): yield r, vals

    def at(self, key, r, col):
        return f"sheet '{self.sheet(key).title}' row {r} column '{TABLES[key][col][0]}'"

# ---------------------------------------------------------------- workbook -> Profile
def read_workbook(path):
    """Workbook -> (draft Profile, Reader). Problems are in reader.errors; nothing is raised for them."""
    rd = Reader(path)
    idn, iw = rd.kv("Identity", IDENTITY); cl, cw = rd.kv("Claim", CLAIM); asr, aw = rd.kv("Assurance", ASSURANCE)
    W = {**iw, **cw, **aw}
    def g(d, k):
        v = d.get(k)
        return _text(v) if k in TEXT_KEYS else _code(v)
    p = {"spec": SPEC_VERSION, "profile_id": g(idn, "profile_id"), "stage": "draft"}
    pb = {k: g(idn, f"subject.platform_baseline.{k}") for k in ("profile_id", "version", "content_hash")}
    models = []
    for r, v in rd.rows("Models", text_cols={3}):
        m = {"provider": _code(v[0]), "model": _code(v[1]), "version": _code(v[2])}
        if v[3] is not None: m["role"] = _text(v[3])
        models.append(m)
    p["subject"] = {"institution": g(idn, "subject.institution"), "deployment_id": g(idn, "subject.deployment_id"),
                    "deployment_version": g(idn, "subject.deployment_version")}
    if g(idn, "subject.description"): p["subject"]["description"] = g(idn, "subject.description")
    p["subject"]["vendor_products"] = rd.split(idn.get("subject.vendor_products"), "\n", W["subject.vendor_products"])
    p["subject"]["platform_baseline"] = pb if any(pb.values()) else None
    p["subject"]["models"] = models
    iss = {"owner": {"name": g(idn, "issuance.owner.name"), "role": g(idn, "issuance.owner.role")}}
    if any(g(idn, f"issuance.issuer.{k}") for k in ("name", "role", "organisation")):
        iss["issuer"] = {"name": g(idn, "issuance.issuer.name")}
        if g(idn, "issuance.issuer.role"): iss["issuer"]["role"] = g(idn, "issuance.issuer.role")
        iss["issuer"]["organisation"] = g(idn, "issuance.issuer.organisation")
        iss["issuer"]["independent"] = bool(_yn(idn.get("issuance.issuer.independent")))
    iss["issued_at"] = rd.datetime(idn.get("issuance.issued_at"), W["issuance.issued_at"])
    for k in ("valid_from", "valid_until", "evidence_as_of"):
        iss[k] = rd.date(idn.get(f"issuance.{k}"), W[f"issuance.{k}"])
    p["issuance"] = {k: iss[k] for k in ("owner", "issuer", "issued_at", "valid_from", "valid_until", "evidence_as_of") if k in iss}
    # claim
    au = {"tier": g(cl, "claim.autonomy.tier"), "tier_basis": g(cl, "claim.autonomy.tier_basis"),
          "modifiers": {m: g(cl, f"claim.autonomy.modifiers.{m}") for m in MODS}}
    if g(cl, "claim.autonomy.approval_quality.assessment"):
        aq = {"assessment": g(cl, "claim.autonomy.approval_quality.assessment")}
        for k in AQ_KEYS[1:]:
            fk = f"claim.autonomy.approval_quality.{k}"
            if k in AQ_BOOL: x = _yn(cl.get(fk))
            else: x = rd.num(cl.get(fk), NUMBERS[fk], W[fk], rate=k in AQ_RATE)
            if x is not None: aq[k] = x
        au["approval_quality"] = aq
    odd = {"business_line": g(cl, "claim.odd.business_line"), "use_case": g(cl, "claim.odd.use_case")}
    if cl.get("claim.odd.use_case_id"): odd["use_case_id"] = cl["claim.odd.use_case_id"]
    for k in ("description", "operational_scope", "population", "cost_of_failure"):
        if g(cl, f"claim.odd.{k}"): odd[k] = g(cl, f"claim.odd.{k}")
    if cl.get("claim.odd.jurisdictions"): odd["jurisdictions"] = rd.split(cl["claim.odd.jurisdictions"], ",", W["claim.odd.jurisdictions"])
    if cl.get("claim.odd.data"): odd["data"] = rd.split(cl["claim.odd.data"], "\n", W["claim.odd.data"])
    permitted, prohibited, oos_actions = [], [], []
    for r, v in rd.rows("Actions"):
        st = v[3] or "not stated"
        {"permitted": permitted, "prohibited": prohibited, "out of scope": oos_actions}.get(st, []).append(_code(v[0]))
    controls = []
    for r, v in rd.rows("Controls", text_cols={4}):
        st = v[3] or "not listed"
        if st == "not listed": continue
        if not v[0]: rd.err(rd.at("Controls", r, 0), f"status '{st}' is set but the control id is blank"); continue
        c = {"control_id": _code(v[0]), "layer": _code(v[1]) or _code(v[0]).split(".")[0],
             "present": {"present": True, "absent": False}.get(st)}
        if st == "not applicable": c["applicable"] = False; c["present"] = None
        if v[4] is not None: c["configuration"] = rd.config(v[4], rd.at("Controls", r, 4))
        controls.append(c)
    p["claim"] = {"statement": g(cl, "claim.statement"), "autonomy": au, "odd": odd,
                  "actions": {"permitted": permitted, "prohibited": prohibited}, "controls": controls}
    # assurance
    axes = {ax: asr.get(f"assurance.axes.{ax}") for ax in ("autonomy", "odd", "actions", "controls")}
    flag = bool(_yn(asr.get("assurance.comparability.flag")))
    a = {"axes": axes, "headline": min(axes.values()) if all(axes.values()) else None,
         "assessors": {}, "test_environment": g(asr, "assurance.test_environment"), "method": g(asr, "assurance.method"),
         "comparability": {"flag": flag, **{k: g(asr, f"assurance.comparability.{k}") for k in ("environment_version", "hidden_set_version", "fidelity_statement")}}}
    for ax in AXES:
        who = {"role": g(asr, f"assurance.assessors.{ax}.role") or ("independent_assessor" if axes.get(ax) == 3 else "institution")}
        for k in ("organisation", "report"):
            if g(asr, f"assurance.assessors.{ax}.{k}") is not None: who[k] = g(asr, f"assurance.assessors.{ax}.{k}")
        a["assessors"][ax] = who
    fid = {k: g(asr, f"assurance.fidelity.{k}") for k in ("tools", "data", "policies", "permissions", "response_times", "failure_conditions", "population")}
    kd = rd.split(asr.get("assurance.fidelity.known_differences"), "\n", W["assurance.fidelity.known_differences"])
    if any(fid.values()) or kd: a["fidelity"] = {**fid, "known_differences": kd}
    a["disclosures"] = derive_disclosures(axes, flag)
    rep = {k: g(asr, f"assurance.reproduction.{k}") for k in ("test_cases", "initial_state", "deployment_config", "evaluator_config", "rerun_instructions")}
    # provenance
    prov, first_row = {}, {}
    for r, v in rd.rows("Provenance", text_cols={3, 4, 5}):
        fid = _code(v[0])
        if not fid: rd.err(rd.at("Provenance", r, 0), "this citation has no field id"); continue
        if fid in prov:
            e = prov[fid]
            if v[1] and e.get("class") and v[1] != e["class"]:
                rd.err(rd.at("Provenance", r, 1), f"'{v[1]}' disagrees with row {first_row[fid]} ('{e['class']}') for {fid}; a field has one provenance class")
            elif v[1] and not e.get("class"): e["class"] = v[1]
        else:
            e = prov[fid] = {"class": v[1]}; first_row[fid] = r
        if v[2]:
            cit = {"evidence_id": _code(v[2])}
            if v[3] is not None: cit["locator"] = _text(v[3])
            if v[4] is not None: cit["verbatim"] = _text(v[4])
            e.setdefault("citations", []).append(cit)
        if v[5] is not None:
            if "note" in e and e["note"] != _text(v[5]): rd.err(rd.at("Provenance", r, 5), f"a second, different note for {fid}; put one note per field")
            e["note"] = _text(v[5])
    p["provenance"] = prov
    # conflicts
    conf = {}
    for r, v in rd.rows("Conflicts", text_cols={4, 5, 6, 8, 9}):
        n = _code(v[0]) or str(len(conf) + 1)
        c = conf.setdefault(n, {"field_id": _code(v[1]), "kind": v[2]})
        for k, i in (("state", 3), ("description", 4), ("resolution_note", 5), ("resolved_by", 6)):
            if v[i] is not None and k not in c: c[k] = v[i] if k == "state" else _text(v[i])
        if v[7]:
            cit = {"evidence_id": _code(v[7])}
            if v[8] is not None: cit["locator"] = _text(v[8])
            if v[9] is not None: cit["verbatim"] = _text(v[9])
            c.setdefault("citations", []).append(cit)
    order = ["field_id", "kind", "citations", "state"]
    p["conflicts"] = [dict(sorted(c.items(), key=lambda kv: order.index(kv[0]) if kv[0] in order else 9)) for c in conf.values()]
    floors = []
    for r, v in rd.rows("Floors", text_cols={1}):
        f = {"id": _code(v[0]), "condition": _text(v[1])}
        if v[4]: f["axis"] = v[4]
        f["status"] = v[2] or "untested"
        refs = rd.split(v[3], ",", rd.at("Floors", r, 3))
        if refs: f["finding_refs"] = refs
        floors.append(f)
    p["floors"] = floors
    results = []
    for r, v in rd.rows("Results", text_cols={3, 12}):
        x = {"claim_id": _code(v[0]), "field_id": _code(v[1]), "disposition": v[2]}
        if v[3] is not None: x["scenario"] = _text(v[3])
        if v[4] is not None: x["runs"] = rd.num(v[4], int, rd.at("Results", r, 4))
        x["evidence_refs"] = rd.split(v[5], ",", rd.at("Results", r, 5))
        ev = {"method": v[6], "tool": _code(v[7]), "version": _code(v[8])}
        if v[9] is not None:
            jm = rd.config(v[9], rd.at("Results", r, 9))
            if isinstance(jm, str):
                parts = [x.strip() for x in jm.split(" / ")]
                if len(parts) == 3 and all(parts): jm = dict(zip(("provider", "model", "version"), parts))
                else: rd.err(rd.at("Results", r, 9), f"'{jm}' should be provider / model / version"); jm = None
            ev["judge_model"] = jm
        ev["evidence_basis"] = rd.split(v[10], ",", rd.at("Results", r, 10)); ev["review_status"] = v[11] or "unreviewed"
        x["evaluation"] = ev
        if v[12] is not None: x["note"] = _text(v[12])
        results.append(x)
    p["results"] = results
    if all(axes.values()) and max(axes.values()) >= 2:
        fields = claim_fields(p["claim"]); JUD = {"held", "contradicted"}; cov = {}
        for ax, l in axes.items():
            if l < 2: continue
            on = [x for x in results if axis_of(x["field_id"] or "") == ax]
            cov[ax] = {"claim_fields": sum(1 for f in fields if axis_of(f) == ax), "tested": len({x["field_id"] for x in on}),
                       "judged": len({x["field_id"] for x in on if x["disposition"] in JUD})}
        a["coverage"] = cov
    if any(rep.values()): a["reproduction"] = rep
    p["assurance"] = a
    bm = asr.get("benchmark")
    p["benchmark"] = rd.config(bm, W["benchmark"]) if bm is not None else None
    p["out_of_scope"] = {"statement": g(asr, "out_of_scope.statement"), "odd": rd.split(asr.get("out_of_scope.odd"), "\n", W["out_of_scope.odd"]),
                         "actions": oos_actions, "controls": rd.split(asr.get("out_of_scope.controls"), ",", W["out_of_scope.controls"]),
                         "users": rd.split(asr.get("out_of_scope.users"), "\n", W["out_of_scope.users"])}
    inv = {"voids": [], "partial_retest": [], "cosmetic": []}
    for r, v in rd.rows("Invalidation", text_cols={3}):
        if not v[0]: rd.err(rd.at("Invalidation", r, 0), "choose an effect: voids, partial_retest or cosmetic"); continue
        if not v[1]: rd.err(rd.at("Invalidation", r, 1), "this row has no trigger"); continue
        it = {"trigger": v[1]}
        if v[2] is not None: it["ref"] = _code(v[2])
        it["description"] = _text(v[3])
        inv[v[0]].append(it)
    if g(asr, "invalidation.monitoring"): inv["monitoring"] = g(asr, "invalidation.monitoring")
    p["invalidation"] = inv
    for k in ("vocab_versions", "evidence_manifest"):
        x = asr.get(k)
        if x is not None:
            x = rd.config(x, W[k])
            if x is not None and not isinstance(x, dict): rd.err(W[k], "must be a JSON object (start the cell with json: or {)"); x = None
        if x is not None: p[k] = x
    ev = []
    for r, v in rd.rows("Evidence"):
        e = {"id": _code(v[0]), "path": _code(v[1]), "content_hash": _code(v[2])}
        if v[3]: e["artifact_class"] = v[3]
        if v[4] is not None: e["bytes"] = rd.num(v[4], int, rd.at("Evidence", r, 4))
        ev.append(e)
    p["evidence"] = ev
    of = []
    for r, v in rd.rows("Findings", text_cols={5}):
        f = {"id": _code(v[0]), "kind": v[1]}
        for k, i in (("field_id", 2), ("floor_ref", 3), ("claim_id", 4)):
            if v[i] is not None: f[k] = _code(v[i])
        f["note"] = _text(v[5])
        if v[6]: f["response"] = v[6]
        of.append(f)
    gaps = [{"claim_id": _code(v[0]), "disposition": v[1], "reason": _text(v[2]), "accepted_by": _text(v[3])} for _, v in rd.rows("Gaps", text_cols={2, 3})]
    p["status"] = {"open_findings": of, "accepted_gaps": gaps,
                   "exceptions": rd.split(asr.get("status.exceptions"), "\n", W["status.exceptions"]),
                   "risk_acceptances": rd.split(asr.get("status.risk_acceptances"), "\n", W["status.risk_acceptances"]),
                   "limitations": rd.split(asr.get("status.limitations"), "\n", W["status.limitations"])}
    p["signatures"] = []
    rd.where = W
    return p, rd

def to_profile(path):
    """Workbook -> draft Profile. Raises WorkbookError listing every problem if the workbook cannot be read cleanly."""
    p, rd = read_workbook(path)
    if rd.errors: raise WorkbookError(f"{len(rd.errors)} problem(s) in {path}", rd.errors)
    return p

# ---------------------------------------------------------------- Profile -> workbook
def from_profile(p):
    if not isinstance(p, dict): raise WorkbookError("the input is not a Profile (a JSON object is expected)")
    wb = build_template()
    s, iss, c, a = p["subject"], p["issuance"], p["claim"], p["assurance"]
    yn = lambda b: None if b is None else ("yes" if b else "no")
    pb = s.get("platform_baseline") or {}
    issuer = iss.get("issuer") or {}
    _kv_write(_sheet(wb, "Identity"), {
        "profile_id": p.get("profile_id"), "subject.institution": s.get("institution"), "subject.deployment_id": s.get("deployment_id"),
        "subject.deployment_version": s.get("deployment_version"), "subject.description": s.get("description"),
        "subject.vendor_products": _join(s.get("vendor_products"), "\n"),
        **{f"subject.platform_baseline.{k}": pb.get(k) for k in ("profile_id", "version", "content_hash")},
        "issuance.owner.name": (iss.get("owner") or {}).get("name"), "issuance.owner.role": (iss.get("owner") or {}).get("role"),
        **{f"issuance.issuer.{k}": issuer.get(k) for k in ("name", "role", "organisation")},
        "issuance.issuer.independent": yn(issuer.get("independent")) if issuer else None,
        **{f"issuance.{k}": iss.get(k) for k in ("evidence_as_of", "valid_from", "valid_until", "issued_at")}})
    ws = _sheet(wb, "Models")
    for i, m in enumerate(s.get("models", [])):
        for j, k in enumerate(("provider", "model", "version", "role"), 1): _put(ws, FIRST_DATA_ROW + i, j, m.get(k))
    au, odd = c["autonomy"], c["odd"]
    vals = {"claim.statement": c.get("statement"), "claim.autonomy.tier": au.get("tier"), "claim.autonomy.tier_basis": au.get("tier_basis"),
            **{f"claim.autonomy.modifiers.{m}": (au.get("modifiers") or {}).get(m) for m in MODS}}
    if au.get("approval_quality"):
        aq = au["approval_quality"]
        vals.update({f"claim.autonomy.approval_quality.{k}": aq.get(k) for k in AQ_KEYS if k not in AQ_BOOL})
        vals.update({f"claim.autonomy.approval_quality.{k}": yn(aq.get(k)) for k in AQ_BOOL})
    ucl = {t["id"]: f'{t["id"]} — {t["label"]}' for t in vocab("use-cases")["terms"]}
    vals.update({"claim.odd.business_line": odd.get("business_line"), "claim.odd.use_case": odd.get("use_case"),
                 "claim.odd.use_case_id": ucl.get(odd.get("use_case_id"), odd.get("use_case_id")),
                 "claim.odd.description": odd.get("description"), "claim.odd.operational_scope": odd.get("operational_scope"),
                 "claim.odd.population": odd.get("population"),
                 "claim.odd.cost_of_failure": odd.get("cost_of_failure"),
                 "claim.odd.jurisdictions": _join(odd.get("jurisdictions"), ","),
                 "claim.odd.data": _join(odd.get("data"), "\n")})
    _kv_write(_sheet(wb, "Claim"), vals)
    ws = _sheet(wb, "Actions"); oos = set(p.get("out_of_scope", {}).get("actions", []))
    acts = c.get("actions") or {}
    for r in range(FIRST_DATA_ROW, FIRST_DATA_ROW + len(ACTIONS)):
        aid = ws.cell(r, 1).value
        ws.cell(r, 4, "permitted" if aid in acts.get("permitted", []) else "prohibited" if aid in acts.get("prohibited", []) else "out of scope" if aid in oos else "not stated")
    ws = _sheet(wb, "Controls"); row_of = {ws.cell(r, 1).value: r for r in range(FIRST_DATA_ROW, FIRST_DATA_ROW + len(CONTROLS))}
    extra = FIRST_DATA_ROW + len(CONTROLS)
    for ctl in c.get("controls", []):
        r = row_of.get(ctl["control_id"])
        if r is None:
            r = extra; extra += 1; _put(ws, r, 1, ctl["control_id"]); _put(ws, r, 2, ctl.get("layer"))
        st = "not applicable" if ctl.get("applicable") is False else {True: "present", False: "absent", None: "not established"}[ctl.get("present")]
        ws.cell(r, 4, st)
        if "configuration" in ctl: _put(ws, r, 5, _cfg_out(ctl["configuration"]))
    ws = _sheet(wb, "Provenance"); r = FIRST_DATA_ROW
    for fid, e in p.get("provenance", {}).items():
        cits = e.get("citations") or [None]
        for i, ci in enumerate(cits):
            _put(ws, r, 1, fid); _put(ws, r, 2, e.get("class"))
            if ci: _put(ws, r, 3, ci["evidence_id"]); _put(ws, r, 4, ci.get("locator")); _put(ws, r, 5, ci.get("verbatim"))
            if i == 0 and e.get("note"): _put(ws, r, 6, e["note"])
            r += 1
    ws = _sheet(wb, "Evidence")
    for i, e in enumerate(p.get("evidence", [])):
        for j, k in enumerate(("id", "path", "content_hash", "artifact_class", "bytes"), 1): _put(ws, FIRST_DATA_ROW + i, j, e.get(k))
    rep = a.get("reproduction") or {}; cp = a.get("comparability") or {}; oo = p.get("out_of_scope") or {}; inv = p.get("invalidation") or {}; st = p.get("status") or {}
    _kv_write(_sheet(wb, "Assurance"), {
        **{f"assurance.axes.{k}": v for k, v in (a.get("axes") or {}).items()},
        **{f"assurance.assessors.{ax}.{k}": ((a.get("assessors") or {}).get(ax) or {}).get(k) for ax in AXES for k in ("role", "organisation", "report")},
        **{f"assurance.fidelity.{k}": (a.get("fidelity") or {}).get(k) for k in ("tools", "data", "policies", "permissions", "response_times", "failure_conditions", "population")},
        "assurance.fidelity.known_differences": _join((a.get("fidelity") or {}).get("known_differences"), "\n"),
        "assurance.test_environment": a.get("test_environment"), "assurance.method": a.get("method"),
        "assurance.comparability.flag": yn(cp.get("flag")), **{f"assurance.comparability.{k}": cp.get(k) for k in ("environment_version", "hidden_set_version", "fidelity_statement")},
        "benchmark": "json:" + json.dumps(p["benchmark"], ensure_ascii=False) if p.get("benchmark") is not None else None,
        **{f"assurance.reproduction.{k}": v for k, v in rep.items()},
        "out_of_scope.statement": oo.get("statement"), "out_of_scope.odd": _join(oo.get("odd"), "\n"),
        "out_of_scope.controls": _join(oo.get("controls"), ","), "out_of_scope.users": _join(oo.get("users"), "\n"),
        "invalidation.monitoring": inv.get("monitoring"),
        "status.exceptions": _join(st.get("exceptions"), "\n"),
        "status.limitations": _join(st.get("limitations"), "\n"), "status.risk_acceptances": _join(st.get("risk_acceptances"), "\n"),
        "vocab_versions": "json:" + json.dumps(p["vocab_versions"], ensure_ascii=False) if p.get("vocab_versions") is not None else None,
        "evidence_manifest": "json:" + json.dumps(p["evidence_manifest"], ensure_ascii=False) if p.get("evidence_manifest") is not None else None})
    ws = _sheet(wb, "Invalidation"); r = FIRST_DATA_ROW
    for eff in ("voids", "partial_retest", "cosmetic"):
        for it in inv.get(eff) or []:
            for j, v in enumerate([eff, it.get("trigger"), it.get("ref"), it.get("description")], 1): _put(ws, r, j, v)
            r += 1
    ws = _sheet(wb, "Results")
    for i, x in enumerate(p.get("results", [])):
        ev = x["evaluation"]
        for j, v in enumerate([x["claim_id"], x["field_id"], x["disposition"], x.get("scenario"), x.get("runs"), _join(x.get("evidence_refs"), ","),
                               ev.get("method"), ev.get("tool"), ev.get("version"), _judge_out(ev.get("judge_model")), _join(ev.get("evidence_basis"), ","), ev.get("review_status"), x.get("note")], 1):
            _put(ws, FIRST_DATA_ROW + i, j, v)
    ws = _sheet(wb, "Floors")
    for i, f in enumerate(p.get("floors", [])):
        for j, v in enumerate([f["id"], f.get("condition"), f.get("status"), _join(f.get("finding_refs"), ","), f.get("axis")], 1): _put(ws, FIRST_DATA_ROW + i, j, v)
    ws = _sheet(wb, "Conflicts"); r = FIRST_DATA_ROW
    for n, cf in enumerate(p.get("conflicts", []), 1):
        for i, ci in enumerate(cf.get("citations") or [None]):
            vals = [n, cf["field_id"], cf["kind"]] + ([cf.get("state"), cf.get("description"), cf.get("resolution_note"), cf.get("resolved_by")] if i == 0 else [None] * 4)
            vals += [ci["evidence_id"], ci.get("locator"), ci.get("verbatim")] if ci else [None] * 3
            for j, v in enumerate(vals, 1): _put(ws, r, j, v)
            r += 1
    ws = _sheet(wb, "Findings")
    for i, f in enumerate(st.get("open_findings", [])):
        for j, v in enumerate([f["id"], f["kind"], f.get("field_id"), f.get("floor_ref"), f.get("claim_id"), f.get("note"), f.get("response")], 1): _put(ws, FIRST_DATA_ROW + i, j, v)
    ws = _sheet(wb, "Gaps")
    for i, gp in enumerate(st.get("accepted_gaps", [])):
        for j, v in enumerate([gp["claim_id"], gp.get("disposition"), gp.get("reason"), gp.get("accepted_by")], 1): _put(ws, FIRST_DATA_ROW + i, j, v)
    return wb

def _sheet(wb, key): return wb[SHEET_NAMES[key]]

def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ("template", "from-json", "to-json") or (sys.argv[1] != "template" and len(sys.argv) < 4):
        print(__doc__); return 2
    cmd = sys.argv[1]
    try:
        if cmd == "template":
            build_template().save(sys.argv[2]); print(f"wrote {sys.argv[2]}"); return 0
        if cmd == "from-json":
            try: p = _read_json(sys.argv[2])
            except (OSError, ValueError) as e: print(f"ERROR   cannot read {sys.argv[2]} as JSON: {e}"); return 1
            from_profile(p).save(sys.argv[3]); print(f"wrote {sys.argv[3]}"); return 0
        p, rd = read_workbook(sys.argv[2])
    except WorkbookError as e:
        print(f"ERROR   {e}"); return 1
    for w in rd.warnings: print(f"WARNING {w}")
    if rd.errors:
        for e in rd.errors: print(f"ERROR   {e}")
        print(f"{len(rd.errors)} problem(s) in the workbook; no JSON written. Fix them and run again."); return 1
    Path(sys.argv[3]).write_text(json.dumps(p, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    rep = check(p)
    where = {k.replace(".", "/"): w for k, w in rd.where.items()}
    where["assurance/headline"] = f"sheet '{SHEET_NAMES['Assurance']}' › headline level (derived once all four axis levels are filled)"
    for i in rep.items:
        msg, loc = i["message"], where.get(i.get("path", ""))
        if i["rule"] == "ARP-001" and loc and ("None is not" in msg or "is too short" in msg): msg = f"missing or too short: {loc}"
        elif loc: msg = f"{loc}: {msg}"
        print(f"{i['severity'].upper():7} {i['rule']:9} {msg}")
    print(f"wrote {sys.argv[3]} (draft) — " + ("CONFORMANT" if not rep.errors else f"NOT CONFORMANT ({len(rep.errors)} error(s))"))
    return 0 if not rep.errors else 1

if __name__ == "__main__":
    sys.exit(main())
