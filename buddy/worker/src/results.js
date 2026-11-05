// Ballot Buddy results: pulls every state's Nov 3 results, puts them in one shape, keeps the last good copy in KV.
//
// Sources, best first:
//   FL  Division of Elections results file (county by county)
//   NC  State Board of Elections feed
//   CA  Secretary of State API
//   all civicAPI (free, no key): every state's list, race calls, local races and county breakdowns
// An official number always beats civicAPI's. civicAPI's race call is kept beside it, because a state's feed says what
// is counted, not who won. A source that fails keeps the last good copy and is named in /api/results/health.
//
// KV (BALLOT_BUDDY): results:<ST> {state file} · results:<ST>:counties {contest id: county table} · results:US · results:meta
export const ELECTION = "2026-11-03";
export const STATE_NAMES = {AL: "Alabama", AK: "Alaska", AZ: "Arizona", AR: "Arkansas", CA: "California", CO: "Colorado", CT: "Connecticut", DE: "Delaware", DC: "District of Columbia", FL: "Florida", GA: "Georgia", HI: "Hawaii", ID: "Idaho", IL: "Illinois", IN: "Indiana", IA: "Iowa", KS: "Kansas", KY: "Kentucky", LA: "Louisiana", ME: "Maine", MD: "Maryland", MA: "Massachusetts", MI: "Michigan", MN: "Minnesota", MS: "Mississippi", MO: "Missouri", MT: "Montana", NE: "Nebraska", NV: "Nevada", NH: "New Hampshire", NJ: "New Jersey", NM: "New Mexico", NY: "New York", NC: "North Carolina", ND: "North Dakota", OH: "Ohio", OK: "Oklahoma", OR: "Oregon", PA: "Pennsylvania", RI: "Rhode Island", SC: "South Carolina", SD: "South Dakota", TN: "Tennessee", TX: "Texas", UT: "Utah", VT: "Vermont", VA: "Virginia", WA: "Washington", WV: "West Virginia", WI: "Wisconsin", WY: "Wyoming"};
export const PRIORITY = ["FL", "AL", "NJ", "CA", "NC"];     // refreshed on every tick; the other states take turns
// A state's automatic or requestable recount margin, in points. Only states checked by hand are listed.
const RECOUNT = {FL: 0.5, NC: 1};
// Statewide ballot questions that need more than a simple majority.
const MEASURE_NEED = {FL: 60};
const UA = {"user-agent": "BallotBuddy/1.0 (election results; ballotbuddy.appolis.app)"};
const CIVIC = "https://civicapi.org/api/v2/race";

export const fold = s => String(s ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const tokens = s => fold(s).replace(/"[^"]*"|\([^)]*\)/g, " ").replace(/\b(jr|sr|ii|iii|iv)\b\.?/g, " ").replace(/[^a-z' -]/g, " ").split(/[\s-]+/).filter(Boolean);
const lastTok = n => tokens(n).slice(-1)[0] || "";
const slug = s => fold(s).replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
const num = v => +String(v ?? "").replace(/[^0-9.]/g, "") || 0;
const round1 = n => Math.round(n * 10) / 10, round2 = n => Math.round(n * 100) / 100;
const PARTY = {republican: "R", rep: "R", democratic: "D", democrat: "D", dem: "D", libertarian: "L", lib: "L", lpf: "L", green: "G", grn: "G", gre: "G", independent: "I", ind: "I", npa: "NPA", nonpartisan: "", "no party": "NPA", una: "U", wri: "WI", "write-in": "WI"};
const party = p => { const k = fold(p).trim(); return k in PARTY ? PARTY[k] : String(p ?? "").trim().slice(0, 12); };
const titleCase = s => String(s).toLowerCase().replace(/(^|[\s(/-])([a-z])/g, (m, a, b) => a + b.toUpperCase()).replace(/\b(Us|Nc|Ii|Iii|Iv|Dc)\b/g, m => m.toUpperCase()).replace(/\b(Of|The|And|For|In|To)\b/g, m => m.toLowerCase()).replace(/^./, m => m.toUpperCase());
// "District 16", "FL-16", "FL-HD-073", "16", "US House 16", "State Senate 40". An at-large seat is district 1.
const distOf = (...xs) => { for (const x of xs) { const t = String(x ?? "").trim(); if (/at[- ]large|^[A-Z]{2}-AL$/i.test(t)) return 1; const m = /(?:district|dist\.?)\s*0*(\d+)/i.exec(t) || /(?:^|-)0*(\d+)$/.exec(t) || /\b(?:house|senate)\s+0*(\d+)\b/i.exec(t); if (m) return +m[1]; } return null; };
const judSlug = s => slug(String(s).replace(/^(north carolina|california|florida|alabama|new jersey|nc)\s+/i, "").replace(/\b0+(\d)/g, "$1"));

async function getText(fetcher, url) {
  const r = await fetcher(url, {headers: UA, redirect: "follow"});
  if (!r.ok) throw new Error(`${r.status} from ${new URL(url).host}`);
  return r.text();
}
async function getJson(fetcher, url) {
  const t = await getText(fetcher, url);
  try { return JSON.parse(t); } catch (e) { throw new Error(`not JSON from ${new URL(url).host}: ${t.slice(0, 80)}`); }
}

// ---------- civicAPI ----------
const OFFICE_KEY = [[/^governor$/i, "gov"], [/lieutenant governor/i, "ltgov"], [/attorney general/i, "ag"], [/secretary of state/i, "sos"], [/chief financial/i, "cfo"], [/commissioner of agriculture/i, "agcomm"], [/treasurer/i, "treas"], [/controller/i, "controller"], [/auditor/i, "auditor"], [/insurance commissioner/i, "insurance"], [/superintendent/i, "superintendent"]];
function civicClass(r) {
  const T = r.type || "", N = r.election_name || "", scope = r.election_type || "";
  const d = distOf(r.district, N);
  if (/^(us senate|senate)$/i.test(T) || /\bus senate\b/i.test(N)) return {lvl: "fed", key: "ussen"};
  if (/^house of representatives$/i.test(T) || /\bus house\b/i.test(N)) return {lvl: "fed", key: d != null ? `ushouse-${d}` : `x-${r.id}`};
  if (/^state senate$/i.test(T)) return scope === "Statewide" ? {lvl: "chamber", key: "chamber-stsen"} : {lvl: "leg", key: d != null ? `stsen-${d}` : `x-${r.id}`};
  if (/^state house$/i.test(T)) return scope === "Statewide" ? {lvl: "chamber", key: "chamber-sthouse"} : {lvl: "leg", key: d != null ? `sthouse-${d}` : `x-${r.id}`};
  if (/^referendum$/i.test(T)) {
    const stw = scope === "Statewide";
    return {lvl: stw ? "measure" : "local", measure: true, key: stw ? `measure-${measureSlug(N)}` : `x-${r.id}`};
  }
  if (/^(judicial|judiciary)$/i.test(T)) {
    const ret = /(?:justice|judge)\s+(.+?)\s+retention\b/i.exec(N);
    return ret ? {lvl: "jud", measure: true, key: "ret-" + lastTok(ret[1])} : {lvl: "jud", key: "jud-" + judSlug(N)};
  }
  for (const [re, k] of OFFICE_KEY) if (re.test(T) && scope === "Statewide") return {lvl: "top", key: k};
  return {lvl: "local", key: `x-${r.id}`};
}
function measureSlug(n) {
  const m = /(?:amendment|proposition|prop\.?|question)(?: no\.?)?\s*0*(\d+)/i.exec(n);
  if (m) return m[1];
  return slug(n.replace(/constitutional amendment\s*-?/i, "").replace(/^(north carolina|california|florida|alabama|new jersey)\s*/i, ""));
}
function civicContest(r, st) {
  const k = civicClass(r), nm = STATE_NAMES[st] || "";
  let t = String(r.election_name || "").replace(new RegExp("^" + nm + "\\s+", "i"), "").trim();
  const dn = /-(\d+)$/.exec(k.key);
  if (k.key === "ussen") t = /special/i.test(t) ? "U.S. Senate (special election)" : "U.S. Senate";
  else if (/^ushouse-/.test(k.key)) t = /at[- ]large|-AL$/i.test(t + " " + (r.district || "")) ? "U.S. House, At Large" : "U.S. House, District " + dn[1];
  else if (/^stsen-/.test(k.key)) t = "State Senate, District " + dn[1];
  else if (/^sthouse-/.test(k.key)) t = (st === "CA" ? "State Assembly" : "State House") + ", District " + dn[1];
  const c = (r.candidates || []).filter(x => (party(x.party) !== "WI" && !/^write-?ins?$/i.test(x.name || "")) || x.votes).map(x => ({n: x.name, p: party(x.party), v: +x.votes || 0, pc: +x.percent || 0, ...(x.winner ? {w: 1} : {}), ...(x.incumbent ? {inc: 1} : {}), ...(x.seats != null ? {seats: x.seats} : {})}));
  return {id: "c" + r.id, key: k.key, t, lvl: k.lvl, type: r.type, ...(r.district ? {dist: r.district} : {}), ...(k.measure ? {m: 1} : {}), rp: r.percent_reporting ?? null, c, src: "civicAPI", civic: r.id, ...(r.seats ? {seats: r.seats} : {})};
}
async function civicSearch(fetcher, params) {
  // One big page on purpose: its row order shifts between calls, so stepping through 500 at a time silently drops races.
  const out = new Map(), limit = 5000;
  for (let offset = 0, page = 0; page < 4; page++, offset += limit) {
    const q = new URLSearchParams({...params, election_date: ELECTION, limit, offset});
    const j = await getJson(fetcher, `${CIVIC}/search?${q}`);
    const rows = j.races || [];
    for (const r of rows) out.set(r.id, r);
    if (rows.length < limit) break;
  }
  return [...out.values()].filter(r => String(r.election_date || "").startsWith(ELECTION) && r.election_type !== "Primary" && !r.test_data);
}
export async function civicState(fetcher, st) {
  const rows = await civicSearch(fetcher, {province: st});
  if (!rows.length) throw new Error(`civicAPI returned no ${st} races`);
  return rows.map(r => civicContest(r, st));
}

// ---------- official feeds ----------
// The cache in front of this file serves a stale pre-election copy, all zeros, to a request without the v= the state's own page adds.
const FL_FILE = "https://flelectionfiles.floridados.gov/enightfilespublic/20261103_ElecResultsFL.txt";
export async function flOfficial(fetcher) {
  const lines = (await getText(fetcher, FL_FILE + "?v=" + Math.floor(Date.now() / 60000))).split(/\r?\n/);
  const H = lines[0].split("\t"), I = n => H.indexOf(n);
  for (const n of ["RaceCode", "RaceName", "CountyName", "CanNameLast", "CanVotes", "Precincts", "PrecinctsReporting"]) if (I(n) < 0) throw new Error("Florida's results file changed: no column " + n);
  const races = new Map();
  for (const l of lines.slice(1)) {
    const c = l.split("\t");
    if (c.length < H.length - 1) continue;
    const code = c[I("RaceCode")].trim(), name = c[I("RaceName")].trim(), id = code + "|" + name;
    let R = races.get(id);
    if (!R) races.set(id, R = {code, name, cands: new Map(), counties: {}, prec: {}});
    const county = c[I("CountyName")].trim();
    R.prec[county] = [num(c[I("Precincts")]), num(c[I("PrecinctsReporting")])];
    const first = c[I("CanNameFirst")].trim(), mid = c[I("CanNameMiddle")].trim(), last = c[I("CanNameLast")].trim();
    const nm = /^yes\b/i.test(last) ? "Yes" : /^no\b/i.test(last) ? "No" : [first, mid, last].filter(Boolean).join(" ");   // a ticket reads "Donalds / Avila"
    const P = c[I("PartyCode")].trim();
    let K = R.cands.get(nm);
    if (!K) R.cands.set(nm, K = {n: nm, p: party(P), v: 0, last, first});
    const v = num(c[I("CanVotes")]);
    K.v += v;
    (R.counties[county] = R.counties[county] || {})[nm] = v;
  }
  const contests = [], counties = {};
  const allVotes = [...races.values()].reduce((a, R) => a + [...R.cands.values()].reduce((b, k) => b + k.v, 0), 0);
  if (!allVotes) throw new Error("Florida's results file shows zero votes (a stale copy)");
  for (const R of races.values()) {
    if (!R.cands.size) continue;
    const d = distOf(R.name);
    let lvl = "local", key = "fl-" + slug(R.code + "-" + R.name), t = R.name, m = 0, need;
    const simple = {USS: ["fed", "ussen", "U.S. Senate"], GOV: ["top", "gov", "Governor"], ATG: ["top", "ag", "Attorney General"], CFO: ["top", "cfo", "Chief Financial Officer"], AGR: ["top", "agcomm", "Commissioner of Agriculture"]}[R.code];
    if (simple) [lvl, key, t] = simple;
    else if (R.code === "USR") { lvl = "fed"; key = `ushouse-${d}`; t = `U.S. House, District ${d}`; }
    else if (R.code === "STS") { lvl = "leg"; key = `stsen-${d}`; t = `State Senate, District ${d}`; }
    else if (R.code === "STR") { lvl = "leg"; key = `sthouse-${d}`; t = `State House, District ${d}`; }
    else if (R.code === "AMD") { lvl = "measure"; m = 1; need = MEASURE_NEED.FL; key = `measure-${measureSlug(R.name)}`; const n = measureSlug(R.name); t = /^\d+$/.test(n) ? `Amendment ${n}` : R.name; }
    else if (R.code === "SCJ" || R.code === "DCA") {
      lvl = "jud"; m = 1; need = 50;
      const who = /(?:Justice|Judge)\s+(.+?)\s+be retained/i.exec(R.name);
      key = `ret-${lastTok(who ? who[1] : R.name)}`;
      t = who ? `Keep ${who[1]}?` : R.name;
    } else if (R.code === "CTJ") {
      lvl = "jud";
      const q = /(\d+)\w* Judicial Circuit, Group (\d+)/i.exec(R.name);
      if (q) key = "jud-circuit-judge-circuit-" + q[1] + "-group-" + q[2];
    }
    const cands = [...R.cands.values()];
    const total = cands.reduce((a, k) => a + k.v, 0);
    const P = Object.values(R.prec);
    const pt = P.reduce((a, x) => a + x[0], 0), pr = P.reduce((a, x) => a + x[1], 0);
    const c = cands.filter(k => k.p !== "WI" || k.v).sort((a, b) => b.v - a.v).map(k => ({n: k.n, p: k.p, v: k.v, pc: total ? round2(k.v / total * 100) : 0}));
    const id = "fl-" + slug(key.startsWith("fl-") ? key.slice(3) : key);
    contests.push({id, key, t, lvl, ...(m ? {m: 1} : {}), ...(need ? {need} : {}), rp: pt ? round1(pr / pt * 100) : null, c, src: "Florida Division of Elections"});
    counties[id] = R.counties;
  }
  return {contests, counties, source: {name: "Florida Division of Elections", url: "https://floridaelectionwatch.gov/"}};
}

const NC_FEED = "https://er.ncsbe.gov/enr/20261103/data/results_0.txt";
export async function ncOfficial(fetcher) {
  const rows = await getJson(fetcher, NC_FEED);
  const by = new Map();
  for (const r of rows) { const k = r.gid + "|" + r.cnm; if (!by.has(k)) by.set(k, []); by.get(k).push(r); }
  const contests = [];
  for (const rs of by.values()) {
    const r0 = rs[0], raw = r0.cnm.replace(/\s*\(VOTE FOR \d+\)\s*$/i, "").trim(), ogl = r0.ogl, d = distOf(raw);
    let lvl = "local", key = "nc-" + r0.gid, t = titleCase(raw), m = 0;
    if (/^US SENATE/i.test(raw)) { lvl = "fed"; key = "ussen"; t = "U.S. Senate"; }
    else if (/^US HOUSE/i.test(raw)) { lvl = "fed"; key = `ushouse-${d}`; t = `U.S. House, District ${d}`; }
    else if (ogl === "NCS") { lvl = "leg"; key = `stsen-${d}`; t = `State Senate, District ${d}`; }
    else if (ogl === "NCH") { lvl = "leg"; key = `sthouse-${d}`; t = `State House, District ${d}`; }
    else if (ogl === "JUD") { lvl = "jud"; key = "jud-" + judSlug(raw); }
    else if (/^CONSTITUTIONAL AMENDMENT/i.test(raw)) { lvl = "measure"; m = 1; key = "measure-" + measureSlug(titleCase(raw)); t = titleCase(raw.replace(/^CONSTITUTIONAL AMENDMENT\s*-\s*/i, "")); }
    else if (String(r0.ref) === "1") { m = 1; }
    const c = rs.map(x => ({n: x.bnm.trim(), p: party(x.pty), v: num(x.vct), pc: round2(num(x.pct) * 100)})).filter(x => x.p !== "WI" || x.v).sort((a, b) => b.v - a.v);
    if (m) for (const x of c) x.n = /^for$/i.test(x.n) ? "Yes" : /^against$/i.test(x.n) ? "No" : x.n;
    const pt = num(r0.ptl), pr = num(r0.prt);
    const vf = +r0.vfr || 1;
    contests.push({id: "nc-" + slug(key.startsWith("nc-") ? key.slice(3) : key), key, t, lvl, ...(m ? {m: 1} : {}), ...(vf > 1 ? {vf} : {}), rp: pt ? round1(pr / pt * 100) : null, c, src: "NC State Board of Elections"});
  }
  return {contests, counties: {}, source: {name: "NC State Board of Elections", url: "https://er.ncsbe.gov/?election_dt=11/03/2026"}};
}

const CA = "https://api.sos.ca.gov/returns";
const CA_TOP = [["governor", "gov", "Governor"], ["lieutenant-governor", "ltgov", "Lieutenant Governor"], ["secretary-of-state", "sos", "Secretary of State"], ["controller", "controller", "Controller"], ["treasurer", "treas", "Treasurer"], ["attorney-general", "ag", "Attorney General"], ["insurance-commissioner", "insurance", "Insurance Commissioner"]];
const caRp = s => { const m = /(\d+(?:\.\d+)?)%/.exec(s || ""); return m ? +m[1] : null; };
const caRace = (j, id, key, t, lvl) => ({id, key, t, lvl, rp: caRp(j.Reporting), c: (j.candidates || []).map(x => ({n: x.Name, p: party(x.Party), v: num(x.Votes), pc: num(x.Percent), ...(x.incumbent ? {inc: 1} : {})})).filter(x => x.n).sort((a, b) => b.v - a.v), src: "California Secretary of State"});
export async function caOfficial(fetcher) {
  const contests = [];
  for (const [path, key, t] of CA_TOP) contests.push(caRace(await getJson(fetcher, `${CA}/${path}`), "ca-" + key, key, t, "top"));
  const dist = async (path, pre, label, lvl) => {
    const j = await getJson(fetcher, `${CA}/${path}/district/all`);
    for (const x of Object.values(j)) {
      const d = distOf(x.raceTitle); if (d == null) continue;
      contests.push(caRace(x, `ca-${pre}-${d}`, `${pre}-${d}`, `${label}, District ${d}`, lvl));
    }
  };
  await dist("us-rep", "ushouse", "U.S. House", "fed");
  await dist("state-senate", "stsen", "State Senate", "leg");
  await dist("state-assembly", "sthouse", "State Assembly", "leg");
  const bm = await getJson(fetcher, `${CA}/ballot-measures`);
  for (const x of bm["ballot-measures"] || []) {
    const n = +x.Number, y = num(x.yesVotes), no = num(x.noVotes);
    contests.push({id: "ca-prop-" + n, key: `measure-${n}`, t: `Proposition ${n}: ${String(x.Name).replace(/\s*(Legislative|Initiative)[^.]*\.\s*$/i, "").replace(/\.$/, "")}`, lvl: "measure", m: 1, rp: caRp(bm.Reporting), c: [{n: "Yes", p: "", v: y, pc: num(x.yesPercent)}, {n: "No", p: "", v: no, pc: num(x.noPercent)}], src: "California Secretary of State"});
  }
  return {contests, counties: {}, source: {name: "California Secretary of State", url: "https://electionresults.sos.ca.gov/"}};
}
const OFFICIAL = {FL: flOfficial, NC: ncOfficial, CA: caOfficial};

// ---------- put the two together ----------
function sameCand(a, b) {
  const la = lastTok(a), lb = lastTok(b);
  if (!la || !lb) return false;
  return la === lb || tokens(a).includes(lb) || tokens(b).includes(la);
}
function decide(c, st) {
  const margin = c.c.length > 1 ? round2(c.c[0].pc - c.c[1].pc) : null;
  const fin = c.rp != null && c.rp >= 100;
  if (c.m) {
    const yes = c.c.find(x => /^(yes|for)\b/i.test(x.n)), no = c.c.find(x => /^(no|against)\b/i.test(x.n));
    if (!yes || !no) return;
    const need = c.need || 50;
    const called = yes.w || no.w;
    c.need = need;
    delete yes.w; delete no.w;
    const clear = Math.abs(yes.pc - need) >= 1;
    if ((called || (fin && st !== "CA")) && clear) c.res = yes.pc >= need ? "passed" : "failed";
    else c.res = null;
    return;
  }
  if (c.c.length === 1 && !c.c[0].w) c.c[0].w = 1;
  const vf = c.vf || 1, called = c.c.filter(x => x.w).length > 0;
  const rc = RECOUNT[st];
  // A state's feed doesn't call races. When nothing else has, a finished count with a clear margin is a win, and California
  // never gets one this way because its mail ballots keep arriving after every precinct has reported.
  if (!called && fin && st !== "CA" && c.c.length > vf && c.c[vf - 1].pc - c.c[vf].pc > (rc ?? .5)) for (const x of c.c.slice(0, vf)) { x.w = 1; x.ap = 1; }
  if (rc != null && margin != null && margin <= rc && vf === 1) c.close = rc;
}
export function merge(st, civic, official) {
  const byKey = new Map(), audit = {compared: 0, off: []};
  for (const x of civic) if (!byKey.has(x.key)) byKey.set(x.key, x);
  const used = new Set(), out = [];
  for (const o of official?.contests || []) {
    let z = byKey.get(o.key);
    // No shared label (Florida's file numbers no amendments): the same names with nearly the same votes is the same contest.
    if (!z) z = civic.find(x => !used.has(x.id) && x.c.length === o.c.length && !!x.m === !!o.m && o.c.every(k => { const q = x.c.find(y => fold(y.n) === fold(k.n) || (!o.m && sameCand(y.n, k.n))); return q && k.v > 50 && Math.abs(q.v - k.v) / k.v < .03; }));
    if (z) {
      used.add(z.id);
      o.civic = z.civic;
      if (o.lvl === "measure" && /^measure-\d+$/.test(z.key)) { o.key = z.key; o.t = z.t; }
      if (o.key === "gov" && st === "FL") for (const k of o.c) { const hit = z.c.find(y => sameCand(y.n, k.n)); if (hit) k.n = hit.n; }
      for (const k of o.c) {
        const hits = z.c.filter(y => sameCand(y.n, k.n));
        if (hits.length !== 1) continue;
        const h = hits[0];
        if (h.w) k.w = 1;
        if (h.inc) k.inc = 1;
        audit.compared++;
        if (k.v > 1000 && Math.abs(h.v - k.v) / k.v > .02) audit.off.push({t: o.t, n: k.n, official: k.v, civic: h.v});
      }
    }
    out.push(o);
  }
  for (const x of civic) if (!used.has(x.id)) out.push(x);
  for (const c of out) {
    if (c.m && c.lvl === "measure" && !c.need && MEASURE_NEED[st]) c.need = MEASURE_NEED[st];
    if (c.lvl !== "chamber") decide(c, st);
  }
  return {contests: out, audit};
}

export async function buildState(fetcher, st) {
  const errors = [];
  let civic = [], official = null;
  try { civic = await civicState(fetcher, st); } catch (e) { errors.push("civicAPI: " + e.message); }
  if (OFFICIAL[st]) try { official = await OFFICIAL[st](fetcher); } catch (e) { errors.push(st + " official feed: " + e.message); }
  if (!civic.length && !official) throw new Error(errors.join("; "));
  const {contests, audit} = merge(st, civic, official);
  const file = {
    st, name: STATE_NAMES[st], election: ELECTION,
    sources: [...(official ? [official.source] : []), ...(civic.length ? [{name: "civicAPI", url: "https://civicapi.org/"}] : [])],
    contests: contests.filter(c => c.lvl !== "chamber"), chambers: contests.filter(c => c.lvl === "chamber"), audit,
  };
  return {file, counties: official?.counties || {}, errors};
}

// The whole country at a glance: Governor, U.S. Senate and U.S. House in every state.
export async function buildNation(fetcher) {
  const rows = [];
  for (const type of ["Governor", "Senate", "US Senate", "House of Representatives"]) rows.push(...await civicSearch(fetcher, {type}));
  const seen = new Set(), races = [];
  for (const r of rows) {
    if (seen.has(r.id) || !STATE_NAMES[r.province]) continue;
    seen.add(r.id);
    const c = civicContest(r, r.province);
    if (!["gov", "ussen"].includes(c.key) && !/^ushouse-/.test(c.key)) continue;
    decide(c, r.province);
    races.push({st: r.province, ...c});
  }
  if (!races.length) throw new Error("civicAPI returned no national races");
  return {election: ELECTION, races, sources: [{name: "civicAPI", url: "https://civicapi.org/"}]};
}

// ---------- storage + cron ----------
const hashOf = async s => [...new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s)))].slice(0, 8).map(b => b.toString(16).padStart(2, "0")).join("");
async function metaOf(env) { return JSON.parse(await env.BALLOT_BUDDY.get("results:meta") || "null") || {states: {}, tick: 0}; }
const voteSum = body => (body.contests || body.races || []).reduce((a, c) => a + c.c.reduce((b, k) => b + (k.v || 0), 0), 0);
async function store(env, meta, st, body, now) {
  const s = JSON.stringify(body), h = await hashOf(s), m = meta.states[st] = meta.states[st] || {}, votes = voteSum(body);
  // Vote totals only climb after an election. A big drop means a bad pull, so the last good copy stays.
  if (m.votes && votes < m.votes * .9) throw new Error("refused: " + votes + " votes is far below the last good " + m.votes);
  m.votes = votes;
  if (m.hash !== h) { await env.BALLOT_BUDDY.put("results:" + st, s); m.hash = h; m.changed = now; }
  m.checked = now; delete m.error;
}
export async function refresh(env, fetcher, opts = {}) {
  const meta = await metaOf(env), now = new Date().toISOString();
  const others = Object.keys(STATE_NAMES).filter(s => !PRIORITY.includes(s));
  meta.tick = (meta.tick + 1) % 1e6;
  const turn = opts.states || [...PRIORITY, ...[0, 1, 2].map(i => others[(meta.tick * 3 + i) % others.length])];
  for (const st of turn) {
    try {
      const {file, counties, errors} = await buildState(fetcher, st);
      await store(env, meta, st, file, now);
      if (Object.keys(counties).length) {
        const s = JSON.stringify(counties), h = await hashOf(s);
        if (meta.states[st].chash !== h) { await env.BALLOT_BUDDY.put(`results:${st}:counties`, s); meta.states[st].chash = h; }
      }
      if (errors.length) meta.states[st].error = errors.join("; ");
    } catch (e) {
      console.error("results", st, e && e.message);
      (meta.states[st] = meta.states[st] || {}).error = String(e && e.message || e);
    }
  }
  try { await store(env, meta, "US", await buildNation(fetcher), now); }
  catch (e) { console.error("results US", e && e.message); (meta.states.US = meta.states.US || {}).error = String(e && e.message || e); }
  meta.ran = now;
  await env.BALLOT_BUDDY.put("results:meta", JSON.stringify(meta));
  return meta;
}

const J = (status, body, age = 60) => new Response(typeof body === "string" ? body : JSON.stringify(body), {status, headers: {"content-type": "application/json", "cache-control": `public, max-age=${age}`}});
// GET /api/results/health · /api/results/US · /api/results/<ST> · /api/results/<ST>/counties/<contest id> · /api/results/race/<civic id>
export async function resultsApi(env, fetcher, path, ctx) {
  const KV = env.BALLOT_BUDDY, parts = path.split("/").filter(Boolean).slice(2);
  if (parts[0] === "health") {
    const m = await metaOf(env), states = Object.entries(m.states).map(([st, x]) => ({st, checked: x.checked || null, changed: x.changed || null, error: x.error || null}));
    return J(200, {ok: !states.some(x => PRIORITY.includes(x.st) && x.error), ran: m.ran || null, states}, 30);
  }
  if (parts[0] === "race" && /^\d+$/.test(parts[1] || "")) {
    const cache = caches.default, key = new Request("https://bb.internal/race/" + parts[1]);
    const hit = await cache.match(key);
    if (hit) return hit;
    try {
      const j = await getJson(fetcher, `${CIVIC}/${parts[1]}`);
      const regions = {};
      for (const x of Object.values(j.region_results || {})) if (x.fips) regions[x.fips] = {n: x.name, rp: x.percent_reporting ?? null, c: (x.candidates || []).map(k => ({n: k.name, p: party(k.party), v: +k.votes || 0, pc: +k.percent || 0}))};
      const res = J(200, {regions, src: "civicAPI"}, 300);
      ctx && ctx.waitUntil(cache.put(key, res.clone()));
      return res;
    } catch (e) { console.error("race", parts[1], e && e.message); return J(502, {error: "The county breakdown isn't available right now."}, 0); }
  }
  const st = (parts[0] || "").toUpperCase();
  if (st !== "US" && !STATE_NAMES[st]) return J(404, {error: "not found"}, 0);
  if (parts[1] === "counties" && parts[2]) {
    const all = JSON.parse(await KV.get(`results:${st}:counties`) || "null");
    return all && all[parts[2]] ? J(200, {counties: all[parts[2]]}) : J(404, {error: "no county table for that race"}, 60);
  }
  const m = await metaOf(env), row = m.states[st];
  let s = await KV.get("results:" + st);
  if (!s) {
    // A state the rotation hasn't reached yet: build it for this visitor and keep it.
    try {
      const body = st === "US" ? await buildNation(fetcher) : (await buildState(fetcher, st)).file;
      s = JSON.stringify(body);
      await KV.put("results:" + st, s);
      return J(200, `{"checked":${JSON.stringify(new Date().toISOString())},"changed":null,"problem":null,"data":${s}}`);
    } catch (e) { console.error("results first build", st, e && e.message); return J(503, {error: "not ready yet", st}, 30); }
  }
  return J(200, `{"checked":${JSON.stringify(row?.checked || null)},"changed":${JSON.stringify(row?.changed || null)},"problem":${JSON.stringify(row?.error || null)},"data":${s}}`);
}
