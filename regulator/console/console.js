// SPDX-License-Identifier: Apache-2.0
/* ====================================================================================
   ARP Supervisory dashboard demo. The Profile checker (check, validate, canonicalHash, verifySig)
   and renderProfile above are shared with the Profile Viewer; everything below is the console.
   ==================================================================================== */
const $$ = s => [...document.querySelectorAll(s)];
const PEER = V.peer_controls;
const TIERS = ["T0","T1","T2","T3","T4","U"];
const TIER_RANK = {T0:0,T1:1,T2:2,T3:3,T4:4,U:-1};
const ACT = Object.fromEntries(V.actions.map(a=>[a.id,a]));
const BL_LABEL = {retail_consumer_banking:"Retail banking",lending_credit:"Lending and credit",payments:"Payments",financial_crime_compliance:"Financial crime and compliance",
  markets:"Markets",wealth_asset_management:"Wealth and asset management",treasury_finance:"Treasury and finance",insurance:"Insurance",internal_corporate:"Internal and corporate"};
const STATUS_LABEL = {in_development:"In development",pilot:"Pilot",production:"Production",retired:"Retired"};
const APPROVAL_LABEL = {every_material_action:"Every material action",some_actions:"Some actions",none:"None"};
const APR_RANK = {every_material_action:2,some_actions:1,none:0};
const CTL_STATUS = ["tested_held","configured","documented_only","unknown","absent","tested_not_shown_to_hold","not_applicable"];
const CTL_LABEL = Object.fromEntries(V.peer_control_status.map(t=>[t.id,t.label])); // vocab/peer-control-status.json
const CTL_CHIP = {tested_held:"c-good",tested_not_shown_to_hold:"c-bad",configured:"c-accent",documented_only:"c-neutral",absent:"c-bad",unknown:"c-warn",not_applicable:"c-neutral"};
const CTL_RANK = {tested_held:4,configured:3,documented_only:2,unknown:1,absent:0,tested_not_shown_to_hold:0};
const STATUS_SETS = {production:["production"],live:["production","pilot"],active:["production","pilot","in_development"],all:["production","pilot","in_development","retired"]};
const DELIVERY = {pull:["Pull","The console reads the firm's feed endpoint on the supervisor's schedule."],push:["Push","The firm submits each snapshot to the supervisor's endpoint and receives a signed receipt."],
  file:["File","The firm uploads the signed snapshot file through the existing secure portal."]};
const pct = v => v==null||isNaN(v) ? "–" : `${Math.round(v*100)}%`;
const fmtDate = d => { if(typeof d!=="string"||!/^\d{4}-\d{2}-\d{2}/.test(d)) return esc(String(d??"–")); const [y,m,dd]=d.split("-").map(Number); return `${dd} ${["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][m-1]} ${y}`; };
const qLabel = d => { if(typeof d!=="string"||!/^\d{4}-\d{2}/.test(d)) return esc(String(d??"–")); const [y,m]=d.split("-").map(Number); return `Q${Math.ceil(m/3)} ${y}`; };
const days = (a,b) => Math.round((Date.parse(a)-Date.parse(b))/864e5);
const median = a => { if(!a.length) return null; const s=[...a].sort((x,y)=>x-y), n=s.length; return n%2?s[(n-1)/2]:(s[n/2-1]+s[n/2])/2; };
const share = (rs,f) => rs.length ? rs.filter(f).length/rs.length : null;
const uniq = a => [...new Set(a)];
const shortHash = h => h ? h.slice(7,19)+"…" : "–";
/* composite keys (firm|ref, dim|value|tab): each part is URI-encoded, so a "|" inside a firm id or label cannot split it */
const kj = (...parts) => parts.map(x=>encodeURIComponent(String(x))).join("|");
const ks = k => String(k).split("|").map(decodeURIComponent);
const providersOf = r => uniq((r.models||"").split(",").map(s=>s.trim()).filter(Boolean).map(m=>{ const t=m.split(/\s+/); return t.length>2?t.slice(0,-2).join(" "):t[0]; }));

/* ---------- the feed checks (port of regulator/arp_feed.py; rules INV-001 to INV-040; spec/FEED.md §6) ---------- */
/* A snapshot signature signs the snapshot hash together with the signer's role, name and key (arp_feed.snapshot_statement). */
const SNAP_CONTEXT = "arp-inventory/0.1 snapshot signature";
async function verifySnapSig(x){ return verifyMsg(x.public_key, x.value, canon({context:SNAP_CONTEXT,alg:x.alg||"ed25519",role:x.role,name:x.name,public_key:x.public_key,signed_hash:x.signed_hash})); }
function liteCheck(r){ const out=[], perm=new Set(r.permitted_actions), both=r.prohibited_actions.filter(a=>perm.has(a));
  if(both.length) out.push(["LITE-010","actions",`both permitted and prohibited: ${both.join(", ")}`]);
  if(r.autonomy_tier==="T2"&&r.human_approval!=="every_material_action") out.push(["LITE-011","human_approval","tier T2 means a person approves every material action"]);
  if(r.tier_basis==="substantiated"&&r.human_approval==="none") out.push(["LITE-012","tier_basis","a tier cannot be substantiated by approval records when there is no human approval"]);
  if((r.profile_level||"none")!=="none"&&!r.full_profile_ref) out.push(["LITE-013","full_profile_ref","a full Profile level is given but no Profile id"]);
  const u=UC[r.use_case_id]; if(u&&r.business_line&&u.business_line!==r.business_line) out.push(["LITE-W01","use_case_id",`warning: ${u.id} is catalogued under ${u.business_line}`]);
  return out; }
/* Strict JSON for files and pulled documents: rejects duplicate keys, as arp_feed.py does (a first-wins reader would see a different document). */
function parseStrict(text){
  const v=JSON.parse(text); let i=0; const n=text.length, ws=()=>{ while(i<n&&" \t\r\n".includes(text[i])) i++; };
  const str=()=>{ let j=i+1, out=""; while(text[j]!=='"'){ if(text[j]==="\\"){ out+=text.slice(j,j+2); j+=2; } else out+=text[j++]; } const s=text.slice(i,j+1); i=j+1; return JSON.parse(s); };
  const val=()=>{ ws(); const c=text[i];
    if(c==="{"){ i++; const keys=new Set(); ws(); if(text[i]==="}"){ i++; return; }
      for(;;){ ws(); const k=str(); if(keys.has(k)) throw new Error(`duplicate key '${k}' in a JSON object`); keys.add(k); ws(); i++; val(); ws(); if(text[i]===","){ i++; continue; } i++; return; } }
    if(c==="["){ i++; ws(); if(text[i]==="]"){ i++; return; } for(;;){ val(); ws(); if(text[i]===","){ i++; continue; } i++; return; } }
    if(c==='"'){ str(); return; } while(i<n&&!",]} \t\r\n".includes(text[i])) i++; };
  val(); return v; }
/* INV-023: an inventory record must agree with its full Profile on the fields they share (port of arp_feed.profile_divergence;
   the Profile's values are derived as arp_lite.from_profile derives a Lite record, with several results per field aggregated per SPEC §4). */
const SHARED=["business_line","use_case","use_case_id","autonomy_tier","tier_basis","permitted_actions","prohibited_actions","models","accountable_owner_role"], OPTIONAL_SHARED=new Set(["use_case_id","models"]);
const normModels=v=>String(v).split(",").filter(x=>x.trim()).map(x=>x.trim().split(/\s+/).join(" ")).sort();
function liteFromProfile(p){ const c=p.claim, res=fieldDispositions(p.results||[]), prov=p.provenance||{};
  const st=cid=>{ const x=(c.controls||[]).find(k=>k.control_id===cid); if(!x) return "unknown"; if(x.applicable===false) return "not_applicable"; if(x.present===false) return "absent"; if(x.present==null) return "unknown";
    const d=hasOwn(res,`controls.${cid}`)?res[`controls.${cid}`].disposition:null; if(d) return d==="held"?"tested_held":"tested_not_shown_to_hold";
    const cls=(prov[`controls.${cid}`]||{}).class; return cls==="configuration_derived"||cls==="measured"?"configured":"documented_only"; };
  const out={business_line:c.odd.business_line,use_case:c.odd.use_case,autonomy_tier:c.autonomy.tier,tier_basis:c.autonomy.tier_basis,permitted_actions:c.actions.permitted,
    prohibited_actions:c.actions.prohibited,accountable_owner_role:p.issuance.owner.role,controls:Object.fromEntries(V.peer_controls.map(k=>[k,st(k)]))};
  if(c.odd.use_case_id) out.use_case_id=c.odd.use_case_id;
  const ms=(p.subject||{}).models||[]; if(ms.length) out.models=ms.map(m=>`${m.provider} ${m.model} ${m.version}`).join(", ");
  return out; }
function profileDivergence(rec, doc){ const d=liteFromProfile(doc), out=[], same=(x,y)=>JSON.stringify(x)===JSON.stringify(y);
  for(const k of SHARED){ const a=rec[k], b=d[k]; if(OPTIONAL_SHARED.has(k)&&(a==null||b==null)) continue;
    const eq=k==="permitted_actions"||k==="prohibited_actions"?same([...(a||[])].sort(),[...(b||[])].sort()):k==="models"?same(normModels(a),normModels(b)):a===b;
    if(!eq) out.push([k,a,b]); }
  if(((doc.claim||{}).autonomy||{}).tier==="T2"&&rec.human_approval!=="every_material_action") out.push(["human_approval",rec.human_approval,"every_material_action"]);
  for(const c of V.peer_controls){ const a=(rec.controls||{})[c], b=d.controls[c]; if(a!==b) out.push([`controls.${c}`,a,b]); }
  return out; }
const fmtV=v=>Array.isArray(v)?v.join(" "):String(v);
function divergenceCheck(r,doc,meta,path,E,W){ const div=profileDivergence(r,doc), note=r.divergence;
  if(div.length){ const declared=new Set((note&&note.fields)||[]), und=div.filter(x=>!declared.has(x[0]));
    if(und.length) E("INV-023",`${path}/record`,`${r.inventory_ref}: the record differs from its full Profile on ${und.map(x=>x[0]).join(", ")} (${und.slice(0,3).map(([k,a,b])=>`${k}: record ${fmtV(a)}, Profile ${fmtV(b)}`).join("; ")}); derive it from the Profile or declare the divergence with a date and reason`);
    else W("INV-023",`${path}/record`,`${r.inventory_ref}: declared divergence from the full Profile since ${note.as_of} on ${div.map(x=>x[0]).join(", ")}: ${note.reason}`); }
  if(note&&(note.as_of||"")>meta.as_of) E("INV-023",`${path}/record/divergence`,`${r.inventory_ref}: the divergence is dated ${note.as_of}, after the snapshot's as-of date`); }
/* Quarantine (FEED.md §6, "Trusted and quarantined snapshots"): only a verified snapshot feeds the supervisory views.
   Any error quarantines; so does any warning outside USABLE_WARNINGS (an unverified signer, an unchecked chain, a browser
   that cannot verify Ed25519). Usable warnings (a Lite catalogue mismatch, an expired Profile, a declared divergence) are labelled. */
const USABLE_WARNINGS=new Set(["INV-010","INV-022","INV-023"]);
const isUnverifiable=f=>f.rule==="INV-040"&&f.severity!=="error"&&/cannot verify Ed25519/.test(f.message);
function trustOf(findings){ const reasons=findings.filter(f=>f.severity==="error"||!USABLE_WARNINGS.has(f.rule)).map(f=>isUnverifiable(f)?"verification unavailable: this browser cannot verify Ed25519 signatures":`${f.rule} ${f.message}`);
  return {trusted:!reasons.length,reasons,unverifiable:findings.some(isUnverifiable)}; }
function keyAllowed(entry,pub,seq){ if(!entry||typeof entry!=="object") return false; if(entry.public_key===pub) return true;
  return (entry.retired_keys||[]).some(k=>k&&k.public_key===pub&&Number.isInteger(k.last_sequence)&&seq<=k.last_sequence); }
async function checkSnapshot(s, prev, objects, registry){
  try{ return await checkSnapshot_(s, prev, objects, registry); }
  catch(e){ return [{rule:"INV-001",severity:"error",path:"-",message:"could not be checked: "+e.message}]; } }
async function checkSnapshot_(s, prev, objects, registry){ // registry: {firm_id: entry} or null when no key register was supplied
  const out=[]; const E=(rule,path,message)=>out.push({rule,severity:"error",path,message}), W=(rule,path,message)=>out.push({rule,severity:"warning",path,message});
  const se=[]; validate(D.inventory_schema,s,[],D.inventory_schema,se); se.forEach(([p,m])=>E("INV-001",p||"-",m)); if(out.length) return out;
  const inst=s.institution, meta=s.snapshot, seen=new Map();
  for(let i=0;i<s.records.length;i++){ const e=s.records[i], r=e.record, path=`records/${i}`;
    liteCheck(r).forEach(([rule,field,msg])=>(rule.includes("W")?W:E)("INV-010",`${path}/record/${field}`,`${r.inventory_ref}: ${rule} ${msg}`));
    if(seen.has(r.inventory_ref)) E("INV-011",path,`${r.inventory_ref} appears more than once`); seen.set(r.inventory_ref,r);
    if(r.institution!==inst.name) E("INV-012",`${path}/record/institution`,`${r.inventory_ref} names '${r.institution}', not '${inst.name}'`);
    const pr=e.profile;
    if(r.profile_level!=="none"){ if(!pr) E("INV-020",path,`${r.inventory_ref} reports a Level ${r.profile_level[1]} Profile but carries no commitment to it`);
      else if(pr.stage!=="issued"||`L${pr.headline}`!==r.profile_level||pr.profile_id!==r.full_profile_ref) E("INV-020",`${path}/profile`,`${r.inventory_ref}: the committed Profile (${pr.profile_id}, ${pr.stage}, Level ${pr.headline}) does not match the record (${r.full_profile_ref}, ${r.profile_level})`); }
    else if(pr&&pr.stage==="issued") E("INV-020",`${path}/profile`,`${r.inventory_ref} commits to an issued Profile but reports profile_level 'none'`);
    if(pr){ let validUntil=pr.valid_until; const doc=objects.get(pr.sha256);
      if(!doc){ // as arp_feed.py: a held document with the committed profile_id but another hash is an error, and the record is checked against it
        const held=[]; for(const [hh,d] of objects) if(d&&typeof d==="object"&&d.profile_id===pr.profile_id) held.push([((d.subject||{}).deployment_id!==r.inventory_ref)?1:0,hh,d]);
        held.sort((a,b)=>a[0]-b[0]||(a[1]<b[1]?-1:a[1]>b[1]?1:0));
        if(held.length){ E("INV-021",`${path}/profile`,`${r.inventory_ref}: Profile ${pr.profile_id} is held with hash ${held[0][1].slice(0,19)}…, not the committed ${String(pr.sha256).slice(0,19)}…: deliver the committed version or correct the commitment`);
          if((held[0][2].subject||{}).deployment_id===r.inventory_ref) divergenceCheck(r,held[0][2],meta,path,E,W); } }
      if(doc){ const h=await canonicalHash(doc);
        if(h!==pr.sha256) E("INV-021",`${path}/profile`,`${r.inventory_ref}: the delivered Profile's hash ${h.slice(0,19)}… is not the committed one`);
        else { const subj=doc.subject||{}, iss=doc.issuance||{};
          const actual={profile_id:doc.profile_id,stage:doc.stage,headline:(doc.assurance||{}).headline,valid_until:iss.valid_until};
          const diffs=Object.keys(actual).filter(k=>(pr[k]===undefined?null:pr[k])!==(actual[k]===undefined?null:actual[k]));
          if(diffs.length) E("INV-021",`${path}/profile`,`${r.inventory_ref}: the commitment's ${diffs.join(", ")} differ${diffs.length===1?"s":""} from the delivered Profile`);
          if(subj.institution!==inst.name) E("INV-021",`${path}/profile`,`${r.inventory_ref}: the delivered Profile is about '${subj.institution}', not '${inst.name}'`);
          if(subj.deployment_id!==r.inventory_ref) E("INV-021",`${path}/profile`,`${r.inventory_ref}: the delivered Profile's deployment_id '${subj.deployment_id}' is not this record's inventory_ref`);
          divergenceCheck(r,doc,meta,path,E,W);
          (await check(doc)).filter(f=>f.severity==="error").forEach(f=>E("INV-021",`${path}/profile`,`${r.inventory_ref}: the Profile fails ${f.rule}: ${f.message}`));
          validUntil=iss.valid_until; } }
      if(pr.stage==="issued"&&validUntil&&validUntil<meta.as_of) W("INV-022",`${path}/profile`,`${r.inventory_ref}: Profile ${pr.profile_id} expired on ${validUntil}`); } }
  if(prev){ const pm=prev.snapshot;
    if(prev.institution.firm_id!==inst.firm_id) E("INV-030","institution/firm_id","the previous snapshot is for a different firm");
    if(meta.sequence!==pm.sequence+1) E("INV-030","snapshot/sequence",`sequence ${meta.sequence} does not follow ${pm.sequence}`);
    if(meta.previous_hash!==await canonicalHash(prev)) E("INV-030","snapshot/previous_hash","previous_hash is not the hash of the previous snapshot: history has been altered or a snapshot is missing");
    if(meta.as_of<pm.as_of) E("INV-030","snapshot/as_of","as_of is earlier than the previous snapshot's");
    prev.records.forEach(pe=>{ const p=pe.record; if(p.deployment_status!=="retired"&&!seen.has(p.inventory_ref)) E("INV-031","records",`${p.inventory_ref} (${p.agent_name}) was in the previous snapshot and has disappeared without being marked retired`); }); }
  else if(meta.sequence!==1) W("INV-030","snapshot","previous snapshot not supplied, so the chain was not checked");
  if(meta.sequence===1&&meta.previous_hash!==null) E("INV-030","snapshot/previous_hash","the first snapshot (sequence 1) must have previous_hash null");
  const sigs=s.signatures; if(!sigs.length) E("INV-040","signatures","no institution signature");
  const h=await canonicalHash(s), entry=registry?registry[inst.firm_id]:undefined;
  if(registry&&!entry) E("INV-040","institution/firm_id",`firm ${inst.firm_id} is not in the key register`);
  for(let i=0;i<sigs.length;i++){ const x=sigs[i];
    if(x.signed_hash!==h){ E("INV-040",`signatures/${i}`,"the signature does not cover this snapshot"); continue; }
    const v=await verifySnapSig(x);
    if(v==="invalid"){ E("INV-040",`signatures/${i}`,"the signature does not verify"); continue; }
    if(v==="unsupported") W("INV-040",`signatures/${i}`,"this browser cannot verify Ed25519 signatures; use arp_feed.py check");
    if(!registry){ W("INV-040",`signatures/${i}`,"UNVERIFIED SIGNER: no key register was supplied, so the signing key was not checked");
      const pk=new Set(((prev||{}).signatures||[]).map(y=>y.public_key)); if(prev&&pk.size&&!pk.has(x.public_key)) E("INV-040",`signatures/${i}`,"the signing key changed since the previous snapshot and no key register records the rotation"); }
    else if(entry){ if(!entry.public_key) E("INV-040",`signatures/${i}`,`firm ${inst.firm_id} has no registered key`);
      else if(!keyAllowed(entry,x.public_key,meta.sequence)) E("INV-040",`signatures/${i}`,"signed with a key that is not the firm's registered key"); } }
  return out; }
/* One firm's snapshots as a chain (port of arp_feed.check_feed). Returns [[snapshot, findings]] in sequence order.
   Two different snapshots claiming the same sequence are a fork (INV-030); neither is shown as the firm's position. */
async function checkFeed(snaps, objects, registry){
  const good=[], bad=[];
  for(const s of snaps){ const f=await checkSnapshot(s,null,objects,registry); (f.some(x=>x.rule==="INV-001")?bad:good).push([s,f]); }
  // each firm's history is a separate chain: another firm's snapshot never affects this one (as arp_feed.check_feed)
  const firms=new Map(); for(const g of good){ const id=g[0].institution.firm_id; if(!firms.has(id)) firms.set(id,[]); firms.get(id).push(g); }
  let out=[]; for(const id of [...firms.keys()].sort()) out=out.concat(await chainOne(firms.get(id),objects,registry));
  return out.concat(bad); }
async function chainOne(good, objects, registry){
  const bySeq=new Map(), hash=new Map();
  for(const [s] of good){ hash.set(s,await canonicalHash(s)); const q=s.snapshot.sequence; if(!bySeq.has(q)) bySeq.set(q,[]); bySeq.get(q).push(s); }
  const out=[]; let forkAt=null;
  for(const seq of [...bySeq.keys()].sort((a,b)=>a-b)){ const uniqH=new Map(); bySeq.get(seq).forEach(s=>{ if(!uniqH.has(hash.get(s))) uniqH.set(hash.get(s),s); });
    if(uniqH.size>1&&forkAt===null) forkAt=seq;
    for(const s of uniqH.values()){ const cands=bySeq.get(seq-1)||[];
      let prev=cands.find(p=>hash.get(p)===s.snapshot.previous_hash)||null;
      if(!prev&&new Set(cands.map(p=>hash.get(p))).size===1) prev=cands[0];
      const f=await checkSnapshot(s,prev,objects,registry);
      if(seq>1&&!cands.length) f.unshift({rule:"INV-030",severity:"error",path:"snapshot/sequence",message:`snapshot ${seq-1} is missing from the feed`});
      else if(seq>1&&!prev) f.unshift({rule:"INV-030",severity:"error",path:"snapshot/previous_hash",message:`no snapshot ${seq-1} in the feed has this snapshot's previous_hash`});
      if(uniqH.size>1) f.unshift({rule:"INV-030",severity:"error",path:"snapshot/sequence",message:`fork: ${uniqH.size} different snapshots claim sequence ${seq}`,fork:true});
      else if(forkAt!==null&&seq>forkAt) f.unshift({rule:"INV-030",severity:"error",path:"snapshot/sequence",message:`follows an unresolved fork at sequence ${forkAt}: not used until the supervisor confirms with the firm which snapshot ${forkAt} is genuine and removes the other`});
      out.push([s,f]); } }
  return out; }
/* What an opened file is. Key registers are never accepted from the snapshot picker (the trust anchor is loaded separately). */
function classifyFile(j){ if(!j||typeof j!=="object"||Array.isArray(j)) return "unknown";
  if("inventory_spec" in j) return "snapshot"; if(j.spec&&j.profile_id) return "profile"; if(Array.isArray(j.firms)) return "register"; return "unknown"; }
/* A pulled snapshot is accepted only from the firm's own endpoint origin and only if it names that firm. */
function acceptPulled(firmId, endpoint, href, snap){
  let base, u; try{ base=new URL(endpoint); u=new URL(href, base.href.replace(/\/?$/,"/")); }catch(e){ return "bad address"; }
  if(u.origin!==base.origin) return `refused: ${u.origin} is not the firm's endpoint origin ${base.origin}`;
  if(snap!==undefined&&!(snap&&snap.institution&&snap.institution.firm_id===firmId)) return `refused: the snapshot names firm ${snap&&snap.institution?snap.institution.firm_id:"(none)"}, not ${firmId}`;
  return null; }

/* ---------- store ---------- */
const DB = { firms:new Map(), objects:new Map(), meta:new WeakMap(), registry:null, registerName:null, sample:false, rejected:[] };
/* Without Web Crypto (no crypto.subtle) nothing can be hashed or verified: every snapshot is shown as unverified (FEED.md §6). */
const CRYPTO_OK = (()=>{ try{ return !!(globalThis.crypto&&globalThis.crypto.subtle&&typeof globalThis.crypto.subtle.digest==="function"); }catch(_){ return false; } })();
const NO_CRYPTO = {rule:"INV-040",severity:"warning",path:"signatures",message:"this browser cannot verify Ed25519 signatures (no Web Crypto in this browser): verification unavailable"};
const unregisteredName = id => `Unregistered firm (${id})`; // a quarantined firm's self-declared name is never shown (it is unverified)
const safeSnap = s => (s&&typeof s==="object"&&s.snapshot&&typeof s.snapshot==="object")?s.snapshot:{};
function firmFor(inst){ const ok=inst&&typeof inst==="object"&&typeof inst.firm_id==="string", id=ok?inst.firm_id:"(unidentified)";
  let f=DB.firms.get(id);
  if(!f){ f={id,name:unregisteredName(id),short:unregisteredName(id),peer:"Unassigned",delivery:"file",endpoint:null,public_key:null,registered:false,snaps:[]}; DB.firms.set(id,f); }
  return f; }
function setRegister(reg, name){ // reg: {firms:[...]} or null
  DB.registry=null; DB.registerName=null;
  for(const f of DB.firms.values()) Object.assign(f,{registered:false,peer:"Unassigned",endpoint:null,public_key:null,name:unregisteredName(f.id),short:unregisteredName(f.id)});
  if(!reg) return;
  DB.registry={}; DB.registerName=name;
  (reg.firms||[]).forEach(r=>{ if(!r||typeof r.firm_id!=="string") return; DB.registry[r.firm_id]=r;
    const f=DB.firms.get(r.firm_id)||{snaps:[]};
    DB.firms.set(r.firm_id,{...f,id:r.firm_id,name:String(r.name||r.firm_id),short:String(r.short||r.name||r.firm_id),peer:String(r.peer_group||"Unassigned"),delivery:r.delivery||"file",endpoint:r.endpoint||null,public_key:r.public_key||null,registered:true}); }); }
function clearAll(){ DB.firms.clear(); DB.objects.clear(); DB.registry=null; DB.registerName=null; DB.sample=false; DB.rejected=[]; S.scope="all"; S.filters=[]; S.drill=null; S.date=null; }
async function loadData(registry, snaps, objects, opts={}){
  clearAll(); DB.sample=!!opts.sample;
  setRegister(registry, opts.registerName||"sample register (fictional firms)");
  for(const p of objects) await addObject(p);
  for(const s of snaps) await addSnapshot(s);
  await recheckAll(); }
const loadSample = () => loadData(D.sample.registry,D.sample.snapshots,D.sample.objects,{sample:true});
async function addObject(p){ if(!CRYPTO_OK) return; try{ DB.objects.set(await canonicalHash(p),p); }catch(_){} }
async function addSnapshot(s){ const f=firmFor(s&&s.institution); let h=null; try{ if(CRYPTO_OK) h=await canonicalHash(s); }catch(_){}
  if(h&&f.snaps.some(x=>(DB.meta.get(x)||{}).hash===h)) return false; // the same document again: ignore. A different one is kept, never replaced.
  f.snaps.push(s); DB.meta.set(s,{hash:h,findings:[]}); return true; }
async function recheckAll(){
  if(!CRYPTO_OK){ for(const f of DB.firms.values()){ for(const s of f.snaps) DB.meta.set(s,{hash:null,findings:[NO_CRYPTO],ok:false,reasons:[NO_CRYPTO.message],unverifiable:true});
      f.snaps.sort((a,b)=>(Number(safeSnap(a).sequence)||0)-(Number(safeSnap(b).sequence)||0)); } CACHE.clear(); return; }
  for(const f of DB.firms.values()){ const res=await checkFeed(f.snaps,DB.objects,DB.registry), seen=new Set();
    for(const [s,findings] of res){ seen.add(s); let h=null; try{ h=await canonicalHash(s); }catch(_){}
      const t=trustOf(findings); DB.meta.set(s,{hash:h,findings,ok:t.trusted,reasons:t.reasons,unverifiable:t.unverifiable}); }
    f.snaps.sort((a,b)=>(Number(safeSnap(a).sequence)||0)-(Number(safeSnap(b).sequence)||0)); }
  CACHE.clear(); }
const shown = f => f.snaps.filter(s=>(DB.meta.get(s)||{}).ok); // trusted snapshots only: the only ones that feed positions, totals, trends, outliers and changes
const quarantined = () => firms().flatMap(f=>f.snaps.filter(s=>!(DB.meta.get(s)||{}).ok).map(s=>({f,s,md:DB.meta.get(s)||{reasons:[],findings:[]}})));
const firms = () => [...DB.firms.values()].filter(f=>f.snaps.length);
const allDates = () => uniq(firms().flatMap(f=>shown(f).map(s=>s.snapshot.as_of))).sort();
function snapAt(f,date){ let cur=null,prev=null; for(const s of shown(f)){ if(s.snapshot.as_of<=date){ prev=cur; cur=s; } } return {cur,prev}; }

/* ---------- supervisory flags (heuristics, configurable; not part of the standard) ---------- */
const prod = x => x.r.deployment_status==="production";
const live = x => ["production","pilot"].includes(x.r.deployment_status);
const permits = (x,as) => as.some(a=>x.r.permitted_actions.includes(a));
const FLAGS = [
  {id:"autonomy_untested_ext",sev:"high",label:"High autonomy, untested, acts externally",why:"Tier T3 or T4 in production, permits external or hard-to-reverse actions (A7 to A12), and has no tested (Level 2 or 3) full Profile.",
    test:x=>prod(x)&&["T3","T4"].includes(x.r.autonomy_tier)&&!["L2","L3"].includes(x.r.profile_level)&&permits(x,["A7","A8","A9","A10","A11","A12"])},
  {id:"autonomy_untested",sev:"medium",label:"High autonomy, untested",why:"Tier T3 or T4 in production with internal actions only, and no tested (Level 2 or 3) full Profile.",
    test:x=>prod(x)&&["T3","T4"].includes(x.r.autonomy_tier)&&!["L2","L3"].includes(x.r.profile_level)&&!permits(x,["A7","A8","A9","A10","A11","A12"])},
  {id:"unprofiled",sev:"high",label:"Unprofiled (tier U)",why:"No reliability claim is possible: envelope, fallback or action boundaries are unspecified.",
    test:x=>live(x)&&x.r.autonomy_tier==="U"},
  {id:"irreversible_unapproved",sev:"high",label:"Irreversible actions, no approval",why:"Permits moving funds (A9), regulatory filing (A10) or access changes (A11) with no human approval.",
    test:x=>live(x)&&permits(x,["A9","A10","A11"])&&x.r.human_approval==="none"},
  {id:"funds_uncapped",sev:"high",label:"Transacts without enforced caps",why:"Permits A8 or A9, but transaction caps are absent, unknown or only documented.",
    test:x=>live(x)&&permits(x,["A8","A9"])&&["absent","unknown","documented_only"].includes(x.r.controls["tool.transaction_caps"])},
  {id:"control_failed",sev:"high",label:"A control failed its test",why:"A peer-set control was tested and not shown to hold.",
    test:x=>live(x)&&Object.values(x.r.controls).includes("tested_not_shown_to_hold")},
  {id:"autonomy_creep",sev:"medium",label:"Autonomy up, Profile unchanged",why:"The tier is higher than in the previous snapshot and the full Profile has not been reissued.",
    test:x=>x.prevR&&TIER_RANK[x.r.autonomy_tier]>TIER_RANK[x.prevR.autonomy_tier]&&(x.p||{}).sha256===(x.prevP||{}).sha256},
  {id:"approval_reduced",sev:"medium",label:"Human approval reduced",why:"Less human approval is required than in the previous snapshot.",
    test:x=>x.prevR&&APR_RANK[x.r.human_approval]<APR_RANK[x.prevR.human_approval]},
  {id:"key_control_gap",sev:"medium",label:"Kill switch or logging gap",why:"The kill switch or immutable tool-call logging is absent or unknown.",
    test:x=>prod(x)&&["harness.kill_switch","harness.immutable_tool_call_logging"].some(c=>["absent","unknown"].includes(x.r.controls[c]))},
  {id:"cf_no_profile",sev:"medium",label:"Customer-facing, no full Profile",why:"In production with customers and no full Profile.",
    test:x=>prod(x)&&x.r.customer_facing==="yes"&&x.r.profile_level==="none"},
  {id:"profile_expired",sev:"medium",label:"Full Profile expired",why:"The committed Profile's validity ended before this snapshot's as-of date.",
    test:x=>x.p&&x.p.stage==="issued"&&x.p.valid_until&&x.p.valid_until<x.asOf},
  {id:"tier_asserted",sev:"low",label:"Tier asserted only",why:"T2 or above in production on the institution's word, not substantiated by approval records or tests.",
    test:x=>prod(x)&&["T2","T3","T4"].includes(x.r.autonomy_tier)&&x.r.tier_basis==="asserted"},
  {id:"stale_review",sev:"low",label:"Not reviewed in 12 months",why:"The record's last review is more than a year before the as-of date.",
    test:x=>live(x)&&days(x.asOf,x.r.last_reviewed)>365}];
const SEV_RANK = {high:3,medium:2,low:1};
const SEV_LABEL = {high:"High",medium:"Medium",low:"Low"};
const sevChip = s => `<span class="sev ${s}">${SEV_LABEL[s]}</span>`;

/* ---------- rows: one per deployment in a firm's current snapshot at a date ---------- */
const CACHE = new Map();
function rowsAt(date){ if(CACHE.has(date)) return CACHE.get(date); const out=[];
  for(const f of firms()){ const {cur,prev}=snapAt(f,date); if(!cur) continue;
    const pmap=new Map((prev?prev.records:[]).map(e=>[e.record.inventory_ref,e]));
    for(const e of cur.records){ const pe=pmap.get(e.record.inventory_ref);
      const x={firm:f,snap:cur,prevSnap:prev,entry:e,r:e.record,p:e.profile||null,prevR:pe?pe.record:null,prevP:pe?pe.profile||null:null,asOf:cur.snapshot.as_of,key:kj(f.id,e.record.inventory_ref)};
      x.flags=FLAGS.filter(fl=>{ try{ return fl.test(x); }catch(_){ return false; } }); x.sev=x.flags.reduce((m,fl)=>Math.max(m,SEV_RANK[fl.sev]),0); out.push(x); } }
  CACHE.set(date,out); return out; }

/* ---------- dimensions for cuts ---------- */
const DIMS = [
  {id:"firm",label:"Firm",get:x=>x.firm.short},
  {id:"peer",label:"Peer group",get:x=>x.firm.peer},
  {id:"status",label:"Deployment status",get:x=>STATUS_LABEL[x.r.deployment_status],order:Object.values(STATUS_LABEL)},
  {id:"business_line",label:"Business line",get:x=>BL_LABEL[x.r.business_line]||x.r.business_line,order:V.business_lines.map(b=>BL_LABEL[b])},
  {id:"use_case",label:"Use case",get:x=>x.r.use_case_id&&UC[x.r.use_case_id]?`${x.r.use_case_id} · ${UC[x.r.use_case_id].label}`:x.r.use_case},
  {id:"tier",label:"Autonomy tier",get:x=>x.r.autonomy_tier,order:TIERS,ordinal:true},
  {id:"tier_basis",label:"Tier basis",get:x=>x.r.tier_basis==="substantiated"?"Substantiated":"Asserted",order:["Substantiated","Asserted"]},
  {id:"approval",label:"Human approval",get:x=>APPROVAL_LABEL[x.r.human_approval],order:Object.values(APPROVAL_LABEL)},
  {id:"customer_facing",label:"Customer-facing",get:x=>x.r.customer_facing==="yes"?"Customer-facing":"Not customer-facing",order:["Customer-facing","Not customer-facing"]},
  {id:"profile_level",label:"Full Profile",get:x=>x.r.profile_level==="none"?"No full Profile":`Level ${x.r.profile_level[1]}`,order:["No full Profile","Level 1","Level 2","Level 3"],ordinal:true},
  {id:"provider",label:"Model provider",get:x=>providersOf(x.r).length?providersOf(x.r):["Not stated"],multi:true},
  {id:"vendor",label:"Vendor or platform",get:x=>x.r.vendor_or_platform||"Not stated"},
  {id:"review_age",label:"Time since review",get:x=>{ const d=days(x.asOf,x.r.last_reviewed); return d<=182?"Under 6 months":d<=365?"6 to 12 months":"Over 12 months"; },order:["Under 6 months","6 to 12 months","Over 12 months"]},
  {id:"action",label:"Permitted action class",get:x=>x.r.permitted_actions.map(a=>`${a} · ${ACT[a].label}`),multi:true,order:V.actions.map(a=>`${a.id} · ${a.label}`)},
  {id:"severity",label:"Highest flag severity",get:x=>x.sev?SEV_LABEL[Object.keys(SEV_RANK).find(k=>SEV_RANK[k]===x.sev)]:"No flags",order:["High","Medium","Low","No flags"]},
  {id:"flag",label:"Supervisory flag",get:x=>x.flags.length?x.flags.map(f=>f.label):["No flags"],multi:true,order:[...FLAGS.map(f=>f.label),"No flags"]},
  ...PEER.map(c=>({id:"ctl:"+c,label:"Control · "+((CTL[c]||{}).label||c),get:x=>CTL_LABEL[x.r.controls[c]]||"Unknown",order:CTL_STATUS.map(s=>CTL_LABEL[s])}))];
const DIM = Object.fromEntries(DIMS.map(d=>[d.id,d]));
const vals = (d,x) => [].concat(DIM[d].get(x));
function orderValues(d, values){ const o=DIM[d].order; if(d==="firm"){ const fo=firms().map(f=>f.short); return values.sort((a,b)=>fo.indexOf(a)-fo.indexOf(b)); }
  return o ? values.sort((a,b)=>(o.indexOf(a)<0?999:o.indexOf(a))-(o.indexOf(b)<0?999:o.indexOf(b))||a.localeCompare(b)) : values.sort((a,b)=>a.localeCompare(b)); }

/* ---------- state ---------- */
const S = {tab:"overview",scope:"all",date:null,status:"production",filters:[],search:"",sort:{key:"sev",dir:-1},
  pivot:{rows:"business_line",cols:"tier",measure:"count"},trend:{dim:"tier",metric:"t3"},change:"all",drill:null};
const TABS = [["overview","Overview"],["inventory","Inventory"],["explore","Explore"],["trends","Trends"],["outliers","Outliers"],["changes","Changes"],["feed","Feed"]];
function inScope(x){ return S.scope==="all"?true:S.scope.startsWith("peer:")?x.firm.peer===S.scope.slice(5):x.firm.id===S.scope; }
function current(opts={}){ const st=STATUS_SETS[opts.status||S.status]; return rowsAt(opts.date||S.date).filter(x=>(opts.allScope||inScope(x))&&st.includes(x.r.deployment_status)&&(opts.noFilters||S.filters.every(f=>vals(f.dim,x).includes(f.val)))); }
const scopeFirms = () => firms().filter(f=>S.scope==="all"||(S.scope.startsWith("peer:")?f.peer===S.scope.slice(5):f.id===S.scope));
const oneFirm = () => S.scope!=="all"&&!S.scope.startsWith("peer:") ? DB.firms.get(S.scope) : null;

/* ---------- firm metrics and peer comparison ---------- */
const METRICS = [
  {id:"t3",short:"T3, T4 or U",label:"At tier T3, T4 or U",worse:"up",f:rs=>share(rs,x=>["T3","T4","U"].includes(x.r.autonomy_tier))},
  {id:"cf",short:"Customer-facing",label:"Customer-facing",worse:null,f:rs=>share(rs,x=>x.r.customer_facing==="yes")},
  {id:"profile",short:"Full Profile",label:"With an issued full Profile",worse:"down",f:rs=>share(rs,x=>x.r.profile_level!=="none")},
  {id:"tested",short:"Tested control",label:"With a control tested and held",worse:"down",f:rs=>share(rs,x=>Object.values(x.r.controls).includes("tested_held"))},
  {id:"high",short:"High flag",label:"With a high-severity flag",worse:"up",f:rs=>share(rs,x=>x.sev===3)},
  {id:"stale",short:"Review > 12 mo",label:"Not reviewed in 12 months",worse:"up",f:rs=>share(rs,x=>days(x.asOf,x.r.last_reviewed)>365)},
  {id:"conc",short:"Top provider",label:"Largest model provider's share",worse:"up",f:rs=>{ if(!rs.length) return null; const c={}; rs.forEach(x=>providersOf(x.r).forEach(p=>c[p]=(c[p]||0)+1)); return Math.max(0,...Object.values(c))/rs.length; }}];
const MET = Object.fromEntries(METRICS.map(m=>[m.id,m]));
function firmMetrics(date){ const rs=rowsAt(date).filter(x=>x.r.deployment_status==="production"); const out=new Map();
  for(const f of firms()){ const mine=rs.filter(x=>x.firm===f); if(!snapAt(f,date).cur) continue;
    const m={n:mine.length}; METRICS.forEach(k=>m[k.id]=k.f(mine)); out.set(f.id,m); }
  return out; }
/* Outlier rule: compare with the median of the OTHER firms in the same peer group (all other firms if fewer than two);
   flag when the gap is at least 15 points and at least 3 times the others' median absolute deviation. */
function peerTest(date){ const M=firmMetrics(date), res=new Map();
  for(const f of firms()){ const mine=M.get(f.id); if(!mine||!mine.n) continue; const r={};
    let others=firms().filter(o=>o!==f&&o.peer===f.peer&&M.get(o.id)&&M.get(o.id).n), basis=f.peer;
    if(others.length<2){ others=firms().filter(o=>o!==f&&M.get(o.id)&&M.get(o.id).n); basis="all other firms"; }
    for(const k of METRICS){ const ov=others.map(o=>M.get(o.id)[k.id]).filter(v=>v!=null), med=median(ov); if(med==null||mine[k.id]==null){ r[k.id]={v:mine[k.id],med:null}; continue; }
      const mad=median(ov.map(v=>Math.abs(v-med))), gap=mine[k.id]-med, thr=Math.max(.15,3*mad), out=Math.abs(gap)>=thr;
      r[k.id]={v:mine[k.id],med,gap,out,dir:gap>0?"up":"down",concern:out&&(k.worse===null?false:k.worse===(gap>0?"up":"down")),basis,n:others.length}; }
    res.set(f.id,r); }
  return res; }

/* ---------- small UI helpers ---------- */
const tip = $("#tip");
function showTip(ev,text){ tip.textContent=text; tip.hidden=false; const r=tip.getBoundingClientRect(); let x=ev.clientX+14, y=ev.clientY+14;
  if(x+r.width>innerWidth-8) x=ev.clientX-r.width-14; if(y+r.height>innerHeight-8) y=ev.clientY-r.height-14; tip.style.left=x+"px"; tip.style.top=y+"px"; }
function bindTips(root){ root.querySelectorAll("[data-tip]").forEach(el=>{ el.addEventListener("pointermove",e=>showTip(e,el.dataset.tip)); el.addEventListener("pointerleave",()=>tip.hidden=true);
  el.addEventListener("focus",()=>{ const b=el.getBoundingClientRect(); showTip({clientX:b.right,clientY:b.bottom},el.dataset.tip); }); el.addEventListener("blur",()=>tip.hidden=true); }); }
function toast(msg){ document.querySelectorAll(".toast").forEach(x=>x.remove()); const t=document.createElement("div"); t.className="toast"; t.setAttribute("role","status"); t.textContent=msg; document.body.appendChild(t); setTimeout(()=>t.remove(),2600); }
const tbl=(head,rows,cls="")=>rows.length?`<div class="tablewrap"><table class="${cls}"><thead><tr>${head.map(h=>typeof h==="string"?`<th>${esc(h)}</th>`:`<th class="${h[1]}">${esc(h[0])}</th>`).join("")}</tr></thead><tbody>${rows.join("")}</tbody></table></div>`:`<p class="empty">Nothing to show for this selection.</p>`;
const tile=(k,v,d="")=>`<div class="tile"><div class="k">${esc(k)}</div><div class="v">${v}</div>${d?`<div class="d">${d}</div>`:""}</div>`;
function addFilter(dim,val,tab){ S.filters=S.filters.filter(f=>f.dim!==dim); S.filters.push({dim,val}); if(tab) S.tab=tab; S.drill=null; render(); }
function nice(max){ if(max<=5) return 5; const p=Math.pow(10,Math.floor(Math.log10(max))), m=max/p; return (m<=1?1:m<=2?2:m<=2.5?2.5:m<=5?5:10)*p; }
function colorFor(dim, values){ // categorical slots in fixed order of the dimension; ordinal ramp for tiers and levels; "Other" grey
  const map={};
  if(dim==="tier"){ ["T0","T1","T2","T3","T4"].forEach((t,i)=>map[t]=`var(--o${i})`); map.U="var(--ou)"; return v=>map[v]||"var(--sother)"; }
  if(dim==="profile_level"){ Object.assign(map,{"No full Profile":"var(--ou)","Level 1":"var(--o1)","Level 2":"var(--o3)","Level 3":"var(--o4)"}); return v=>map[v]||"var(--sother)"; }
  values.filter(v=>v!=="Other").forEach((v,i)=>map[v]=i<8?`var(--s${i+1})`:"var(--sother)"); return v=>map[v]||"var(--sother)"; }

/* ---------- charts (inline SVG; hover tooltips; text in ink tokens) ---------- */
function stackedBars(el, dates, cats, data, color){
  const W=Math.max(320,el.clientWidth||700), H=280, m={l:44,r:12,t:22,b:30}, iw=W-m.l-m.r, ih=H-m.t-m.b;
  const tot=dates.map(d=>cats.reduce((a,c)=>a+(data[d][c]||0),0)), mx=Math.max(1,...tot), st=[1,2,2.5,5,10,20,25,50,100,200,250,500,1000].find(s=>Math.ceil(mx/s)<=5)||1000, nt=Math.ceil(mx/st), ymax=st*nt, y=v=>m.t+ih*(1-v/ymax);
  const step=iw/dates.length, bw=Math.min(72,step*.56); let g="";
  for(let i=0;i<=nt;i++){ const v=st*i; g+=`<line x1="${m.l}" x2="${W-m.r}" y1="${y(v)}" y2="${y(v)}" stroke="var(--grid)"/><text x="${m.l-8}" y="${y(v)+4}" text-anchor="end">${v}</text>`; }
  dates.forEach((d,i)=>{ const cx=m.l+step*(i+.5), x0=cx-bw/2; let cum=0;
    const segs=cats.filter(c=>data[d][c]);
    segs.forEach((c,j)=>{ const v=data[d][c], y1=y(cum+v), y0=y(cum), h=Math.max(0,y0-y1-(j?2:0)); cum+=v;
      const top=j===segs.length-1, r=Math.min(4,h/2);
      const path=top?`M${x0},${y1+h} V${y1+r} Q${x0},${y1} ${x0+r},${y1} H${x0+bw-r} Q${x0+bw},${y1} ${x0+bw},${y1+r} V${y1+h} Z`:`M${x0},${y1} h${bw} v${h} h${-bw} Z`;
      g+=`<path d="${path}" fill="${color(c)}" tabindex="0" data-tip="${esc(`${qLabel(d)} · ${c}\n${v} deployment${v===1?"":"s"} (${pct(v/tot[i])})`)}"/>`; });
    g+=`<text class="lbl" x="${cx}" y="${y(tot[i])-6}" text-anchor="middle">${tot[i]}</text><text x="${cx}" y="${H-8}" text-anchor="middle">${qLabel(d)}</text>`; });
  g+=`<line x1="${m.l}" x2="${W-m.r}" y1="${y(0)}" y2="${y(0)}" stroke="var(--axis)"/>`;
  el.innerHTML=`<div class="legend">${cats.map(c=>`<span><i style="background:${color(c)}"></i>${esc(c)}</span>`).join("")}</div><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Deployments by quarter">${g}</svg>`;
  bindTips(el); }
function lineChart(el, dates, series, label){
  const W=Math.max(320,el.clientWidth||700), H=280, m={l:44,r:120,t:16,b:30}, iw=W-m.l-m.r, ih=H-m.t-m.b;
  const ymax=Math.min(1,Math.max(.2,Math.ceil((Math.max(0,...series.flatMap(s=>s.values.filter(v=>v!=null)))+.05)*10)/10));
  const x=i=>m.l+(dates.length===1?iw/2:iw*i/(dates.length-1)), y=v=>m.t+ih*(1-v/ymax); let g="";
  for(let i=0;i<=4;i++){ const v=ymax*i/4; g+=`<line x1="${m.l}" x2="${W-m.r}" y1="${y(v)}" y2="${y(v)}" stroke="var(--grid)"/><text x="${m.l-8}" y="${y(v)+4}" text-anchor="end">${Math.round(v*100)}%</text>`; }
  dates.forEach((d,i)=>g+=`<text x="${x(i)}" y="${H-8}" text-anchor="middle">${qLabel(d)}</text>`);
  const ends=[];
  [...series].sort((a,b)=>(a.emph?1:0)-(b.emph?1:0)).forEach(s=>{ const pts=s.values.map((v,i)=>v==null?null:[x(i),y(v)]); let d="",pen=false;
    pts.forEach(p=>{ if(!p){pen=false;return;} d+=(pen?"L":"M")+p[0]+","+p[1]; pen=true; });
    g+=`<path d="${d}" fill="none" stroke="${s.color}" stroke-width="${s.emph?2.5:1.5}" ${s.dash?'stroke-dasharray="5 4"':""} stroke-linejoin="round" stroke-linecap="round"/>`;
    pts.forEach(p=>{ if(p&&s.emph) g+=`<circle cx="${p[0]}" cy="${p[1]}" r="4" fill="${s.color}" stroke="var(--surface)" stroke-width="2"/>`; });
    const li=s.values.map((v,i)=>v==null?-1:i).filter(i=>i>=0).pop(); if(li!=null&&li>=0&&(s.emph||s.label)) ends.push({y:y(s.values[li]),x:x(li),name:s.name,color:s.color,emph:s.emph}); });
  ends.sort((a,b)=>a.y-b.y); for(let i=1;i<ends.length;i++) if(ends[i].y-ends[i-1].y<14) ends[i].y=ends[i-1].y+14;
  ends.forEach(e=>g+=`<text class="${e.emph?"lbl":""}" x="${W-m.r+8}" y="${e.y+4}">${esc(e.name)}</text>`);
  g+=`<line x1="${m.l}" x2="${W-m.r}" y1="${y(0)}" y2="${y(0)}" stroke="var(--axis)"/><line id="xh" x1="0" x2="0" y1="${m.t}" y2="${m.t+ih}" stroke="var(--muted)" stroke-width="1" visibility="hidden"/>
    <rect x="${m.l-10}" y="${m.t}" width="${iw+20}" height="${ih}" fill="transparent" class="hit"/>`;
  el.innerHTML=`<div class="legend">${series.filter(s=>s.legend!==false).map(s=>`<span><i class="line" style="background:${s.color}${s.dash?";opacity:.8":""}"></i>${esc(s.name)}</span>`).join("")}</div><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(label)}">${g}</svg>`;
  const svg=el.querySelector("svg"), hit=el.querySelector(".hit"), xh=el.querySelector("#xh");
  hit.addEventListener("pointermove",ev=>{ const b=svg.getBoundingClientRect(), px=(ev.clientX-b.left)*W/b.width; let i=Math.round((px-m.l)/(dates.length>1?iw/(dates.length-1):1)); i=Math.max(0,Math.min(dates.length-1,i));
    xh.setAttribute("x1",x(i)); xh.setAttribute("x2",x(i)); xh.setAttribute("visibility","visible");
    const lines=series.map(s=>[s.values[i],s.name]).filter(a=>a[0]!=null).sort((a,b)=>b[0]-a[0]).map(([v,n])=>`${pct(v)}  ${n}`);
    showTip(ev,`${qLabel(dates[i])} · ${label}\n${lines.join("\n")}`); });
  hit.addEventListener("pointerleave",()=>{ tip.hidden=true; xh.setAttribute("visibility","hidden"); }); }
function stripRow(el, points, med, label){ // one metric: every firm as a dot on 0-100%, a median tick, outliers and the focus firm labelled
  const W=Math.max(260,el.clientWidth||600), H=66, m={l:10,r:10}, iw=W-m.l-m.r, x=v=>m.l+iw*v, cy=32; let g="";
  [0,.25,.5,.75,1].forEach(v=>g+=`<line x1="${x(v)}" x2="${x(v)}" y1="${cy-8}" y2="${cy+8}" stroke="var(--grid)"/><text x="${x(v)}" y="${H-2}" text-anchor="${v===0?"start":v===1?"end":"middle"}" style="font-size:11px">${v*100}%</text>`);
  g+=`<line x1="${m.l}" x2="${W-m.r}" y1="${cy}" y2="${cy}" stroke="var(--axis)"/>`;
  if(med!=null) g+=`<line x1="${x(med)}" x2="${x(med)}" y1="${cy-11}" y2="${cy+11}" stroke="var(--ink)" stroke-width="2"><title>median</title></line>`;
  const labs=points.filter(p=>p.out||p.hl).sort((a,b)=>a.v-b.v); let lastX=-1e9, flip=false;
  labs.forEach(p=>{ const px=x(p.v), w=p.name.length*6.6+10; flip=px-lastX<w?!flip:false; lastX=px; const ty=flip?cy+20:cy-12, anchor=px>W-80?"end":px<60?"start":"middle";
    g+=`<text class="lbl" x="${px}" y="${ty}" text-anchor="${anchor}" style="font-size:11.5px">${esc(p.name)}</text>`; });
  points.sort((a,b)=>(a.hl||a.out?1:0)-(b.hl||b.out?1:0)).forEach(p=>{ const c=p.concern?"var(--bad)":p.out?"var(--warn)":p.hl?"var(--accent)":"var(--muted)";
    g+=`<circle cx="${x(p.v)}" cy="${cy}" r="${p.hl||p.out?6:5}" fill="${c}" stroke="var(--surface)" stroke-width="2"/>`;
    g+=`<circle cx="${x(p.v)}" cy="${cy}" r="12" fill="transparent" tabindex="0" data-tip="${esc(`${p.name}: ${pct(p.v)}${p.detail?"\n"+p.detail:""}`)}"/>`; });
  el.innerHTML=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(label)}">${g}</svg>`; bindTips(el); }

/* ---------- views ---------- */
function vOverview(m){ const f=oneFirm(); return f?vFirm(m,f):vPortfolio(m); }
function feedProblems(){ const out=[]; for(const f of firms()) for(const x of f.snaps){ const md=DB.meta.get(x)||{findings:[],reasons:[]}; if(md.ok) continue;
    const errs=md.findings.filter(y=>y.severity==="error"); out.push({f,s:x,errs:errs.length?errs:(md.reasons||[]).map(m=>({message:m}))}); } return out; }
function vPortfolio(m){
  const rs=current(), prevDate=allDates().filter(d=>d<S.date).pop(), prs=prevDate?current({date:prevDate}):[], PT=peerTest(S.date), M=firmMetrics(S.date);
  const fp=feedProblems().filter(p=>scopeFirms().includes(p.f));
  const flagged=rs.filter(x=>x.sev===3);
  let h=`<div class="tiles">${tile("Firms reporting",scopeFirms().filter(f=>snapAt(f,S.date).cur).length,`${fp.length?`<span class="bad">${fp.length} feed problem${fp.length>1?"s":""}</span>`:"All feeds verified"}`)}
    ${tile("Deployments",rs.length,prevDate?`${rs.length-prs.length>=0?"+":""}${rs.length-prs.length} since ${qLabel(prevDate)}`:"")}
    ${tile("At tier T3, T4 or U",pct(share(rs,x=>["T3","T4","U"].includes(x.r.autonomy_tier))),"share of deployments shown")}
    ${tile("With a full Profile",pct(share(rs,x=>x.r.profile_level!=="none")),`${rs.filter(x=>["L2","L3"].includes(x.r.profile_level)).length} tested (Level 2+)`)}
    ${tile("High-severity flags",flagged.length,`<button class="linkbtn" data-f="severity|High|inventory">Show them</button>`)}</div>`;
  if(fp.length) h+=`<div class="disclosure" role="note"><p><strong>Quarantined snapshot${fp.length>1?"s":""}: not used in these figures.</strong> Each firm is shown at its last trusted snapshot.<br>${fp.map(p=>`${esc(p.f.short)}, snapshot ${esc(String(safeSnap(p.s).sequence??"?"))}: ${esc(p.errs[0].message)}${p.errs.length>1?` (and ${p.errs.length-1} more)`:""}`).join("<br>")} <button class="linkbtn" data-tab="feed">Open the feed view</button></p></div>`;
  const cols=["t3","cf","profile","tested","high","stale","conc"];
  h+=`<h3 class="sec">Firms</h3><p class="lead">Shares of production deployments at each firm's latest snapshot on or before ${fmtDate(S.date)}. A marked cell is far from the firm's peers (method under Outliers): red where that is a concern, grey where it is not. Select a firm to focus on it.</p>`;
  h+=tbl(["Firm","Peer group",["Snapshot","hide-sm"],["Production","num"],...cols.map(c=>[MET[c].short,"num"])],
    scopeFirms().map(f=>{ const mm=M.get(f.id), pt=PT.get(f.id)||{}, s=snapAt(f,S.date).cur; if(!mm) return "";
      return `<tr class="click" tabindex="0" data-scope="${esc(f.id)}"><td><b>${esc(f.short)}</b></td><td>${esc(f.peer)}</td><td class="hide-sm">${s?`#${esc(String(s.snapshot.sequence))} · ${fmtDate(s.snapshot.as_of)}`:"–"}</td><td class="num">${mm.n}</td>
      ${cols.map(c=>{ const t=pt[c]||{}; return `<td class="num">${pct(mm[c])}${t.out?`<span class="mark ${t.concern?"up":"neutral"}" title="${esc(`${t.dir==="up"?"Above":"Below"} the median of ${t.basis} (${pct(t.med)})`)}">${t.dir==="up"?"▲":"▼"}</span>`:""}</td>`; }).join("")}</tr>`; }).filter(Boolean));
  const cnt=FLAGS.map(fl=>({fl,n:rs.filter(x=>x.flags.includes(fl)).length})).filter(c=>c.n).sort((a,b)=>SEV_RANK[b.fl.sev]-SEV_RANK[a.fl.sev]||b.n-a.n);
  h+=`<div class="grid2"><div><h3 class="sec">Where to look first</h3>${tbl(["Severity","Flag",["Deployments","num"]],cnt.map(c=>`<tr class="click" tabindex="0" data-f="${esc(kj("flag",c.fl.label,"inventory"))}"><td>${sevChip(c.fl.sev)}</td><td>${esc(c.fl.label)}<div class="note">${esc(c.fl.why)}</div></td><td class="num">${c.n}</td></tr>`))}</div>
    <div><h3 class="sec">Model provider concentration</h3>${concentration(rs)}</div></div>`;
  m.innerHTML=h; }
function concentration(rs){ const c={}; rs.forEach(x=>providersOf(x.r).forEach(p=>c[p]=(c[p]||0)+1)); const tot=rs.length; const top=Object.entries(c).sort((a,b)=>b[1]-a[1]);
  if(!tot) return `<p class="empty">No deployments in this selection.</p>`;
  const warn=top.length&&top[0][1]/tot>.5;
  return `${warn?`<div class="disclosure" role="note"><p><strong>${esc(top[0][0])} underlies ${pct(top[0][1]/tot)} of these deployments</strong> across ${uniq(rs.filter(x=>providersOf(x.r).includes(top[0][0])).map(x=>x.firm.id)).length} firm(s). A single provider's outage or model change would reach all of them.</p></div>`:""}
  ${tbl(["Provider",["Deployments","num"],["Share","num"],"Firms"],top.map(([p,n])=>`<tr class="click" tabindex="0" data-f="${esc(kj("provider",p,"inventory"))}"><td>${esc(p)}</td><td class="num">${n}</td><td class="num">${pct(n/tot)}</td><td>${esc(uniq(rs.filter(x=>providersOf(x.r).includes(p)).map(x=>x.firm.short)).join(", "))}</td></tr>`))}`; }
function vFirm(m,f){
  const {cur,prev}=snapAt(f,S.date); if(!cur){ m.innerHTML=`<p class="empty">${esc(f.short)} has no snapshot on or before ${fmtDate(S.date)}.</p>`; return; }
  const rs=current(), PT=peerTest(S.date).get(f.id)||{}, meta=DB.meta.get(cur), errs=meta.findings.filter(x=>x.severity==="error");
  const dl=DELIVERY[f.delivery]||["–",""];
  let h=`<div class="card" style="margin-bottom:16px">${kv([["Firm",`<b>${esc(f.name)}</b> · <span class="mono">${esc(f.id)}</span>`],["Peer group",esc(f.peer)],["Delivery",`${esc(dl[0])} · <span class="note">${esc(dl[1])}</span>${f.endpoint?`<div class="mono note">${esc(f.endpoint)}</div>`:""}`],
    ["Latest snapshot",`#${esc(String(cur.snapshot.sequence))} · as of ${fmtDate(cur.snapshot.as_of)} · delivered ${fmtDate(String(cur.snapshot.produced_at).slice(0,10))} · ${cur.records.length} records`],
    ["Verification",errs.length?`<span class="chip c-bad">${errs.length} error${errs.length>1?"s":""}</span> <span class="note">${esc(errs[0].message)}</span> <button class="linkbtn" data-tab="feed">Details</button>`:`<span class="chip c-good">Signed, chained, conforms</span> <span class="note mono">${shortHash(meta.hash)}</span>`],
    ["Attested by",esc(`${cur.attestation.name}, ${cur.attestation.role}`)]])}</div>`;
  const M=firmMetrics(S.date).get(f.id)||{};
  h+=`<div class="tiles">${tile("Deployments shown",rs.length,prev?`${rs.length-current({date:prev.snapshot.as_of}).length>=0?"+":""}${rs.length-current({date:prev.snapshot.as_of}).length} since ${qLabel(prev.snapshot.as_of)}`:"")}
    ${["t3","profile","high","stale"].map(k=>{ const t=PT[k]||{}; return tile(MET[k].label,pct(M[k]),t.med!=null?`Peers ${pct(t.med)}${t.out?` <span class="mark ${t.concern?"up":"neutral"}">${t.dir==="up"?"▲ above":"▼ below"}</span>`:""}`:""); }).join("")}</div>`;
  h+=`<h3 class="sec">Compared with peers</h3><p class="lead">Each dot is a firm's share of production deployments. ${esc(f.short)} is labelled. Red marks an outlier in the concerning direction, amber one that is not; the black tick is the peer median. Peer group: ${esc((PT.t3||{}).basis||f.peer)}.</p><div id="peerstrips"></div>`;
  const cnt=FLAGS.map(fl=>({fl,n:rs.filter(x=>x.flags.includes(fl)).length})).filter(c=>c.n).sort((a,b)=>SEV_RANK[b.fl.sev]-SEV_RANK[a.fl.sev]||b.n-a.n);
  const ch=prev?changes(prev,cur):[];
  h+=`<div class="grid2"><div><h3 class="sec">Flags at this firm</h3>${tbl(["Severity","Flag",["Deployments","num"]],cnt.map(c=>`<tr class="click" tabindex="0" data-f="${esc(kj("flag",c.fl.label,"inventory"))}"><td>${sevChip(c.fl.sev)}</td><td>${esc(c.fl.label)}</td><td class="num">${c.n}</td></tr>`))}</div>
    <div><h3 class="sec">Since the previous snapshot</h3>${skipNote(f,cur,prev)?`<p class="note">${skipNote(f,cur,prev)}</p>`:""}${prev?tbl(["Change",["Count","num"]],Object.entries(CHANGE_KINDS).map(([k,l])=>[l,ch.filter(c=>c.kind===k).length,k]).filter(a=>a[1]).map(([l,n,k])=>`<tr class="click" tabindex="0" data-change="${k}"><td>${esc(l)}</td><td class="num">${n}</td></tr>`)):`<p class="empty">This is the firm's first snapshot.</p>`}</div></div>`;
  m.innerHTML=h;
  const PTall=peerTest(S.date), box=$("#peerstrips"); box.innerHTML=`<div class="strip">${METRICS.map(k=>`<div class="lab">${esc(k.label)}<span class="note">${esc(f.short)} ${pct((PT[k.id]||{}).v)} · peers ${pct((PT[k.id]||{}).med)}</span></div><div class="chart" data-strip="${k.id}"></div>`).join("")}</div>`;
  METRICS.forEach(k=>{ const pts=firms().filter(o=>PTall.get(o.id)).map(o=>{ const t=PTall.get(o.id)[k.id]; return {name:o.short,v:t.v||0,out:o===f&&t.out,concern:o===f&&t.concern,hl:o===f,detail:o.peer}; });
    stripRow(box.querySelector(`[data-strip="${k.id}"]`),pts,(PT[k.id]||{}).med,k.label); }); }
function vInventory(m){
  let rs=current(); const q=S.search.trim().toLowerCase();
  if(q) rs=rs.filter(x=>[x.firm.short,x.r.inventory_ref,x.r.agent_name,x.r.use_case,x.r.use_case_id,x.r.models,x.r.vendor_or_platform].join(" ").toLowerCase().includes(q));
  const keyf={firm:x=>x.firm.short,ref:x=>x.r.inventory_ref,name:x=>x.r.agent_name,status:x=>x.r.deployment_status,bl:x=>BL_LABEL[x.r.business_line],tier:x=>TIER_RANK[x.r.autonomy_tier],
    approval:x=>APR_RANK[x.r.human_approval],cf:x=>x.r.customer_facing,profile:x=>x.r.profile_level,sev:x=>x.sev*100+x.flags.length,review:x=>x.r.last_reviewed};
  const k=keyf[S.sort.key]||keyf.sev; rs=[...rs].sort((a,b)=>{ const A=k(a),B=k(b); return (A<B?-1:A>B?1:0)*S.sort.dir||a.r.inventory_ref.localeCompare(b.r.inventory_ref); });
  const head=[["firm","Firm"],["ref","Ref"],["name","Deployment"],["status","Status"],["bl","Business line"],["tier","Tier"],["approval","Approval"],["cf","Customer"],["profile","Profile"],["sev","Flags"],["review","Reviewed"]];
  m.innerHTML=`<div class="filters" style="padding-top:0"><label>Search<input type="search" id="q" value="${esc(S.search)}" placeholder="Name, ref, use case, model…"></label>
    <button class="btn" id="csv">Copy as CSV</button><span class="note">${rs.length} deployment${rs.length===1?"":"s"}</span></div>
    <div class="tablewrap"><table><thead><tr>${head.map(([id,l])=>`<th><button class="linkbtn" style="color:inherit;text-decoration:none" data-sort="${id}">${esc(l)}${S.sort.key===id?(S.sort.dir>0?" ↑":" ↓"):""}</button></th>`).join("")}</tr></thead><tbody>
    ${rs.map(x=>`<tr class="click" tabindex="0" data-drill="${esc(x.key)}"><td>${esc(x.firm.short)}</td><td class="mono">${esc(x.r.inventory_ref)}</td><td>${esc(x.r.agent_name)}<div class="note">${esc(x.r.use_case_id||"")} ${esc(x.r.use_case)}</div></td>
      <td>${esc(STATUS_LABEL[x.r.deployment_status])}</td><td>${esc(BL_LABEL[x.r.business_line])}</td><td class="mono">${esc(x.r.autonomy_tier)}${x.r.tier_basis==="substantiated"?"":'<span class="note"> asserted</span>'}</td>
      <td>${esc(APPROVAL_LABEL[x.r.human_approval])}</td><td>${x.r.customer_facing==="yes"?"Yes":"No"}</td><td>${x.r.profile_level==="none"?'<span class="note">None</span>':esc("Level "+x.r.profile_level[1])}</td>
      <td>${x.flags.length?(fs=>`<div tabindex="0" data-tip="${esc(fs.map(fl=>`${SEV_LABEL[fl.sev]}: ${fl.label}`).join("\n"))}">${sevChip(fs[0].sev)} <span class="note">${esc(fs[0].label)}${fs.length>1?` · +${fs.length-1} more`:""}</span></div>`)(x.flags.slice().sort((a,b)=>SEV_RANK[b.sev]-SEV_RANK[a.sev])):'<span class="note">–</span>'}</td>
      <td style="white-space:nowrap">${esc(x.r.last_reviewed)}</td></tr>`).join("")}</tbody></table></div>`;
  bindTips(m);
  const qi=$("#q"); qi.addEventListener("input",()=>{ S.search=qi.value; const pos=qi.selectionStart; vInventory(m); bindMain(m); const n=$("#q"); n.focus(); n.setSelectionRange(pos,pos); });
  m.querySelectorAll("[data-sort]").forEach(b=>b.addEventListener("click",()=>{ const id=b.dataset.sort; S.sort={key:id,dir:S.sort.key===id?-S.sort.dir:(id==="sev"||id==="tier"?-1:1)}; render(); }));
  $("#csv").addEventListener("click",async()=>{ const cols=["firm","firm_id","as_of","inventory_ref","agent_name","deployment_status","business_line","use_case_id","use_case","customer_facing","autonomy_tier","tier_basis","human_approval","permitted_actions","profile_level","full_profile_ref","models","vendor_or_platform","last_reviewed","flags"];
    const q2=v=>{ let s=String(v??""); if(/^[=+\-@\t\r]/.test(s)) s="'"+s; /* no live formulas when the CSV is opened in a spreadsheet */ return /[",\n\r]/.test(s)?`"${s.replace(/"/g,'""')}"`:s; };
    const txt=[cols.join(","),...rs.map(x=>[x.firm.short,x.firm.id,x.asOf,x.r.inventory_ref,x.r.agent_name,x.r.deployment_status,x.r.business_line,x.r.use_case_id,x.r.use_case,x.r.customer_facing,x.r.autonomy_tier,x.r.tier_basis,x.r.human_approval,x.r.permitted_actions.join(" "),x.r.profile_level,x.r.full_profile_ref,x.r.models,x.r.vendor_or_platform,x.r.last_reviewed,x.flags.map(f=>f.label).join("; ")].map(q2).join(","))].join("\n");
    try{ await navigator.clipboard.writeText(txt); toast(`Copied ${rs.length} rows as CSV`); }catch(e){ const t=document.createElement("textarea"); t.className="json"; t.value=txt; m.prepend(t); t.select(); toast("Press Ctrl/⌘+C to copy the selected CSV"); } }); }
const MEASURES = {count:"Deployments",pct_row:"% of row",pct_col:"% of column",profile:"% with a full Profile",t3:"% at tier T3, T4 or U",high:"% with a high-severity flag"};
function vExplore(m){
  const P=S.pivot, rs=current(), dimOpts=sel=>DIMS.map(d=>`<option value="${d.id}"${d.id===sel?" selected":""}>${esc(d.label)}</option>`).join("");
  const R=orderValues(P.rows,uniq(rs.flatMap(x=>vals(P.rows,x)))), C=P.cols==="none"?["All"]:orderValues(P.cols,uniq(rs.flatMap(x=>vals(P.cols,x))));
  const cell=(r,c)=>rs.filter(x=>vals(P.rows,x).includes(r)&&(P.cols==="none"||vals(P.cols,x).includes(c)));
  const rowSet=r=>rs.filter(x=>vals(P.rows,x).includes(r)), colSet=c=>P.cols==="none"?rs:rs.filter(x=>vals(P.cols,x).includes(c));
  const meas=(set,r,c)=>{ const n=set.length; switch(P.measure){ case "count": return n; case "pct_row": return r==null?null:n/Math.max(1,rowSet(r).length); case "pct_col": return c==null?null:n/Math.max(1,colSet(c).length);
    case "profile": return share(set,x=>x.r.profile_level!=="none"); case "t3": return share(set,x=>["T3","T4","U"].includes(x.r.autonomy_tier)); case "high": return share(set,x=>x.sev===3); } };
  const fmt=v=>v==null?"–":P.measure==="count"?String(v):pct(v);
  const grid=R.map(r=>C.map(c=>{ const set=cell(r,c); return {set,v:set.length?meas(set,r,P.cols==="none"?null:c):null}; }));
  const vmax=Math.max(0,...grid.flat().map(g=>g.v||0));
  const step=v=>!v||!vmax?0:Math.min(6,1+Math.floor(5.999*v/vmax));
  const multi=DIM[P.rows].multi||(P.cols!=="none"&&DIM[P.cols].multi);
  let h=`<div class="filters" style="padding-top:0"><label>Rows<select id="p-rows">${dimOpts(P.rows)}</select></label><label>Columns<select id="p-cols"><option value="none">(none)</option>${dimOpts(P.cols)}</select></label>
    <label>Show<select id="p-measure">${Object.entries(MEASURES).map(([k,l])=>`<option value="${k}"${k===P.measure?" selected":""}>${esc(l)}</option>`).join("")}</select></label>
    <button class="btn" id="p-swap">Swap rows and columns</button></div>
    <p class="lead">${rs.length} deployments in the current scope. Select a cell to list its deployments. Shading is relative to the largest cell.${multi?" A deployment can sit in more than one row or column for this field (it has several values), so totals count each deployment once.":""}</p>`;
  h+=`<div class="tablewrap"><table class="heat"><thead><tr><th>${esc(DIM[P.rows].label)}</th>${C.map(c=>`<th class="num">${esc(c)}</th>`).join("")}${P.cols!=="none"?`<th class="total">Total</th>`:""}</tr></thead><tbody>
    ${R.map((r,i)=>`<tr><th class="rowh">${esc(r)}</th>${C.map((c,j)=>{ const g=grid[i][j], s=step(g.v); return `<td class="cell" tabindex="0" data-cell="${i}|${j}" style="${s?`background:var(--h${s});color:var(--h${s}-ink)`:""}" data-tip="${esc(`${r}${P.cols!=="none"?" × "+c:""}\n${g.set.length} deployment${g.set.length===1?"":"s"}${P.measure!=="count"?" · "+fmt(g.v):""}`)}">${g.set.length?fmt(g.v):'<span class="note">·</span>'}</td>`; }).join("")}
      ${P.cols!=="none"?`<td class="total">${fmt(P.measure==="count"?rowSet(r).length:meas(rowSet(r),r,null)??(P.measure==="pct_row"?1:null))}</td>`:""}</tr>`).join("")}
    <tr><td class="total" style="text-align:left">Total</td>${C.map(c=>`<td class="total">${fmt(P.measure==="count"?colSet(c).length:P.measure==="pct_col"?1:P.measure==="pct_row"?colSet(c).length/Math.max(1,rs.length):meas(colSet(c),null,null))}</td>`).join("")}${P.cols!=="none"?`<td class="total">${fmt(P.measure==="count"?rs.length:P.measure.startsWith("pct")?1:meas(rs,null,null))}</td>`:""}</tr></tbody></table></div>`;
  m.innerHTML=h;
  $("#p-rows").addEventListener("change",e=>{ S.pivot.rows=e.target.value; render(); }); $("#p-cols").addEventListener("change",e=>{ S.pivot.cols=e.target.value; render(); });
  $("#p-measure").addEventListener("change",e=>{ S.pivot.measure=e.target.value; render(); });
  $("#p-swap").addEventListener("click",()=>{ if(P.cols==="none") return; [S.pivot.rows,S.pivot.cols]=[P.cols,P.rows]; render(); });
  m.querySelectorAll("[data-cell]").forEach(td=>{ const go=()=>{ const [i,j]=td.dataset.cell.split("|").map(Number); S.filters=S.filters.filter(f=>f.dim!==P.rows&&f.dim!==P.cols); S.filters.push({dim:P.rows,val:R[i]}); if(P.cols!=="none") S.filters.push({dim:P.cols,val:C[j]}); S.tab="inventory"; tip.hidden=true; render(); };
    td.addEventListener("click",go); td.addEventListener("keydown",e=>{ if(e.key==="Enter") go(); }); });
  bindTips(m); }
function vTrends(m){
  const dates=allDates(), T=S.trend, single=DIMS.filter(d=>!d.multi&&d.id!=="firm"&&d.id!=="peer"&&d.id!=="use_case");
  if(oneFirm()===null) single.unshift(DIM.firm);
  const data={}, all={}; dates.forEach(d=>{ data[d]={}; current({date:d}).forEach(x=>{ const v=vals(T.dim,x)[0]; data[d][v]=(data[d][v]||0)+1; all[v]=(all[v]||0)+1; }); });
  let cats=orderValues(T.dim,Object.keys(all));
  if(cats.length>8&&!DIM[T.dim].ordinal){ const keep=new Set(Object.entries(all).sort((a,b)=>b[1]-a[1]).slice(0,7).map(a=>a[0])); cats=cats.filter(c=>keep.has(c));
    dates.forEach(d=>{ let o=0; Object.keys(data[d]).forEach(k=>{ if(!keep.has(k)){ o+=data[d][k]; delete data[d][k]; } }); if(o) data[d].Other=o; }); cats.push("Other"); }
  const f=oneFirm();
  m.innerHTML=`<div class="filters" style="padding-top:0"><label>Break down by<select id="t-dim">${(T.dim==="firm"&&f?[DIM.firm,...single]:single).map(d=>`<option value="${d.id}"${d.id===T.dim?" selected":""}>${esc(d.label)}</option>`).join("")}</select></label></div>
    <h3 class="sec">Deployments by quarter</h3><p class="lead">Each firm's snapshot on or before each quarter end, with the scope and filters above.</p><div class="chart" id="c-bars"></div>
    <h3 class="sec">How each firm is moving</h3><div class="filters" style="padding-top:0"><label>Measure<select id="t-metric">${METRICS.map(k=>`<option value="${k.id}"${k.id===T.metric?" selected":""}>${esc(k.label)}</option>`).join("")}</select></label></div>
    <p class="lead">Share of each firm's production deployments. The dashed line is the median across all firms.${f?` ${esc(f.short)} is highlighted.`:""}</p><div class="chart" id="c-lines"></div>`;
  stackedBars($("#c-bars"),dates,cats,data,colorFor(T.dim,cats));
  const FM=dates.map(d=>firmMetrics(d)), fl=firms(), fcolor=colorFor("firm",fl.map(x=>x.short));
  const series=fl.map(x=>({name:x.short,values:FM.map(M=>{ const v=M.get(x.id); return v&&v.n?v[T.metric]:null; }),color:f?(x===f?"var(--s1)":"var(--axis)"):fcolor(x.short),emph:f?x===f:true,legend:!f||x===f,label:!f||x===f}));
  series.push({name:"Median, all firms",values:FM.map(M=>median([...M.values()].filter(v=>v.n&&v[T.metric]!=null).map(v=>v[T.metric]))),color:"var(--ink)",dash:true,label:true});
  lineChart($("#c-lines"),dates,series,MET[T.metric].label);
  $("#t-dim").addEventListener("change",e=>{ S.trend.dim=e.target.value; render(); }); $("#t-metric").addEventListener("change",e=>{ S.trend.metric=e.target.value; render(); }); }
function vOutliers(m){
  const PT=peerTest(S.date), rs=current(), fs=scopeFirms().filter(f=>PT.get(f.id));
  let h=`<h3 class="sec">Firms that stand out from their peers</h3><p class="lead">Each firm is compared with the median of the other firms in its peer group (all other firms when the group has fewer than three). It is marked when the gap is at least 15 points and at least three times the others' median absolute deviation. Red means the gap is in the concerning direction, amber that it is not; the black tick is the median of all firms shown. These are prompts for a supervisory conversation, not conclusions.</p>
    <div class="strip">${METRICS.map(k=>`<div class="lab">${esc(k.label)}<span class="note">${esc(fs.filter(f=>PT.get(f.id)[k.id].out).map(f=>`${f.short} ${PT.get(f.id)[k.id].dir==="up"?"▲":"▼"}`).join(", ")||"No outliers")}</span></div><div class="chart" data-strip="${k.id}"></div>`).join("")}</div>`;
  const fl=firms().filter(f=>scopeFirms().includes(f));
  h+=`<h3 class="sec">Deployment flags by firm</h3><p class="lead">Rule-based flags on each firm's reported records. Select a count to list the deployments.</p>`+
    tbl(["Severity","Flag",...fl.map(f=>[f.short,"num"]),["Total","num"]],FLAGS.map(F=>{ const by=fl.map(f=>rs.filter(x=>x.firm===f&&x.flags.includes(F)).length), t=by.reduce((a,b)=>a+b,0);
      return `<tr><td>${sevChip(F.sev)}</td><td>${esc(F.label)}<div class="note">${esc(F.why)}</div></td>${by.map((n,i)=>`<td class="num">${n?`<button class="linkbtn" data-ff="${esc(kj(fl[i].id,F.label))}">${n}</button>`:'<span class="note">·</span>'}</td>`).join("")}<td class="num"><b>${t}</b></td></tr>`; }));
  h+=`<h3 class="sec">Concentration</h3>${concentration(rs)}`;
  m.innerHTML=h;
  METRICS.forEach(k=>{ const pts=fs.map(f=>{ const t=PT.get(f.id)[k.id]; return {name:f.short,v:t.v||0,out:t.out,concern:t.concern,hl:false,detail:t.med!=null?`Median of ${t.basis}: ${pct(t.med)}`:""}; });
    stripRow(m.querySelector(`[data-strip="${k.id}"]`),pts,median(pts.map(p=>p.v)),k.label); });
  m.querySelectorAll("[data-ff]").forEach(b=>b.addEventListener("click",()=>{ const [fid,lab]=ks(b.dataset.ff); S.scope=fid; addFilter("flag",lab,"inventory"); })); }
const CHANGE_KINDS = {vanished:"Disappeared without being retired",tier_up:"Autonomy tier increased",approval_down:"Human approval reduced",actions_added:"New permitted action classes",
  control_worse:"Control status weakened",profile_gone:"Full Profile withdrawn",added:"New deployment",to_production:"Moved into production",profile_new:"Full Profile issued or changed",
  control_better:"Control status strengthened",approval_up:"Human approval increased",tier_down:"Autonomy tier decreased",retired:"Retired"};
function changes(prev,cur){ const out=[], pm=new Map(prev.records.map(e=>[e.record.inventory_ref,e])), cm=new Map(cur.records.map(e=>[e.record.inventory_ref,e]));
  const add=(kind,r,before,after)=>out.push({kind,ref:r.inventory_ref,name:r.agent_name,before,after});
  for(const [ref,e] of cm){ const r=e.record, pe=pm.get(ref); if(!pe){ add("added",r,"",STATUS_LABEL[r.deployment_status]); continue; } const p=pe.record;
    if(r.deployment_status!==p.deployment_status){ if(r.deployment_status==="production") add("to_production",r,STATUS_LABEL[p.deployment_status],"Production"); if(r.deployment_status==="retired") add("retired",r,STATUS_LABEL[p.deployment_status],"Retired"); }
    if(TIER_RANK[r.autonomy_tier]>TIER_RANK[p.autonomy_tier]) add("tier_up",r,p.autonomy_tier,r.autonomy_tier); else if(r.autonomy_tier!==p.autonomy_tier) add("tier_down",r,p.autonomy_tier,r.autonomy_tier);
    if(APR_RANK[r.human_approval]<APR_RANK[p.human_approval]) add("approval_down",r,APPROVAL_LABEL[p.human_approval],APPROVAL_LABEL[r.human_approval]); else if(APR_RANK[r.human_approval]>APR_RANK[p.human_approval]) add("approval_up",r,APPROVAL_LABEL[p.human_approval],APPROVAL_LABEL[r.human_approval]);
    const na=r.permitted_actions.filter(a=>!p.permitted_actions.includes(a)); if(na.length) add("actions_added",r,"",na.join(", "));
    const a=(e.profile||{}).sha256, b=(pe.profile||{}).sha256; if(a&&a!==b) add("profile_new",r,b?(pe.profile.profile_id):"None",`${e.profile.profile_id} (Level ${e.profile.headline})`); if(!a&&b) add("profile_gone",r,pe.profile.profile_id,"None");
    for(const c of PEER){ const x=r.controls[c], y=p.controls[c]; if(x===y||x==="not_applicable"||y==="not_applicable") continue;
      add(CTL_RANK[x]<CTL_RANK[y]?"control_worse":"control_better",r,`${(CTL[c]||{}).label||c}: ${CTL_LABEL[y]}`,CTL_LABEL[x]); } }
  for(const [ref,pe] of pm) if(!cm.has(ref)&&pe.record.deployment_status!=="retired") add("vanished",pe.record,STATUS_LABEL[pe.record.deployment_status],"Not in the snapshot");
  return out; }
/* When a snapshot between two trusted ones is quarantined, changes are computed against the last trusted snapshot and labelled
   (FEED.md §10). Snapshots after an unresolved fork are themselves quarantined (INV-030), so no change is computed across a fork. */
function skipNote(f,cur,prev){ if(!cur||!prev||cur.snapshot.sequence===prev.snapshot.sequence+1) return "";
  return `${esc(f.short)}: snapshot #${esc(String(cur.snapshot.sequence))} is compared with #${esc(String(prev.snapshot.sequence))}, the last trusted snapshot before it; the snapshot${cur.snapshot.sequence-prev.snapshot.sequence>2?"s":""} in between ${cur.snapshot.sequence-prev.snapshot.sequence>2?"are":"is"} quarantined.`; }
function vChanges(m){
  const fs=scopeFirms(); const all=[], notes=[];
  fs.forEach(f=>{ const {cur,prev}=snapAt(f,S.date); const n=skipNote(f,cur,prev); if(n) notes.push(n); if(cur&&prev) changes(prev,cur).forEach(c=>all.push({...c,f,from:prev.snapshot.as_of,to:cur.snapshot.as_of})); });
  const kinds=Object.entries(CHANGE_KINDS).map(([k,l])=>[k,l,all.filter(c=>c.kind===k).length]);
  const shown=S.change==="all"?all:all.filter(c=>c.kind===S.change);
  const order=Object.keys(CHANGE_KINDS);
  m.innerHTML=`<p class="lead">What changed between each firm's latest trusted snapshot on or before ${fmtDate(S.date)} and the trusted one before it. No request was needed: both snapshots came through the feed.</p>
    ${notes.length?`<div class="disclosure" role="note"><p><strong>Compared with the last trusted snapshot.</strong> ${notes.join("<br>")}</p></div>`:""}
    <div class="filters" style="padding-top:0"><label>Show<select id="c-kind"><option value="all">All changes (${all.length})</option>${kinds.filter(k=>k[2]).map(([k,l,n])=>`<option value="${k}"${k===S.change?" selected":""}>${esc(l)} (${n})</option>`).join("")}</select></label></div>
    ${tbl(["Firm","Ref","Deployment","Change","Before","After"],shown.sort((a,b)=>order.indexOf(a.kind)-order.indexOf(b.kind)||a.f.short.localeCompare(b.f.short)).map(c=>`<tr class="click" tabindex="0" data-drill="${esc(kj(c.f.id,c.ref))}"><td>${esc(c.f.short)}</td><td class="mono">${esc(c.ref)}</td><td>${esc(c.name)}</td>
      <td>${c.kind==="vanished"?'<span class="chip c-bad">':["tier_up","approval_down","control_worse","actions_added"].includes(c.kind)?'<span class="chip c-warn">':'<span class="chip c-neutral">'}${esc(CHANGE_KINDS[c.kind])}</span></td><td>${esc(c.before)}</td><td>${esc(c.after)}</td></tr>`))}`;
  $("#c-kind").addEventListener("change",e=>{ S.change=e.target.value; render(); }); }
function vFeed(m){
  let h=DB.rejected.length?`<h3 class="sec">Files that could not be used</h3>${tbl(["File","Rule","Finding"],DB.rejected.map(x=>`<tr><td class="mono">${esc(x.name)}</td><td class="mono">INV-001</td><td>${esc(x.message)}</td></tr>`))}`:"";
  h+=`<p class="lead">How each firm's inventory reaches this console. Whatever the route, the object is the same signed, hash-chained snapshot (spec/FEED.md), and the console runs the same checks on it.</p>
  <div class="flow" aria-label="How snapshots flow"><div class="node"><b>Firm</b>Keeps its agent inventory as Profile Lite records, with commitments to full Profiles</div><div class="arrow" aria-hidden="true">→</div>
    <div class="node"><b>Signed snapshot</b>Signed by the firm and chained to the previous snapshot by hash, so history cannot be rewritten silently</div><div class="arrow" aria-hidden="true">→</div>
    <div class="node"><b>Pull, push or file</b>The supervisor reads the firm's endpoint, the firm posts to the supervisor's endpoint, or the file comes through a portal</div><div class="arrow" aria-hidden="true">→</div>
    <div class="node"><b>This console</b>Checks every snapshot (INV-001 to INV-040), then derives the cuts, trends, changes and flags</div></div>`;
  for(const f of scopeFirms()){ const dl=DELIVERY[f.delivery]||["–",""];
    h+=`<h3 class="sec">${esc(f.short)} <span class="note" style="font:400 13px var(--font-body)">${esc(f.id)} · ${esc(dl[0])}${f.registered?"":" · not in the key register"}</span></h3>
    <p class="note" style="margin:0 0 8px">${esc(dl[1])}${f.endpoint?` <span class="mono">${esc(f.endpoint)}</span> <button class="btn" data-pull="${esc(f.id)}" style="margin-left:6px;padding:3px 10px">Pull now</button>`:""}</p>`+
    tbl([["#","num"],"As of","Delivered",["Lag","num"],["Records","num"],"Hash","Checks"],f.snaps.slice().reverse().map(s=>{ const md=DB.meta.get(s)||{findings:[]}, e=md.findings.filter(x=>x.severity==="error"), w=md.findings.filter(x=>x.severity!=="error"), sm=safeSnap(s), ok=md.ok;
      return `<tr><td class="num">${esc(String(sm.sequence??"?"))}</td><td>${fmtDate(sm.as_of)}</td><td>${fmtDate(typeof sm.produced_at==="string"?sm.produced_at.slice(0,10):sm.produced_at)}</td><td class="num">${ok?days(sm.produced_at.slice(0,10),sm.as_of)+" d":"–"}</td><td class="num">${ok?s.records.length:"–"}</td><td class="mono">${esc(shortHash(md.hash))}</td>
      <td>${e.length?`<span class="chip c-bad">${e.length} error${e.length>1?"s":""}</span>`:ok?`<span class="chip c-good">Signed, chained, conforms</span>`:""}${ok?"":` <span class="chip c-bad">${md.unverifiable&&!e.length?"Unverified":"Quarantined"} · not shown in any view</span>`}${w.length?` <span class="chip c-warn">${w.length} warning${w.length>1?"s":""}</span>`:""}
      ${md.findings.length?`<ul class="msgs">${md.findings.map(x=>`<li><span class="mono">${esc(x.rule)}</span> ${esc(x.message)}</li>`).join("")}</ul>`:""}</td></tr>`; })); }
  h+=`<h3 class="sec">Add snapshots</h3><p class="note">Open snapshot files (and any full Profile documents) with <b>Open snapshot files…</b> above, or read a firm's endpoint. In this hosted page the browser cannot reach other sites, so <b>Pull now</b> shows what would be requested; run the console inside the supervisor's network for live pulls.</p>`;
  m.innerHTML=h;
  m.querySelectorAll("[data-pull]").forEach(b=>b.addEventListener("click",()=>pull(DB.firms.get(b.dataset.pull)))); }
async function pull(f){ const url=f.endpoint.replace(/\/$/,"")+"/inventory"; let n=0, refused=[];
  try{ if(acceptPulled(f.id,f.endpoint,url)) throw new Error("the register's endpoint is not a valid address");
    const r=await fetch(url,{headers:{Accept:"application/json"}}); if(!r.ok) throw new Error(`HTTP ${r.status}`); const idx=parseStrict(await r.text());
    const have=new Set(shown(f).map(x=>x.snapshot.sequence));
    for(const s of (idx&&Array.isArray(idx.snapshots)?idx.snapshots:[])){ if(!s||have.has(s.sequence)) continue;
      const why=acceptPulled(f.id,f.endpoint,String(s.href||"")); if(why){ refused.push(why); continue; }
      const sr=await fetch(new URL(String(s.href),url)); const snap=parseStrict(await sr.text());
      const why2=acceptPulled(f.id,f.endpoint,String(s.href),snap); if(why2){ refused.push(why2); continue; }
      if(await addSnapshot(snap)) n++; }
    await recheckAll(); render(); toast(`Pulled ${n} new snapshot${n===1?"":"s"} from ${f.short}${refused.length?`; refused ${refused.length}: ${refused[0]}`:""}`); }
  catch(e){ toast(`Could not reach ${url} (${e.message}). Expected: GET /inventory, then each new /inventory/{sequence}.`); } }
function vDrill(m){
  const [fid,ref]=ks(S.drill), f=DB.firms.get(fid), x=rowsAt(S.date).find(y=>y.key===S.drill)||rowsAt(allDates().slice(-1)[0]).find(y=>y.key===S.drill);
  if(!x){ m.innerHTML=`<p class="empty">This deployment is not in ${esc(f?f.short:"the firm")}'s snapshot at this date.</p><button class="btn" id="back">← Back</button>`; $("#back").addEventListener("click",()=>{ S.drill=null; render(); }); return; }
  const r=x.r, hist=shown(f).map(s=>({s,e:s.records.find(e=>e.record.inventory_ref===ref)}));
  const actChips=V.actions.map(a=>`<span class="chip ${r.permitted_actions.includes(a.id)?"c-good":"c-neutral"}" title="${esc(a.label)}" style="margin:0 4px 4px 0">${a.id}${r.permitted_actions.includes(a.id)?"":" ✕"}</span>`).join("");
  let h=`<div class="drill-head"><div><button class="linkbtn" id="back">← Back</button><h2>${esc(r.agent_name)}</h2><div class="note">${esc(f.name)} · <span class="mono">${esc(ref)}</span> · snapshot #${esc(String(x.snap.snapshot.sequence))}, as of ${fmtDate(x.asOf)}</div></div>
    <div>${x.flags.length?x.flags.map(fl=>`<div>${sevChip(fl.sev)} ${esc(fl.label)}</div>`).join(""):'<span class="chip c-good">No flags</span>'}</div></div>`;
  if(x.flags.length) h+=`<div class="card" style="margin-bottom:14px"><h2>Why it is flagged</h2>${x.flags.map(fl=>`<p style="margin:4px 0">${sevChip(fl.sev)} <b>${esc(fl.label)}.</b> ${esc(fl.why)}</p>`).join("")}</div>`;
  h+=`<div class="grid2"><div><h3 class="sec">As reported</h3>${kv([["Status",esc(STATUS_LABEL[r.deployment_status])],["Business line",esc(BL_LABEL[r.business_line])],["Use case",esc(`${r.use_case_id?r.use_case_id+" · ":""}${r.use_case}`)],
    ["Customer-facing",r.customer_facing==="yes"?"Yes":"No"],["Autonomy tier",`<span class="mono">${esc(r.autonomy_tier)}</span> · ${esc((V.tiers.find(t=>t.id===r.autonomy_tier)||{}).label||"")} · ${r.tier_basis==="substantiated"?chip("substantiated","c-good"):chip("asserted","c-warn")}`],
    ["Human approval",esc(APPROVAL_LABEL[r.human_approval])],["Action classes",`<div>${actChips}</div><div class="note">Green: permitted. Grey ✕: prohibited.</div>`],["Models",esc(r.models||"Not stated")],["Vendor or platform",esc(r.vendor_or_platform||"Not stated")],
    ["Accountable owner",esc(r.accountable_owner_role)],["Last reviewed",`${esc(r.last_reviewed)} <span class="note">(${days(x.asOf,r.last_reviewed)} days before as-of)</span>`]])}</div>
    <div><h3 class="sec">Peer-set controls</h3><div class="ctlgrid">${PEER.map(c=>`<div><span>${esc((CTL[c]||{}).label||c)}</span>${chip(CTL_LABEL[r.controls[c]]||"Unknown",CTL_CHIP[r.controls[c]]||"c-warn")}</div>`).join("")}</div>
    <p class="note">As reported by the firm. "Tested, held" is backed by a Level 2 or 3 full Profile; anything else is the firm's statement.</p></div></div>`;
  h+=`<h3 class="sec">History in the feed</h3>`+tbl(["Snapshot","Status","Tier","Approval","Full Profile","Controls at configured or better"],hist.map(({s,e})=>e?`<tr${s===x.snap?' style="font-weight:600"':""}><td>#${esc(String(s.snapshot.sequence))} · ${fmtDate(s.snapshot.as_of)}</td><td>${esc(STATUS_LABEL[e.record.deployment_status])}</td><td class="mono">${esc(e.record.autonomy_tier)}</td><td>${esc(APPROVAL_LABEL[e.record.human_approval])}</td><td>${e.profile?esc(`${e.profile.profile_id} · L${e.profile.headline}`):'<span class="note">None</span>'}</td><td>${PEER.filter(c=>(CTL_RANK[e.record.controls[c]]||0)>=3).length} of ${PEER.filter(c=>e.record.controls[c]!=="not_applicable").length}</td></tr>`:`<tr><td>#${esc(String(s.snapshot.sequence))} · ${fmtDate(s.snapshot.as_of)}</td><td colspan="5" class="note">Not in this snapshot</td></tr>`));
  const dv=((DB.meta.get(x.snap)||{}).findings||[]).filter(fi=>fi.rule==="INV-023"&&fi.severity==="warning"&&fi.message.startsWith(r.inventory_ref+":"));
  h+=`<h3 class="sec">Full Profile</h3>`;
  if(dv.length) h+=`<div class="disclosure" role="note"><p><strong>Declared divergence.</strong> ${esc(dv[0].message.slice(r.inventory_ref.length+2))} The record above, not the full Profile, is what the firm reports today.</p></div>`;
  if(!x.p) h+=`<p class="empty">The firm reports no full Profile for this deployment. The record above is the firm's own statement; nothing in it has been tested.</p>`;
  else { const doc=DB.objects.get(x.p.sha256);
    h+=kv([["Committed Profile",`<span class="mono">${esc(x.p.profile_id)}</span> · ${esc(x.p.stage)} · Level ${esc(String(x.p.headline))}`],["Valid until",esc(x.p.valid_until||"–")+(x.p.valid_until&&x.p.valid_until<x.asOf?` ${chip("expired","c-bad")}`:"")],["Hash",`<span class="mono">${esc(x.p.sha256)}</span>`]]);
    h+=doc?`<div id="pstatus" style="margin:10px 0"></div><div class="profile-embed" id="pview"></div>`:`<p class="note">The Profile document is not in this feed. ${f.endpoint?`Pull mode: <span class="mono">GET ${esc(f.endpoint)}/objects/${esc(x.p.sha256.slice(7))}</span>; the console accepts it only if its hash matches the commitment.`:`Ask the firm to deposit it (push: <span class="mono">PUT …/objects/${esc(x.p.sha256.slice(7,19))}…</span>), or open the file here.`}</p>`; }
  m.innerHTML=h; $("#back").addEventListener("click",()=>{ S.drill=null; render(); });
  if(x.p&&DB.objects.get(x.p.sha256)){ const doc=DB.objects.get(x.p.sha256); check(doc).then(fd=>{ const e=fd.filter(z=>z.severity==="error");
    $("#pstatus").innerHTML=`${e.length?chip(`${e.length} conformance error${e.length>1?"s":""}`,"c-bad"):chip(`Hash matches the commitment · well-formed under ${D.spec} (not a judgement of the agent)`,"c-good")} <span class="note">Checked in this browser with the same checker as the Profile Viewer.</span>`;
    renderProfile($("#pview"),doc,fd); }); } }

/* ---------- frame ---------- */
const VIEWS = {overview:vOverview,inventory:vInventory,explore:vExplore,trends:vTrends,outliers:vOutliers,changes:vChanges,feed:vFeed};
function renderBadges(){
  $("#sample-badge").hidden=!DB.sample;
  $("#register-info").innerHTML=DB.registry?`Key register: <b>${esc(DB.registerName)}</b> · ${Object.keys(DB.registry).length} firm${Object.keys(DB.registry).length===1?"":"s"}`:`<span class="bad">No key register loaded: signers cannot be checked</span>`;
  $("#sample-note").hidden=!DB.sample;
  const q=quarantined(), unv=q.filter(x=>x.md.unverifiable), tb=$("#trust-banner");
  const rj=DB.rejected.length, rjNote=rj?` ${rj} opened file${rj>1?"s":""} could not be used (INV-001; listed in the Feed view).`:"";
  if(tb){ tb.hidden=!q.length&&!rj;
    tb.innerHTML=!q.length?(rj?`<p><strong>Files not used.</strong>${rjNote} <button class="linkbtn" data-tab="feed">Feed view</button></p>`:""):unv.length?`<p><strong>Verification unavailable.</strong> This browser cannot verify Ed25519 signatures, so ${unv.length} snapshot${unv.length>1?"s are":" is"} treated as unverified and kept out of every total, trend and outlier. Use a current browser, or check the feed with <span class="mono">arp_feed.py chain</span>.${q.length>unv.length?` ${q.length-unv.length} more ${q.length-unv.length>1?"are":"is"} quarantined for failed checks.`:""} <button class="linkbtn" data-tab="feed">Feed view</button></p>`
      :`<p><strong>${q.length} snapshot${q.length>1?"s are":" is"} quarantined</strong> because ${q.length>1?"they fail":"it fails"} verification or the feed checks. Quarantined data is listed only in the Feed view and is not used in positions, totals, trends, outliers or changes; each firm is shown at its last trusted snapshot.${rjNote} <button class="linkbtn" data-tab="feed">Feed view</button></p>`;
    tb.querySelectorAll("[data-tab]").forEach(el=>el.addEventListener("click",()=>{ S.tab=el.dataset.tab; S.drill=null; render(); })); } }
function renderFrame(){
  const ds=allDates(); if(!S.date||!ds.includes(S.date)) S.date=ds[ds.length-1];
  const peers=uniq(firms().map(f=>f.peer));
  $("#f-scope").innerHTML=`<option value="all">All firms (${firms().length})</option>${peers.map(p=>`<option value="peer:${esc(p)}">Peer group: ${esc(p)}</option>`).join("")}<optgroup label="Firm">${firms().map(f=>`<option value="${esc(f.id)}">${esc(f.short)}</option>`).join("")}</optgroup>`;
  $("#f-scope").value=S.scope; $("#f-date").innerHTML=ds.slice().reverse().map(d=>`<option value="${esc(d)}">${fmtDate(d)} · ${qLabel(d)}</option>`).join(""); $("#f-date").value=S.date; $("#f-status").value=S.status;
  $("#f-chips").innerHTML=S.filters.map((f,i)=>`<span class="fchip">${esc(DIM[f.dim].label)}: ${esc(f.val)}<button aria-label="Remove filter" data-rm="${i}">×</button></span>`).join("")+(S.filters.length>1?`<button class="linkbtn" id="clearf">Clear all</button>`:"");
  const flagged=current().filter(x=>x.sev===3).length, fp=feedProblems().filter(p=>scopeFirms().includes(p.f)).length;
  $("#tabs").innerHTML=TABS.map(([id,l])=>`<button class="tab" role="tab" aria-selected="${S.tab===id&&!S.drill}" data-tab="${id}">${l}${id==="inventory"?`<span class="count">${current().length}</span>`:id==="outliers"&&flagged?`<span class="count">${flagged} high</span>`:id==="feed"&&fp?`<span class="count" style="color:var(--bad)">${fp} problem</span>`:""}</button>`).join("");
  $("#f-chips").querySelectorAll("[data-rm]").forEach(b=>b.addEventListener("click",()=>{ S.filters.splice(Number(b.dataset.rm),1); render(); }));
  const cl=$("#clearf"); if(cl) cl.addEventListener("click",()=>{ S.filters=[]; render(); });
  $("#tabs").querySelectorAll("[data-tab]").forEach(b=>b.addEventListener("click",()=>{ S.tab=b.dataset.tab; S.drill=null; render(); })); }
function bindMain(m){
  m.querySelectorAll("[data-scope]").forEach(el=>{ const go=()=>{ S.scope=el.dataset.scope; render(); }; el.addEventListener("click",go); el.addEventListener("keydown",e=>{ if(e.key==="Enter") go(); }); });
  m.querySelectorAll("[data-drill]").forEach(el=>{ const go=()=>{ S.drill=el.dataset.drill; render(); scrollTo(0,0); }; el.addEventListener("click",go); el.addEventListener("keydown",e=>{ if(e.key==="Enter") go(); }); });
  m.querySelectorAll("[data-f]").forEach(el=>{ const go=()=>{ const [d,v,t]=ks(el.dataset.f); addFilter(d,v,t); }; el.addEventListener("click",go); el.addEventListener("keydown",e=>{ if(e.key==="Enter") go(); }); });
  m.querySelectorAll("[data-tab]").forEach(el=>el.addEventListener("click",()=>{ S.tab=el.dataset.tab; S.drill=null; render(); }));
  m.querySelectorAll("[data-change]").forEach(el=>{ const go=()=>{ S.change=el.dataset.change; S.tab="changes"; render(); }; el.addEventListener("click",go); el.addEventListener("keydown",e=>{ if(e.key==="Enter") go(); }); }); }
function vEmpty(m){ m.innerHTML=`<div class="card empty-state"><h2>No feed loaded</h2>
  <p>Load your key register first (it says which signing key belongs to which firm), then open the firms' snapshot files and any full Profile documents. Everything stays in this browser.</p>
  <p>To explore first, load the sample feed: five fictional firms, four quarterly snapshots each, with problems planted on purpose.</p>
  <div class="btns" style="display:flex;gap:10px;flex-wrap:wrap"><button class="btn" data-act="sample">Load sample (fictional) feed</button><label class="btn" for="regfile">Load key register…</label><label class="btn" for="files">Open snapshot files…</label></div></div>`;
  m.querySelector('[data-act="sample"]').addEventListener("click",()=>$("#reset").click()); }
function render(){ tip.hidden=true; renderBadges(); const m=$("#main");
  if(!firms().length&&!DB.rejected.length){ $("#tabs").innerHTML=""; $("#f-chips").innerHTML=""; $("#f-scope").innerHTML=""; $("#f-date").innerHTML=""; vEmpty(m); return; }
  if(!allDates().length){ S.tab="feed"; S.drill=null; }
  renderFrame(); if(S.drill) vDrill(m); else VIEWS[S.tab](m); bindMain(m); }
$("#f-scope").addEventListener("change",e=>{ S.scope=e.target.value; S.drill=null; render(); });
$("#f-date").addEventListener("change",e=>{ S.date=e.target.value; render(); });
$("#f-status").addEventListener("change",e=>{ S.status=e.target.value; render(); });
$("#reset").addEventListener("click",async()=>{ await loadSample(); S.tab="overview"; render(); toast("Sample feed loaded: all firms, keys and data are fictional"); });
$("#regfile").addEventListener("change",async e=>{ const file=e.target.files[0]; e.target.value=""; if(!file) return; let j;
  try{ j=parseStrict(await file.text()); }catch(err){ toast(`${file.name} is not valid JSON (${err.message})`); return; }
  if(classifyFile(j)!=="register"){ toast(`${file.name} is not a key register (it needs a "firms" list)`); return; }
  if(DB.sample){ clearAll(); toast("Sample data cleared"); }
  setRegister(j,file.name); await recheckAll(); render(); toast(`Key register loaded from ${file.name}: ${Object.keys(DB.registry).length} firms`); });
/* Files from the picker. A file that is not strict JSON, or is neither a snapshot nor a Profile, is listed in the Feed view
   with an INV-001 finding (FEED.md §6); key registers are refused here (they load only through Load key register…). */
async function openFiles(files){ let ns=0,np=0,bad=0,regs=0;
  if(DB.sample){ clearAll(); toast("Sample data cleared before opening your files"); }
  for(const file of files){ let j, k;
    try{ j=parseStrict(await file.text()); k=classifyFile(j); }
    catch(err){ DB.rejected.push({name:String(file.name),message:`not strict JSON: ${err.message}`}); bad++; continue; }
    if(k==="snapshot"){ if(await addSnapshot(j)) ns++; } else if(k==="profile"){ await addObject(j); np++; } else if(k==="register") regs++;
    else { DB.rejected.push({name:String(file.name),message:"neither an inventory snapshot nor a Profile"}); bad++; } }
  await recheckAll(); if(bad&&!firms().length){ S.tab="feed"; S.drill=null; } render();
  toast(`Added ${ns} snapshot${ns===1?"":"s"} and ${np} Profile${np===1?"":"s"}${bad?`; ${bad} file(s) could not be used (see the Feed view)`:""}${regs?`; ${regs} key register file(s) ignored: use Load key register…`:""}`); }
$("#files").addEventListener("change",async e=>{ const fl=[...e.target.files]; e.target.value=""; await openFiles(fl); });
let rz; addEventListener("resize",()=>{ clearTimeout(rz); rz=setTimeout(()=>{ if(["trends","outliers","overview"].includes(S.tab)||S.drill) render(); },200); });
window.ARPConsole={ready:Promise.resolve().then(()=>render()),trustOf,quarantined,feedProblems,openFiles,CRYPTO_OK,loadSample,addSnapshot,addObject,setRegister,recheckAll,clearAll,checkSnapshot,checkFeed,classifyFile,acceptPulled,parseStrict,changes,rowsAt,peerTest,firmMetrics,DB,S,render,FLAGS};
