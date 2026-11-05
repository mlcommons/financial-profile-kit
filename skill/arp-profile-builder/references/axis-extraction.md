# Filling the four axes

## 1. Autonomy tier (`autonomy.tier`)

| Tier | Choose it when |
|---|---|
| T0 | No action capability; read or suggest only |
| T1 | A person invokes each action; no multi-step chaining |
| T2 | Multi-step task; a person approves every material action **and** approval records show substantive review |
| T3 | Whole task in envelope; escalates on uncertainty or hazard triggers; or T2 by configuration with reflexive approval in the records |
| T4 | No contemporaneous approval; out-of-envelope actions blocked in software; tested safe state |
| U  | Envelope, fallback or action boundaries unspecified. Record an `unprofiled` open finding |

Approval quality (`autonomy.approval_quality`) from sample approval records: sample size,
median seconds to approve, edit rate, rejection rate, whether the approver saw the specific
resource. Consistently reflexive approval (seconds-long, no edits, no rejections) means
assessment `reflexive` and tier T3, whatever the configuration says. If there are no records,
assessment is `not_assessed`, and a T2 claim rests on configuration alone: say so in the note.

**Configuration that contradicts the tier definition.** T2 requires that the approver is shown
the specific resource affected. If configuration or a console export shows the resource is not
shown, T2 cannot be asserted even when every action needs approval: record **T3** with
`tier_basis: asserted`, and a conflict with any document that claims T2.

**`not_assessed` approval quality.** Set `sample_size` to the number of usable records (often 0)
and the rate fields to null. Its provenance is `absent`, with a note naming the records that would
establish it. Values from simulated records go in the note only.

Record all six modifiers: data authority, reversibility profile, customer and market impact,
stack composability (`predefined` or `dynamic`), accountability, population scope.

## 2. Operational design domain (`odd.*`)

Business line from `spec/vocab/business-lines.json`; use case in the institution's words;
population, data sources, jurisdictions, cost of failure. Software caps that bound the domain
(data windows, account scopes) are configuration evidence for the ODD.

## 3. Action classes (`actions.A1`–`actions.A12`)

Map every registered tool and every write scope to a class:

| Class | Typical tools or scopes |
|---|---|
| A1 Read / retrieve | get_*, search, query, read scopes |
| A2 Analyse / compute | scoring, simulation, in-memory reconciliation |
| A3 Draft for a person | draft_*, generate narrative |
| A4 Recommend / route | recommend, escalate, prioritise |
| A5 Write internal | add_note, create_ticket, open PR, CRM update |
| A6 Submit / commit internal | close_case, merge, commit |
| A7 External communication | send_email, notify_customer, transmit to third party |
| A8 Transact, bounded | place_hold, block_card, cancellable trade |
| A9 Move funds | initiate_payment, release_wire |
| A10 Regulatory filing | file_sar, submit_return |
| A11 Access and infrastructure change | grant_permission, deploy, change branch protection |
| A12 Delegate / spawn | create_agent, delegate, grant credential |

A class is **permitted** if any tool or scope in it is available; **prohibited** if policy
forbids it or no tool exists for it (cite the registry for "no tool in class"). A scope that
enables a class the policy prohibits is a conflict (e.g. policy says no case closure, the
service account holds `cases:write`).

## 4. Controls (`controls.*`)

For each control the documents claim or the configuration shows, find the catalogue id.
`present` is `true` (evidence shows it), `false` (evidence shows it missing or off), or `null`
(claimed but nothing can establish it; provenance `absent`). Record configuration values
(caps, windows, fail-open or fail-closed) in `configuration`. A control that fails open is a
configuration finding.

## 5. The bounded claim

"On the evidence supplied, <deployment> operates at autonomy tier <T> within <ODD>, may
<permitted classes>, is prohibited from <prohibited classes>, and operates under <key
controls>. <n> fields could not be established and <m> conflicts remain open. This is a
Level 1 Asserted Profile: nothing in it has been tested."
