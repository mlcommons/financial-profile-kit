# Interoperability note: Microsoft ASSERT and the Agent Control Specification (non-normative)

Status: non-normative working note for the pilot, written 2026-09-27 and checked against
arp/1.0-rc2. Based on Microsoft's public documentation; no integration has been run. Naming a
product here is not an endorsement by the Working Group or MLCommons.

## ASSERT: a test proposer, not a Validator

ASSERT (MIT) turns written behaviour specifications into a taxonomy of permitted and
prohibited behaviour, generates stratified test cases, runs them against a target, and scores
them with model judges.

How it could serve a Profile:

* **Input.** Generate the ASSERT specification from the Level 1 Profile — the bounded claim,
  prohibited action classes, floors — plus the applicable catalogue controls and independent
  threat scenarios. Do not generate it from the institution's policies alone: tests drawn only
  from what the bank wrote reproduce its omissions. Have an expert review the taxonomy.
* **Output.** Treat generated cases as candidate scenarios. The Validator still supplies the
  deployment adapter, the controlled initial state, authoritative observations (control
  decisions and resulting state) and the disposition criteria.
* **Traces.** A plain callable target may expose only final text; tool calls and routing need
  instrumentation of the host.
* **Judging.** Model-judged scores may flag suspicious behaviour and propose findings. They do
  not decide `actions.*` or `controls.*` claims (ARP-016). Microsoft reports 80–90% agreement
  with human annotators in its own studies; that is not a measured accuracy for banking control
  claims, and aggregate agreement can hide consequential false negatives.
* **Reproducibility.** ASSERT outcomes can vary between runs. Preserve executable cases, initial
  state, versions and evaluator configuration (ARP-017), not just hashes.

## ACS: a candidate configuration and event source

The Agent Control Specification (Agent Governance Toolkit) is marked Draft and pre-release. It
defines eight intervention points (`agent_startup`, `agent_shutdown`, `input`, `pre_model_call`,
`post_model_call`, `pre_tool_call`, `post_tool_call`, `output`). The runtime returns verdicts; the
host must enforce them. Telemetry is optional. Its determinism guarantee holds for identical
manifest, snapshot, mode and dispatcher results; it does not make a model-based classifier
deterministic.

How it could serve a Profile:

* **Builder input.** An ACS policy manifest is evidence for the tool and harness layers, and
  `configuration_derived` only with evidence that it is the deployed manifest.
* **Validator input.** `pre_tool_call` verdicts are the control decisions a Validator judges from,
  provided the host emits them and resulting state shows a `deny` was enforced.
* **Handled is not blocked.** ASSERT's ACS adapter reports cases "handled" (deny, escalate, warn or
  transform) separately from "strongly blocked" (deny or escalate). A warn permits execution and
  never supports a `held` disposition on a prohibited action.
* **Guard scope.** ASSERT's `guard_target` rerun path enforces only the input and output points.
  Blocking an output does not show that an earlier tool call (a transfer, a disclosure) was
  prevented. Tool-boundary testing needs a full ACS host that wraps tool calls.

## Proposed pilot experiment

1. One deployment, a small set of material claims.
2. Expert-authored tests alongside ASSERT-generated tests.
3. Both run in a controlled environment, capturing control decisions and resulting state.
4. Compare model judgments, deterministic checks and expert review.
5. Measure added coverage, missed violations, false positives and total effort.

Sources: github.com/responsibleai/ASSERT (docs/targets/callable.md, docs/guides/securing-agents-with-acs.md,
docs/concepts.md); github.com/microsoft/agent-governance-toolkit (policy-engine/spec/SPECIFICATION.md);
commandline.microsoft.com/assert-written-intent-executable-evals/.
