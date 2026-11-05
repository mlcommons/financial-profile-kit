// SPDX-License-Identifier: Apache-2.0
// Checks that the Supervisory dashboard demo's feed checks (JS) agree with regulator/arp_feed.py (Python) on the sample feed and on
// deliberately broken feeds, plus console-only safeguards (pull origin, key-register loading, escaping of firm-supplied data).
//   Usage: node regulator/console/test_console.mjs
// The rendering (XSS) tests need jsdom: `npm install jsdom@24` next to the kit, or set ARP_JSDOM=/path/to/node_modules/jsdom/lib/api.js.
import fs from "node:fs"; import os from "node:os"; import path from "node:path"; import crypto from "node:crypto";
import { execFileSync } from "node:child_process"; import { fileURLToPath, pathToFileURL } from "node:url";
const here = path.dirname(fileURLToPath(import.meta.url)), kit = path.resolve(here, "../.."), feed = path.join(kit, "regulator/sample-feed");
// the Python reference: $PYTHON if set, else the first of the kit's .venv, python3/py, python that has the requirements
function findPython() {
  const cands = [process.env.PYTHON, path.join(kit, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python"),
                 process.platform === "win32" ? "py" : "python3", "python"].filter(Boolean);
  for (const c of cands) { try { execFileSync(c, ["-c", "import jsonschema, cryptography, openpyxl"], { stdio: "ignore" }); return c; } catch (_) {} }
  console.log(`cannot run the Python reference checker: none of ${cands.join(", ")} has jsonschema, cryptography and openpyxl.\n` +
              "Install them (python3 -m pip install -r requirements.txt) or set PYTHON=/path/to/python, then run this test again.");
  process.exit(3);
}
const PY = findPython();
const htmlPath = path.join(kit, "regulator/ARP Supervisory Dashboard Demo.html"), html = fs.readFileSync(htmlPath, "utf8");
const core = html.slice(html.indexOf("const ARP_DATA"), html.indexOf("const chip=")).replace("(function(){", "");
const checks = html.slice(html.indexOf("/* ---------- the feed checks"), html.indexOf("/* ---------- store ---------- */"));
const { checkSnapshot, checkFeed, canonicalHash, classifyFile, acceptPulled, parseStrict, canon, SNAP_CONTEXT, trustOf } =
  new Function("document", core + checks + "\nreturn {checkSnapshot, checkFeed, canonicalHash, classifyFile, acceptPulled, parseStrict, canon, SNAP_CONTEXT, trustOf};")({ querySelector: () => null });
const C0 = { trustOf };
const J = f => JSON.parse(fs.readFileSync(f, "utf8")), clone = o => JSON.parse(JSON.stringify(o));
const REG = J(path.join(feed, "registry.json")), registry = Object.fromEntries(REG.firms.map(f => [f.firm_id, f]));
const objects = new Map(); for (const f of fs.readdirSync(path.join(feed, "objects"))) { const p = J(path.join(feed, "objects", f)); objects.set(await canonicalHash(p), p); }
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "arpfeed-"));
const errRules = fs_ => [...new Set(fs_.filter(f => (f.severity || f[1]) === "error").map(f => f.rule || f[0]))].sort();
function runPy(args) { try { return execFileSync(PY, [path.join(kit, "regulator/arp_feed.py"), ...args], { encoding: "utf8" }); } catch (e) { return e.stdout || ""; } }
function regArgs(reg) { if (reg === null) return ["--no-register"]; const f = path.join(tmp, "reg.json"); fs.writeFileSync(f, JSON.stringify({ firms: Object.values(reg) })); return ["--registry", f]; }
function pyCheck(snapOrText, prev, reg = registry, warnRule) {
  const a = path.join(tmp, "s.json"); fs.writeFileSync(a, typeof snapOrText === "string" ? snapOrText : JSON.stringify(snapOrText));
  const args = ["check", a, "--objects", path.join(feed, "objects"), ...regArgs(reg)];
  if (prev) { const b = path.join(tmp, "p.json"); fs.writeFileSync(b, JSON.stringify(prev)); args.push("--previous", b); }
  const out = runPy(args), lines = out.split("\n");
  return { errors: [...new Set(lines.filter(l => l.startsWith("ERROR")).map(l => l.split(/\s+/)[1]))].sort(), text: out };
}
function pyChain(snapsByFile, reg = registry) {
  const d = fs.mkdtempSync(path.join(tmp, "chain-")); for (const [n, s] of Object.entries(snapsByFile)) fs.writeFileSync(path.join(d, n), JSON.stringify(s));
  return JSON.parse(runPy(["chain", d, "--json", "--objects", path.join(feed, "objects"), ...regArgs(reg)]));
}
let pass = 0, fail = 0, skipped = 0;
const ok = (name, cond, detail = "") => { cond ? pass++ : fail++; console.log(`${cond ? "pass" : "FAIL"}  ${name}${detail ? ": " + detail : ""}`); };
async function expect(name, snap, prev, want, reg = registry) {
  const a = errRules(await checkSnapshot(snap, prev, objects, reg)), b = pyCheck(snap, prev, reg).errors;
  ok(name, JSON.stringify(a) === JSON.stringify(want) && JSON.stringify(b) === JSON.stringify(want), `console [${a}] python [${b}] expected [${want}]`);
}
async function expectChain(name, files, want, reg = registry) { // files: {name: snapshot}; want: {name: [rules]}
  const js = await checkFeed(Object.values(files), objects, reg), byObj = new Map(Object.entries(files).map(([n, s]) => [s, n]));
  const a = Object.fromEntries(js.map(([s, f]) => [byObj.get(s), errRules(f)])), py = pyChain(files, reg);
  const b = Object.fromEntries(py.map(r => [r.file, errRules(r.findings)]));
  const same = n => JSON.stringify(a[n]) === JSON.stringify(want[n]) && JSON.stringify(b[n]) === JSON.stringify(want[n]);
  ok(name, Object.keys(want).every(same), Object.keys(want).map(n => `${n}: console [${a[n]}] python [${b[n]}] expected [${want[n]}]`).join("; "));
}
// keys: the sample's DEMO-ONLY keys are derived from a public seed (regulator/gen_sample.py), so tests can re-sign with them
const demoKey = fid => crypto.createPrivateKey({ key: Buffer.concat([Buffer.from("302e020100300506032b657004220420", "hex"), crypto.createHash("sha256").update("ARP DEMO-ONLY sample key " + fid).digest()]), format: "der", type: "pkcs8" });
const pubOf = k => crypto.createPublicKey(k).export({ format: "der", type: "spki" }).subarray(-32).toString("base64");
async function resign(snap, priv) { const out = clone(snap); out.signatures = []; const h = await canonicalHash(out);
  const sig = { role: "institution", name: "Test Signer (fictional)", alg: "ed25519", public_key: pubOf(priv), signed_hash: h };
  sig.value = crypto.sign(null, Buffer.from(canon({ context: SNAP_CONTEXT, alg: sig.alg, role: sig.role, name: sig.name, public_key: sig.public_key, signed_hash: h }), "utf8"), priv).toString("base64");
  out.signatures.push(sig); return out; }
const other = crypto.generateKeyPairSync("ed25519").privateKey;
const firmDir = id => path.join(feed, id), snapsOf = id => fs.readdirSync(firmDir(id)).sort().map(f => [f, J(path.join(firmDir(id), f))]);

// 1. the sample feed, firm by firm, as a chain: only the planted problem (a deployment that vanished) is an error
for (const d of fs.readdirSync(feed).filter(d => d.startsWith("DEMO-FIRM-")).sort()) {
  const files = Object.fromEntries(snapsOf(d)), want = Object.fromEntries(Object.keys(files).map(n => [n, d === "DEMO-FIRM-05" && n === "inventory-4.json" ? ["INV-031"] : []]));
  await expectChain(`sample ${d}`, files, want);
}
// 2. broken snapshots
const s = n => J(path.join(firmDir("DEMO-FIRM-02"), `inventory-${n}.json`)), k2 = demoKey("DEMO-FIRM-02");
let t = clone(s(3)); t.records[0].record.agent_name += " (edited)"; await expect("record edited after signing", t, s(2), ["INV-040"]);
await expect("history rewritten (next snapshot no longer chains)", s(4), t, ["INV-030"]);
await expect("signed with an unregistered key", await resign(s(3), other), s(2), ["INV-040"]);
t = clone(s(3)); t.records.push(clone(t.records[0])); await expect("duplicate deployment", await resign(t, k2), s(2), ["INV-011"]);
t = clone(s(3)); t.records.splice(2, 1); await expect("deployment silently dropped", await resign(t, k2), s(2), ["INV-031"]);
const withDoc = snap => snap.records.find(e => e.profile && objects.has(e.profile.sha256));
t = clone(s(4)); withDoc(t).record.profile_level = "L3"; await expect("record contradicts its Profile commitment", await resign(t, k2), s(3), ["INV-020"]);
t = clone(s(4)); { const e = withDoc(t); e.record.profile_level = "L3"; e.profile.headline = 3; } await expect("commitment misstates the delivered Profile", await resign(t, k2), s(3), ["INV-021"]);
t = clone(s(4)); withDoc(t).profile.valid_until = "2030-01-01"; await expect("commitment extends the Profile's expiry", await resign(t, k2), s(3), ["INV-021"]);
// a commitment whose hash is wrong for a Profile the supervisor holds (by profile_id) is an error, and the record is still
// checked against the held Profile (W8, D1: before, a wrong hash hid INV-023)
t = clone(s(4)); withDoc(t).profile.sha256 = "sha256:" + "1".repeat(64); await expect("wrong commitment hash for a held Profile", await resign(t, k2), s(3), ["INV-021"]);
{ t = clone(s(4)); const e = withDoc(t); e.profile.sha256 = "sha256:" + "1".repeat(64); e.record.autonomy_tier = "T4";
  e.record.prohibited_actions = e.record.prohibited_actions.filter(a => a !== "A12"); e.record.permitted_actions = [...e.record.permitted_actions, "A12"];
  const u = await resign(t, k2); await expect("wrong commitment hash with tier T4 and A12 permitted: INV-021 and INV-023 (D1 repro)", u, s(3), ["INV-021", "INV-023"]);
  ok("D1 repro is quarantined (python and console)", !C0.trustOf(await checkSnapshot(u, s(3), objects, registry)).trusted && /QUARANTINED/.test(pyCheck(u, s(3)).text)); }
{ t = clone(s(4)); const e = withDoc(t); e.profile.sha256 = "sha256:" + "0".repeat(64); e.profile.profile_id = e.record.full_profile_ref = "example.not-delivered.v1.L1";
  await expect("commitment to a Profile not held under that hash or id (allowed, not available)", await resign(t, k2), s(3), []); }
await expect("skipped sequence", s(4), s(2), ["INV-030"]);
// 2b. verification fixes (W5): the signature covers the signer's name and role (L4); strict dates and patterns (L2)
t = clone(s(3)); t.signatures[0].name = "Someone Else (fictional)"; await expect("signer name edited after signing", t, s(2), ["INV-040"]);
t = clone(s(3)); t.signatures[0].role = "regulator"; await expect("signer role edited after signing", t, s(2), ["INV-001"]);
t = clone(s(3)); t.snapshot.as_of += "\n"; await expect("as_of with a trailing newline", await resign(t, k2), s(2), ["INV-001"]);
t = clone(s(3)); t.records[0].record.inventory_ref += "\n"; await expect("inventory_ref with a trailing newline", await resign(t, k2), s(2), ["INV-001"]);
t = clone(s(3)); t.snapshot.as_of = "2026-99-99"; await expect("as_of that is not a calendar date", await resign(t, k2), s(2), ["INV-001"]);
t = clone(s(3)); t.records[0].record.last_reviewed = "2026-02-30"; await expect("last_reviewed that is not a calendar date", await resign(t, k2), s(2), ["INV-001"]);
// 3. a committed Profile must be about this firm and this deployment (B-08)
{ const n4 = J(path.join(firmDir("DEMO-FIRM-01"), "inventory-4.json")), eb = withDoc(s(4)), e = n4.records.find(x => x.record.deployment_status === "production" && x.record.profile_level === "none");
  e.record.profile_level = `L${eb.profile.headline}`; e.record.full_profile_ref = eb.profile.profile_id; e.profile = clone(eb.profile);
  await expect("firm commits to another firm's public Profile", await resign(n4, demoKey("DEMO-FIRM-01")), J(path.join(firmDir("DEMO-FIRM-01"), "inventory-3.json")), ["INV-021", "INV-023"]); }
// 3b. an inventory record must agree with its full Profile, or declare the divergence (INV-023; Astra review, item 3)
t = clone(s(4)); withDoc(t).record.autonomy_tier = "T4"; await expect("record reports tier T4, its full Profile says T2", await resign(t, k2), s(3), ["INV-023"]);
t = clone(s(4)); withDoc(t).record.controls["tool.transaction_caps"] = "tested_held"; await expect("record reports a control status its Profile does not support", await resign(t, k2), s(3), ["INV-023"]);
{ t = clone(s(4)); const e = withDoc(t); e.record.autonomy_tier = "T4"; e.record.divergence = { fields: ["autonomy_tier"], as_of: t.snapshot.as_of, reason: "Tier raised on 30 Sep; reissue in progress" };
  const u = await resign(t, k2), a = await checkSnapshot(u, s(3), objects, registry), p = pyCheck(u, s(3));
  ok("declared divergence: a labelled warning, not an error", !errRules(a).length && !p.errors.length && a.some(f => f.rule === "INV-023" && f.severity === "warning") && /WARNING INV-023/.test(p.text) && /TRUSTED/.test(p.text)); }
{ t = clone(s(4)); const e = withDoc(t); e.record.autonomy_tier = "T4"; e.record.divergence = { fields: ["autonomy_tier"], as_of: "2027-01-01", reason: "x" };
  await expect("divergence dated after the snapshot", await resign(t, k2), s(3), ["INV-023"]); }
// 4. signer trust (B-04)
t = clone(s(3)); t.institution.firm_id = "DEMO-FIRM-99"; await expect("firm not in the key register", await resign(t, other), null, ["INV-040"]);
{ const r = await checkSnapshot(s(3), s(2), objects, null), p = pyCheck(s(3), s(2), null);
  ok("no key register: signer reported as unverified, not trusted", !errRules(r).length && !p.errors.length && r.some(f => /UNVERIFIED SIGNER/.test(f.message)) && /UNVERIFIED SIGNER/.test(p.text)); }
await expect("no key register: history re-signed with a new key", await resign(s(3), other), s(2), ["INV-040"], null);
{ const rot = clone(registry); rot["DEMO-FIRM-02"] = { ...rot["DEMO-FIRM-02"], public_key: pubOf(other), retired_keys: [{ public_key: registry["DEMO-FIRM-02"].public_key, last_sequence: 3 }] };
  await expect("key rotation: old key still valid up to its last sequence", s(3), s(2), [], rot);
  await expect("key rotation: old key refused after its last sequence", s(4), s(3), ["INV-040"], rot); }
// 5. forks and gaps in a chain (B-05)
{ const f = Object.fromEntries(snapsOf("DEMO-FIRM-02")); const alt = clone(f["inventory-3.json"]); alt.records[0].record.agent_name += " (replacement)";
  f["inventory-3b.json"] = await resign(alt, k2);
  await expectChain("fork: two different snapshots claim the same sequence", f, { "inventory-1.json": [], "inventory-2.json": [], "inventory-3.json": ["INV-030"], "inventory-3b.json": ["INV-030"], "inventory-4.json": ["INV-030"] });
  ok("fork: snapshots after the fork are quarantined until it is resolved (W8, D5c)", pyChain(f).find(r => r.file === "inventory-4.json").trusted === false);
  const g = Object.fromEntries(snapsOf("DEMO-FIRM-02")); delete g["inventory-2.json"];
  await expectChain("gap: a snapshot is missing", g, { "inventory-1.json": [], "inventory-3.json": ["INV-030"], "inventory-4.json": [] });
  const h = Object.fromEntries(snapsOf("DEMO-FIRM-02")); h["inventory-x4.json"] = J(path.join(firmDir("DEMO-FIRM-01"), "inventory-4.json"));
  await expectChain("another firm's snapshot in the folder does not taint this firm's chain (L6)", h,
    { "inventory-1.json": [], "inventory-2.json": [], "inventory-3.json": [], "inventory-4.json": [], "inventory-x4.json": ["INV-030"] }); }
// a quarantined snapshot in the middle of a chain: the next one is checked against it and stays trusted (W8, D5c)
const midQ = async () => { const f = Object.fromEntries(snapsOf("DEMO-FIRM-02")), t3 = clone(f["inventory-3.json"]); t3.records.push(clone(t3.records[0]));
  f["inventory-3.json"] = await resign(t3, k2); const t4 = clone(f["inventory-4.json"]); t4.snapshot.previous_hash = await canonicalHash(f["inventory-3.json"]);
  f["inventory-4.json"] = await resign(t4, k2); return f; };
await expectChain("quarantined snapshot in the middle of a chain", await midQ(), { "inventory-2.json": [], "inventory-3.json": ["INV-011"], "inventory-4.json": [] });
// 5b. quarantine (Astra review, item 1): arp_feed.py reports trusted / quarantined per snapshot, as the console does
{ const f = Object.fromEntries(snapsOf("DEMO-FIRM-02")); const tam = clone(f["inventory-4.json"]); tam.records[0].record.agent_name += " (edited)"; f["inventory-4.json"] = tam;
  const py = Object.fromEntries(pyChain(f).map(r => [r.file, r.trusted])), js = await checkFeed(Object.values(f), objects, registry);
  const jsT = Object.fromEntries(js.map(([sn, fi]) => [Object.keys(f).find(n => f[n] === sn), C0.trustOf(fi).trusted]));
  ok("tampered snapshot is quarantined, earlier ones stay trusted (python and console)", JSON.stringify(py) === JSON.stringify(jsT) && py["inventory-4.json"] === false && py["inventory-3.json"] === true, `python ${JSON.stringify(py)} console ${JSON.stringify(jsT)}`); }
{ const r = await checkSnapshot(s(3), s(2), objects, null);
  ok("no key register: snapshot is not trusted (unverified signer)", !C0.trustOf(r).trusted && /QUARANTINED/.test(pyCheck(s(3), s(2), null).text)); }
// 6. malformed input (B-12, B-13): findings, never a crash
{ const txt = JSON.stringify(s(3)).replace('"attestation":{', '"attestation":{"statement":"forged first value of a duplicated key",'); let jsRule;
  try { await checkSnapshot(parseStrict(txt), null, objects, registry); jsRule = "parsed"; } catch (e) { jsRule = /duplicate key/.test(e.message) ? "INV-001" : "other"; }
  const p = pyCheck(txt, null); ok("duplicate JSON key is refused", jsRule === "INV-001" && JSON.stringify(p.errors) === '["INV-001"]', `console ${jsRule} python [${p.errors}]`); }
for (const [n, bad] of [["array", []], ["sequence is markup", { ...s(3), snapshot: { ...s(3).snapshot, sequence: '5<img src=x onerror="alert(1)">' } }], ["null", null]]) {
  const a = errRules(await checkSnapshot(bad, null, objects, registry)), b = pyCheck(bad, null).errors;
  ok(`malformed snapshot (${n}) gives INV-001`, a.includes("INV-001") && b.includes("INV-001"), `console [${a}] python [${b}]`); }
// 7. console-only safeguards
ok("pull: snapshot from another origin is refused", !!acceptPulled("DEMO-FIRM-01", "https://feed.a.example/arp/v0", "https://evil.example/arp/v0/inventory/3"));
ok("pull: snapshot naming another firm is refused", !!acceptPulled("DEMO-FIRM-01", "https://feed.a.example/arp/v0", "inventory/3", s(3)));
ok("pull: the firm's own snapshot from its own origin is accepted", acceptPulled("DEMO-FIRM-02", "https://feed.a.example/arp/v0", "inventory/3", s(3)) === null);
ok("snapshot picker never accepts a key register", classifyFile(REG) === "register" && classifyFile(s(1)) === "snapshot" && classifyFile([]) === "unknown");
// 8. rendering: firm-supplied text is never interpreted as markup (B-01)
let JSDOM = null; for (const spec of [process.env.ARP_JSDOM, "jsdom"].filter(Boolean)) { try { JSDOM = (await import(spec.includes("/") ? pathToFileURL(spec).href : spec)).JSDOM; break; } catch (_) {} }
if (!JSDOM) { skipped++; console.log("skip  rendering tests: jsdom not installed (npm install jsdom@24, or set ARP_JSDOM)"); }
else {
  const P = id => `<img id="pwn_${id}" src="x" onerror="window.__pwned=(window.__pwned||0)+1">`;
  const dom = new JSDOM(html, { runScripts: "dangerously", pretendToBeVisual: true, url: "https://console.example/", beforeParse(w) {
    Object.defineProperty(w, "crypto", { value: globalThis.crypto }); w.TextEncoder = TextEncoder; w.fetch = async () => { throw new Error("offline"); }; } });
  const w = dom.window, C = w.ARPConsole; await C.ready; await C.loadSample();
  // payload firms are registered and start their own chain (sequence 1, no Profile commitments), so their snapshots are
  // trusted and rendered in every view; an unregistered copy (EVIL-02) is quarantined and appears only in the Feed view
  const seq1 = x => { x.snapshot.sequence = 1; x.snapshot.previous_hash = null; x.records.forEach(e => { delete e.profile; e.record.profile_level = "none"; delete e.record.full_profile_ref; delete e.record.divergence; }); return x; };
  C.setRegister({ firms: [...REG.firms, { firm_id: "EVIL-01", name: "Evil Bank " + P("reg"), peer_group: "Test " + P("peer"), public_key: pubOf(k2) }, { firm_id: "PIPE|01", name: "Pipe Bank", peer_group: "Test", public_key: pubOf(k2) }] }, "test register " + P("regname"));
  const evil = seq1(clone(s(4))); evil.institution.name = "Evil Bank " + P("inst"); evil.institution.firm_id = "EVIL-01";
  evil.records.forEach((e, i) => { e.record.institution = evil.institution.name; if (i < 3) { e.record.agent_name = P("name" + i); e.record.use_case = P("uc" + i); e.record.models = P("model" + i); e.record.vendor_or_platform = P("vendor" + i); e.record.accountable_owner_role = P("owner" + i); } });
  evil.attestation.name = P("att"); evil.snapshot.change_note = P("note");
  const broken = clone(s(4)); broken.snapshot.sequence = "9" + P("seq"); broken.snapshot.as_of = '2026-12-30">' + P("asof"); broken.snapshot.produced_at = P("prod");
  broken.records[0].profile = { ...(broken.records[0].profile || {}), headline: P("headline") };
  const evil2 = clone(evil); evil2.institution.firm_id = "EVIL-02"; evil2.records.forEach(e => e.record.agent_name += P("q"));
  await C.addSnapshot(await resign(evil, k2)); await C.addSnapshot(await resign(evil2, other)); await C.addSnapshot(broken); await C.recheckAll();
  const tabs = ["overview", "inventory", "explore", "trends", "outliers", "changes", "feed"], seen = []; let rendered = false;
  for (const scope of ["all", "EVIL-01", "EVIL-02", "DEMO-FIRM-02"]) for (const tab of tabs) { C.S.scope = scope; C.S.tab = tab; C.S.drill = null; C.render();
    const html_ = w.document.body.innerHTML; if (html_.includes("&lt;img id=\"pwn_name0")) rendered = true; if (w.document.querySelector('[id^="pwn_"]')) seen.push(`${scope}/${tab}`); if (/<img id="pwn_/.test(html_)) seen.push(`${scope}/${tab} (markup)`); }
  for (const x of C.rowsAt(C.S.date).filter(x => x.firm.id === "EVIL-01").slice(0, 4)) { C.S.drill = x.key; C.render(); if (w.document.querySelector('[id^="pwn_"]')) seen.push("drill " + x.key); }
  await new Promise(r => setTimeout(r, 50));
  ok("firm-supplied text renders as text in every view (no injected elements)", rendered && !seen.length && !w.__pwned, rendered ? seen.join(", ") : "the payload snapshot was never rendered");
  const feedRow = (() => { C.S.drill = null; C.S.tab = "feed"; C.render(); return w.document.body.textContent.includes("not shown in any view"); })();
  ok("a snapshot that fails INV-001 is listed with its findings but not used in any view", feedRow && !C.rowsAt(C.S.date).some(x => x.snap === broken));
  ok("a quarantined snapshot (unregistered signer) never reaches the views", !C.rowsAt(C.S.date).some(x => x.firm.id === "EVIL-02"));
  { const pipe = seq1(clone(s(4))); pipe.institution.firm_id = "PIPE|01"; await C.addSnapshot(await resign(pipe, k2)); await C.recheckAll(); let err = null, shown = 0;
    const rows = C.rowsAt(C.S.date).filter(x => x.firm.id === "PIPE|01").slice(0, 3);
    for (const x of rows) { C.S.scope = "all"; C.S.tab = "inventory"; C.S.drill = x.key; try { C.render(); if (w.document.getElementById("main").textContent.includes(x.r.inventory_ref)) shown++; } catch (e) { err = e; } }
    ok("drill-down works for a firm id containing '|' (L1)", rows.length > 0 && !err && shown === rows.length, err ? String(err) : `${shown}/${rows.length} shown`); C.S.drill = null; }
  // quarantine calculations (Astra review, item 1): edit a record in a signed snapshot without re-signing it; the firm's
  // position falls back to its last trusted snapshot and the tampered records leave every total
  await C.loadSample(); C.S.scope = "all"; C.S.tab = "overview"; C.render(); const D0 = C.S.date, base = C.rowsAt(D0);
  { const objs = fs.readdirSync(path.join(feed, "objects")).map(f => J(path.join(feed, "objects", f)));
    const all = fs.readdirSync(feed).filter(d => d.startsWith("DEMO-FIRM-")).sort().flatMap(d => snapsOf(d).map(([n, x]) => [d, n, x]));
    const tam = clone(s(4)); tam.records[0].record.agent_name += " (edited)";
    C.clearAll(); C.setRegister(REG, "sample register (test)"); for (const o of objs) await C.addObject(o);
    for (const [d, n, x] of all) await C.addSnapshot(d === "DEMO-FIRM-02" && n === "inventory-4.json" ? tam : x);
    await C.recheckAll(); C.S.tab = "overview"; C.render();
    const rows = C.rowsAt(C.S.date), f2 = rows.filter(x => x.firm.id === "DEMO-FIRM-02");
    const prodOf = sn => sn.records.filter(e => e.record.deployment_status === "production").length;
    ok("tampered snapshot: never in any row", !rows.some(x => / \(edited\)$/.test(x.r.agent_name)));
    ok("tampered snapshot: the firm's position falls back to its last trusted snapshot", f2.length > 0 && f2.every(x => x.snap.snapshot.sequence === 3), `sequences ${[...new Set(f2.map(x => x.snap.snapshot.sequence))]}`);
    ok("tampered snapshot: portfolio total = baseline − snapshot 4 + snapshot 3", C.S.date === D0 && rows.length === base.length - s(4).records.length + s(3).records.length, `${rows.length} vs ${base.length} − ${s(4).records.length} + ${s(3).records.length}`);
    ok("tampered snapshot: firm metrics and peer tests use snapshot 3", (C.firmMetrics(D0).get("DEMO-FIRM-02") || {}).n === prodOf(s(3)));
    ok("tampered snapshot: overview and banner say it is quarantined", /Quarantined snapshot/.test(w.document.getElementById("main").textContent) && !w.document.getElementById("trust-banner").hidden);
    C.S.tab = "feed"; C.render(); ok("tampered snapshot: listed in the Feed view as quarantined", /Quarantined · not shown in any view/.test(w.document.getElementById("main").textContent)); }
  // W8, D3: the sample's planted autonomy creep is in a trusted snapshot and is visible at the default date
  await C.loadSample(); C.S.scope = "all"; C.S.tab = "overview"; C.render();
  { const lum = C.rowsAt(C.S.date).filter(x => x.firm.id === "DEMO-FIRM-03"), kinds = lum.length ? C.changes(lum[0].prevSnap, lum[0].snap).map(c => c.kind) : [];
    ok("sample: Lumen's snapshot 4 is trusted and current at the default date", lum.length > 0 && lum.every(x => x.snap.snapshot.sequence === 4) && !C.quarantined().some(q => q.f.id === "DEMO-FIRM-03"));
    ok("sample: the autonomy-creep flag fires at the default date", lum.some(x => x.flags.some(fl => fl.id === "autonomy_creep")));
    ok("sample: Lumen's changes include tier increases, reduced approval, additions and moves to production", ["tier_up", "approval_down", "added", "to_production"].every(k => kinds.includes(k)), kinds.join(","));
    C.S.scope = "DEMO-FIRM-03"; C.S.tab = "changes"; C.render(); const txt = w.document.getElementById("main").textContent;
    ok("sample: the Changes view shows the creep", /Autonomy tier increased/.test(txt) && /Human approval reduced/.test(txt));
    ok("sample: the vanished deployment (INV-031) is Meridian's snapshot 4, the only quarantined sample snapshot", C.quarantined().length === 1 && C.quarantined()[0].f.id === "DEMO-FIRM-05" && C.quarantined()[0].s.snapshot.sequence === 4,
       JSON.stringify(C.quarantined().map(q => [q.f.id, q.s.snapshot.sequence]))); C.S.scope = "all"; }
  // W8, D5a: an unregistered firm's self-declared name is never shown (it is unverified); it is named by its firm id
  { const self = seq1(clone(s(4))); self.institution = { ...self.institution, firm_id: "EVIL-03", name: "Selfnamed Bank" }; self.records.forEach(e => e.record.institution = "Selfnamed Bank");
    await C.addSnapshot(await resign(self, other)); await C.recheckAll(); const leaks = [];
    for (const scope of ["all", "EVIL-03"]) for (const tab of tabs.filter(x => x !== "feed")) { C.S.scope = scope; C.S.tab = tab; C.S.drill = null; C.render();
      if (w.document.body.textContent.replace(w.document.getElementById("toast")?.textContent || "", "").includes("Selfnamed")) leaks.push(`${scope}/${tab}`); }
    const picker = w.document.getElementById("f-scope").textContent;
    ok("unregistered firm: its self-declared name is not in the scope picker or any view but Feed", !picker.includes("Selfnamed") && /Unregistered firm \(EVIL-03\)/.test(picker) && !leaks.length, `picker: ${picker.includes("Selfnamed")}; ${leaks.join(", ")}`);
    C.S.scope = "all"; }
  // W8, D5b: files opened with the picker that are malformed, have a duplicate key or are not ARP documents are listed with INV-001
  { C.clearAll(); const mk = (name, text) => ({ name, text: async () => text });
    await C.openFiles([mk("broken.json", "{not json"), mk("dupkey.json", '{"a":1,"a":2}'), mk("other.json", '{"hello":"world"}'), mk("good.json", JSON.stringify(s(1)))]);
    C.S.tab = "feed"; C.render(); const txt = w.document.getElementById("main").textContent;
    ok("opened files that cannot be used are listed in the Feed view with INV-001", ["broken.json", "dupkey.json", "other.json"].every(n => txt.includes(n)) && /Files that could not be used/.test(txt) && /INV-001/.test(txt) && /duplicate key/.test(txt) && !txt.includes("good.json"));
    C.clearAll(); await C.openFiles([mk("only-bad.json", "[1,")]); C.render();
    ok("a session with only unusable files opens on the Feed view", C.S.tab === "feed" && w.document.getElementById("main").textContent.includes("only-bad.json")); }
  // W8, D5c: after a quarantined snapshot, changes are compared with the last trusted one and labelled; after a fork, nothing is used
  { const objs = fs.readdirSync(path.join(feed, "objects")).map(f => J(path.join(feed, "objects", f)));
    const load = async files => { C.clearAll(); C.setRegister(REG, "sample register (test)"); for (const o of objs) await C.addObject(o); for (const x of Object.values(files)) await C.addSnapshot(x); await C.recheckAll(); };
    await load(await midQ()); C.S.scope = "DEMO-FIRM-02"; C.S.tab = "changes"; C.render();
    const f2 = C.rowsAt(C.S.date).filter(x => x.firm.id === "DEMO-FIRM-02");
    ok("quarantined middle snapshot: #4 is compared with #2 and the Changes view says so", f2.length && f2.every(x => x.snap.snapshot.sequence === 4 && x.prevSnap.snapshot.sequence === 2) && /compared with #2/.test(w.document.getElementById("main").textContent));
    const fk = Object.fromEntries(snapsOf("DEMO-FIRM-02")), alt = clone(fk["inventory-3.json"]); alt.records[0].record.agent_name += " (replacement)"; fk["inventory-3b.json"] = await resign(alt, k2);
    await load(fk); C.S.tab = "overview"; C.render(); const g2 = C.rowsAt(C.S.date).filter(x => x.firm.id === "DEMO-FIRM-02");
    ok("fork: the firm's position stays at its last snapshot before the fork, no change is computed across it", g2.length && g2.every(x => x.snap.snapshot.sequence === 2) && C.quarantined().filter(q => q.f.id === "DEMO-FIRM-02").length === 3);
    C.S.scope = "all"; }
  await C.loadSample(); C.render(); ok("sample data is badged while loaded", !w.document.getElementById("sample-badge").hidden);
  C.clearAll(); C.render(); ok("the console starts from an empty state when nothing is loaded", w.document.getElementById("sample-badge").hidden && /No feed loaded/.test(w.document.getElementById("main").textContent));
  w.close();
  // verification unavailable: a browser without Ed25519 treats every snapshot as unverified and shows nothing as trusted
  const dom2 = new JSDOM(html, { runScripts: "dangerously", pretendToBeVisual: true, url: "https://console.example/", beforeParse(w2) {
    const no = async () => { const e = new Error("Ed25519 is not supported"); e.name = "NotSupportedError"; throw e; };
    Object.defineProperty(w2, "crypto", { value: { getRandomValues: a => globalThis.crypto.getRandomValues(a), subtle: { digest: (...a) => globalThis.crypto.subtle.digest(...a), importKey: no, verify: no } } });
    w2.TextEncoder = TextEncoder; w2.fetch = async () => { throw new Error("offline"); }; } });
  { const w2 = dom2.window, C2 = w2.ARPConsole; await C2.ready; await C2.loadSample(); C2.render();
    const banner = w2.document.getElementById("trust-banner");
    ok("verification unavailable: no snapshot is trusted, the banner says so, nothing reaches the totals",
       !banner.hidden && /Verification unavailable/.test(banner.textContent) && C2.quarantined().length === 20 && C2.quarantined().every(x => x.md.unverifiable) && !C2.rowsAt("2026-09-30").length && !C2.rowsAt("2025-12-31").length);
    C2.S.tab = "feed"; C2.render(); ok("verification unavailable: the Feed view marks snapshots as unverified", /Unverified · not shown in any view/.test(w2.document.getElementById("main").textContent));
    w2.close(); }
  // no Web Crypto at all (W8, D5d): the console still loads and shows "Verification unavailable" instead of throwing
  const errs = []; const dom3 = new JSDOM(html, { runScripts: "dangerously", pretendToBeVisual: true, url: "https://console.example/", beforeParse(w3) {
    Object.defineProperty(w3, "crypto", { value: { getRandomValues: a => globalThis.crypto.getRandomValues(a) } }); w3.TextEncoder = TextEncoder;
    w3.fetch = async () => { throw new Error("offline"); }; w3.addEventListener("error", e => errs.push(String(e.message))); w3.addEventListener("unhandledrejection", e => errs.push(String(e.reason))); } });
  { const w3 = dom3.window, C3 = w3.ARPConsole; let err = null;
    try { await C3.ready; await C3.loadSample(); C3.render(); } catch (e) { err = e; }
    const banner = w3.document.getElementById("trust-banner");
    ok("no Web Crypto at all: no error, banner says verification unavailable, nothing trusted", !err && !errs.length && C3.CRYPTO_OK === false && !banner.hidden && /Verification unavailable/.test(banner.textContent) && C3.quarantined().length === 20 && !C3.rowsAt("2026-09-30").length,
       String(err || errs.join("; ")));
    w3.close(); }
}
console.log(`${pass} passed, ${fail} failed${skipped ? `, ${skipped} group skipped` : ""}`); process.exit(fail ? 1 : 0);
