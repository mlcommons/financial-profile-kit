// SPDX-License-Identifier: Apache-2.0
// Runs the Viewer's embedded checker (JS port) against the conformance vectors and checks parity with the
// reference checker: same error rules, same canonical hash (RFC 8785), signatures valid.
// Usage: node templates/viewer/test_viewer.mjs   (from anywhere; Node 18+)
import fs from "node:fs"; import path from "node:path"; import { fileURLToPath } from "node:url";
const here = path.dirname(fileURLToPath(import.meta.url)), kit = path.resolve(here, "../..");
const html = fs.readFileSync(path.join(kit, "templates/ARP Profile Viewer.html"), "utf8");
const start = html.indexOf("const ARP_DATA"), end = html.indexOf("/* ---------- state");
const src = html.slice(start, end).replace("(function(){", "") + "\nreturn {check, checkText, canonicalHash, parseStrict};";
const { check, checkText, canonicalHash } = new Function("document", src)({ querySelector: () => null });
const vdir = path.join(kit, "conformance/vectors"), man = JSON.parse(fs.readFileSync(path.join(vdir, "manifest.json"), "utf8"));
let pass = 0, fail = 0;
const ok = (cond, msg) => { cond ? pass++ : (fail++, console.log("FAIL " + msg)); };
for (const v of man.vectors) {
  // read as bytes and decode strictly, as the reference checker does
  let text; try { text = new TextDecoder("utf-8", { fatal: true }).decode(fs.readFileSync(path.join(vdir, v.file))); } catch (e) { text = null; }
  const { profile, findings } = text === null ? { profile: null, findings: [{ rule: "ARP-001", severity: "error", message: "not UTF-8" }] } : await checkText(text);
  const got = [...new Set(findings.filter(r => r.severity === "error").map(r => r.rule))].sort(), want = [...v.error_rules].sort();
  ok(JSON.stringify(got) === JSON.stringify(want), `${v.file}: expected [${want}] got [${got}]\n   ${findings.filter(r => r.severity === "error").map(r => r.rule + ": " + r.message).join("\n   ")}`);
  if (v.canonical_hash && profile) ok((await canonicalHash(profile)) === v.canonical_hash, `${v.file}: canonical hash differs from the reference checker`);
}
for (const f of ["examples/l1-aml-alert-triage.issued.json", "examples/l2-open-banking.json"]) {
  const p = JSON.parse(fs.readFileSync(path.join(kit, f), "utf8")), h = await canonicalHash(p), R = await check(p);
  const sigOk = (p.signatures || []).every(s => s.signed_hash === h) && !R.some(r => r.rule === "ARP-091" || r.rule === "ARP-019");
  console.log(`${f}: hash ${h.slice(0, 16)}… signatures ${sigOk ? "valid" : "NOT valid"}; errors ${R.filter(r => r.severity === "error").length}`);
  ok(sigOk, `${f}: signatures`);
}
// SPEC §4: several results on one field. A contradicted result followed by a passing one must stay 'contradicted'
// in every summary, and the summary must show that there are other results (Astra review, item 3).
{
  const core = html.slice(start, end).replace("(function(){", ""), ri = html.indexOf("const chip="), re = html.indexOf("/* ---------- edit form");
  const fn = new Function("document", core + "\n" + html.slice(ri, re) + "\nreturn {renderProfile, fieldDispositions, check};");
  const T = fn({ querySelector: () => null });
  const v11 = JSON.parse(fs.readFileSync(path.join(vdir, "valid/v11-failed-then-held-result.json"), "utf8"));
  const agg = T.fieldDispositions(v11.results)["controls.tool.per_case_data_scoping"];
  ok(agg && agg.disposition === "contradicted" && agg.results.length === 2, "v11: aggregated disposition is 'contradicted' with 2 results");
  const F = await T.check(v11); ok(F.some(f => f.rule === "ARP-071" && f.severity === "warning"), "v11: ARP-071 warning reported");
  const el = { innerHTML: "" }; T.renderProfile(el, v11, F);
  const i = el.innerHTML.indexOf("tool.per_case_data_scoping</div>"), row = i < 0 ? "" : el.innerHTML.slice(i, el.innerHTML.indexOf("</tr>", i));
  ok(/c-bad">contradicted</.test(row) && /2 results/.test(row) && !/c-good">held</.test(row), "v11: the controls summary shows 'contradicted' and lists both results, not 'held'");
}
console.log(`${pass} passed, ${fail} failed`); process.exit(fail ? 1 : 0);
