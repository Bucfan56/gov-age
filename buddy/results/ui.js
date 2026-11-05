// Ballot Buddy results tracker. Loaded ahead of the app's own script, and shares its globals (API, D, ALL, PICKS, ctx, esc, $, openSheet, ordered, lines).
const RES = {st: null, files: {}, view: "all", q: "", shown: 30, layer: "gov", timer: null};
const RES_TABS = [["US", "🌎 Country"], ["FL", "Florida"], ["AL", "Alabama"], ["NJ", "New Jersey"], ["CA", "California"], ["NC", "North Carolina"]];
const RES_NAMES = {AL: "Alabama", AK: "Alaska", AZ: "Arizona", AR: "Arkansas", CA: "California", CO: "Colorado", CT: "Connecticut", DE: "Delaware", DC: "District of Columbia", FL: "Florida", GA: "Georgia", HI: "Hawaii", ID: "Idaho", IL: "Illinois", IN: "Indiana", IA: "Iowa", KS: "Kansas", KY: "Kentucky", LA: "Louisiana", ME: "Maine", MD: "Maryland", MA: "Massachusetts", MI: "Michigan", MN: "Minnesota", MS: "Mississippi", MO: "Missouri", MT: "Montana", NE: "Nebraska", NV: "Nevada", NH: "New Hampshire", NJ: "New Jersey", NM: "New Mexico", NY: "New York", NC: "North Carolina", ND: "North Dakota", OH: "Ohio", OK: "Oklahoma", OR: "Oregon", PA: "Pennsylvania", RI: "Rhode Island", SC: "South Carolina", SD: "South Dakota", TN: "Tennessee", TX: "Texas", UT: "Utah", VT: "Vermont", VA: "Virginia", WA: "Washington", WV: "West Virginia", WI: "Wisconsin", WY: "Wyoming", US: "the whole country"};
const RES_GRID = {AK: [0, 0], ME: [10, 0], VT: [9, 1], NH: [10, 1], WA: [0, 2], ID: [1, 2], MT: [2, 2], ND: [3, 2], MN: [4, 2], IL: [5, 2], WI: [6, 2], MI: [7, 2], NY: [8, 2], RI: [9, 2], MA: [10, 2], OR: [0, 3], NV: [1, 3], WY: [2, 3], SD: [3, 3], IA: [4, 3], IN: [5, 3], OH: [6, 3], PA: [7, 3], NJ: [8, 3], CT: [9, 3], CA: [0, 4], UT: [1, 4], CO: [2, 4], NE: [3, 4], MO: [4, 4], KY: [5, 4], WV: [6, 4], VA: [7, 4], MD: [8, 4], DE: [9, 4], AZ: [1, 5], NM: [2, 5], KS: [3, 5], AR: [4, 5], TN: [5, 5], NC: [6, 5], SC: [7, 5], DC: [8, 5], OK: [3, 6], LA: [4, 6], MS: [5, 6], AL: [6, 6], GA: [7, 6], HI: [0, 7], TX: [3, 7], FL: [8, 7]};
const TOP_ORDER = ["gov", "ussen", "ltgov", "ag", "sos", "cfo", "treas", "controller", "auditor", "agcomm", "insurance", "superintendent"];
const VIEWS = [["all", "Overview"], ["top", "Statewide"], ["fed", "Congress"], ["leg", "Legislature"], ["measure", "Questions"], ["jud", "Judges"], ["local", "County & local"]];

const resFold = s => String(s ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const resToks = s => resFold(s).replace(/"[^"]*"|\([^)]*\)/g, " ").replace(/\b(jr|sr|ii|iii|iv)\b\.?/g, " ").replace(/[^a-z' -]/g, " ").split(/[\s-]+/).filter(Boolean);
const resLast = s => resToks(s).slice(-1)[0] || "";
const resNum = n => Number(n || 0).toLocaleString("en-US");
const resAgo = iso => { if (!iso) return ""; const m = Math.round((Date.now() - new Date(iso)) / 60000); return m < 1 ? "just now" : m < 60 ? m + " min ago" : m < 1440 ? Math.round(m / 60) + " hr ago" : Math.round(m / 1440) + " days ago"; };
const resPartyName = p => ({R: "Republican", D: "Democrat", L: "Libertarian", G: "Green", I: "Independent", NPA: "No party", U: "Unaffiliated"}[p] || p || "");
const resColor = (p, n) => /^(yes|for)$/i.test(n || "") ? "var(--good)" : /^(no|against)$/i.test(n || "") ? "var(--bad)" : p === "R" ? "var(--rp)" : p === "D" ? "var(--dp)" : "var(--none)";
const resWinners = c => c.c.filter(k => k.w);

function resStatus(c) {
  if (c.m) {
    if (c.res === "passed") return ["pass", /^keep/i.test(c.t) ? "Kept" : "Passed"];
    if (c.res === "failed") return ["fail", /^keep/i.test(c.t) ? "Removed" : "Failed"];
    return ["open", resCounting(c)];
  }
  if (c.close && !resWinners(c).length) return ["close", "Too close to call"];
  if (resWinners(c).length) return ["won", c.c.length === 1 ? "Unopposed" : "Decided"];
  return ["open", resCounting(c)];
}
const resCounting = c => c.rp == null ? "Not reported yet" : !c.rp ? "No votes in yet" : c.rp >= 100 ? "Still being counted" : `${Math.round(c.rp)}% counted`;

const resOrder = c => c.m ? c.c.slice().sort((a, b) => (/^(yes|for)$/i.test(b.n) ? 1 : 0) - (/^(yes|for)$/i.test(a.n) ? 1 : 0)) : c.c;
function resRow(k, c) {
  const w = k.w, col = resColor(k.p, k.n), label = esc(k.n);
  const need = c.m && /^(yes|for)$/i.test(k.n) && c.need && c.need !== 50 ? `<s style="left:${c.need}%" title="Needs ${c.need}%"></s>` : "";
  return `<div class="rr${w ? " win" : ""}"><div class="rr-t"><span class="rn">${w ? "✓ " : ""}${label}${k.inc ? ` <small>incumbent</small>` : ""}</span>${k.p && !c.m ? `<span class="rp">${esc(k.p)}</span>` : ""}<span class="rpc">${k.pc}%</span></div><div class="trk"><i style="width:${Math.min(100, k.pc)}%;background:${col}"></i>${need}</div><div class="rv">${resNum(k.v)} votes</div></div>`;
}
function resCard(c, st) {
  const [cls, txt] = resStatus(c), top = resOrder(c).slice(0, 3), more = c.c.length - top.length;
  return `<button class="rcard" data-res="${esc(st)}~${esc(c.id)}"><div class="rc-h"><b>${esc(c.t)}</b><span class="rst ${cls}">${esc(txt)}</span></div>
    ${top.map(k => resRow(k, c)).join("")}
    <div class="rc-f">${more > 0 ? `+${more} more · ` : ""}${c.m && c.need && c.need !== 50 ? `Needs ${c.need}% to pass · ` : ""}${c.close ? `Inside the ${c.close}% recount margin · ` : ""}${c.rp != null ? `${Math.round(c.rp)}% of precincts in` : ""} <span class="go">Details ›</span></div></button>`;
}
function resTally(cs) {
  const t = {R: 0, D: 0, other: 0, open: 0};
  for (const c of cs) {
    const w = resWinners(c);
    if (!w.length) { t.open++; continue; }
    for (const k of w) k.p === "R" ? t.R++ : k.p === "D" ? t.D++ : t.other++;
  }
  return t;
}
function resSeatBar(title, t, view) {
  const all = t.R + t.D + t.other + t.open || 1, seg = (n, col) => n ? `<i style="width:${n / all * 100}%;background:${col}"></i>` : "";
  return `<button class="rseat" data-rview="${view}"><div class="rc-h"><b>${esc(title)}</b><span class="go">All ${all} ›</span></div><div class="stk">${seg(t.D, "var(--dp)")}${seg(t.other, "var(--none)")}${seg(t.open, "var(--chip)")}${seg(t.R, "var(--rp)")}</div><div class="rseat-l"><span><i style="background:var(--dp)"></i>Democrats ${t.D}</span>${t.other ? `<span><i style="background:var(--none)"></i>Other ${t.other}</span>` : ""}${t.open ? `<span><i style="background:var(--chip)"></i>Not decided ${t.open}</span>` : ""}<span><i style="background:var(--rp)"></i>Republicans ${t.R}</span></div></button>`;
}

// ---------- the voter's own ballot against the results ----------
function resContestFor(r, file, ji) {
  const by = k => file.contests.find(c => c.key === k), W = r.where || {};
  const fixed = {senate: "ussen", governor: "gov", ag: "ag", cfo: "cfo", agriculture: "agcomm"}[r.id];
  if (fixed) return by(fixed);
  if (r.kind === "judges") return r.judges[ji] ? by("ret-" + resLast(r.judges[ji].name)) : null;
  if (r.kind === "measure") {
    const nm = (r.m && r.m.name) || r.sub || "", a = /Amendment\s+(\d+)/i.exec(nm);
    if (a && W.all) return by("measure-" + a[1]);
    const words = s => new Set(resFold(s).replace(/\([^)]*\)/g, " ").split(/[^a-z0-9]+/).filter(x => (x.length > 3 || /^\d+$/.test(x)) && !["city", "county", "referendum", "florida", "shall", "with", "manatee"].includes(x)));
    const mine = words(nm), hits = file.contests.filter(c => c.m && c.lvl === "local").map(c => { const w = words(c.t); return [c, w.size ? [...w].filter(x => mine.has(x)).length / w.size : 0]; }).filter(x => x[1] >= .6).sort((a, b) => b[1] - a[1]);
    if (hits.length && (hits.length === 1 || hits[0][1] > hits[1][1])) return hits[0][0];
    const plain = W.county && !W.city ? file.contests.filter(c => c.m && resFold(c.t) === resFold(W.county + " County Referendum")) : [];   // the county's own question has no other words to go on
    return plain.length === 1 ? plain[0] : null;
  }
  if (W.cd) return by("ushouse-" + W.cd);
  if (W.sd) return by("stsen-" + W.sd);
  if (W.hd) return by("sthouse-" + W.hd);
  if (!r.cands) return null;
  const last = r.cands.map(c => resLast(c.name));
  const named = c => c.c.filter(k => !/^write-?ins?$/i.test(k.n));      // a counted write-in line isn't a named candidate
  const hits = file.contests.filter(c => !c.m && named(c).length === last.length && named(c).every(k => last.some(l => resToks(k.n).includes(l))));
  if (hits.length > 1) { const cty = resFold(W.county || (ctx && ctx.county) || ""), mine = cty ? hits.filter(c => resFold(c.t).includes(cty)) : []; return mine.length === 1 ? mine[0] : null; }
  return hits[0] || null;      // never guess: the same names twice with no county to tell them apart means no match
}
function resCand(c, name) {
  const l = resLast(name), hits = c.c.filter(k => resToks(k.n).includes(l));
  return hits.length === 1 ? hits[0] : null;
}
function resLine(r, key, pick, file) {
  const ji = r.kind === "judges" ? +String(key).split("|")[1] : 0, c = resContestFor(r, file, ji);
  if (!c) return r.cands && r.cands.length === 1 ? {state: pick ? "won" : "none", outcome: "Ran unopposed"} : {state: "none"};
  if (c.m) {
    if (!c.res) return {state: "open", c};
    const yes = c.res === "passed";
    return {state: !pick ? "none" : (/^yes$/i.test(pick) === yes ? "won" : "lost"), c, outcome: /^keep/i.test(c.t) ? (yes ? "Kept" : "Removed") : (yes ? "Passed" : "Failed")};
  }
  const w = resWinners(c), k = pick && resCand(c, pick);
  if (!w.length) return {state: "open", c, outcome: c.close ? "Too close to call" : resCounting(c)};
  const names = w.map(x => x.n).join(", ");
  if (!pick) return {state: "none", c, outcome: names + " won"};
  if (!k) return {state: "none", c, outcome: names + " won"};
  return {state: k.w ? "won" : "lost", c, outcome: k.w ? "Your pick won" : names + " won"};
}
function resMine(file) {
  const list = ctx ? ordered() : ALL.filter(r => (r.where || {}).all), out = [];
  for (const r of list) for (const [key, q] of lines(r)) { if (PICKS[key]) out.push({r, key, q, pick: PICKS[key], ...resLine(r, key, PICKS[key], file)}); }
  return out;
}
function resMineBox(file) {
  const rows = resMine(file);
  if (!rows.length) return `<div class="rmine"><b>📝 How your picks did</b><p>${ctx ? "You haven't made any picks yet. Make some on the My ballot tab and they'll be scored here." : "Add your address on the Ballot tab and your own races show up here."}</p></div>`;
  const n = s => rows.filter(x => x.state === s).length, won = n("won"), lost = n("lost"), open = n("open"), other = rows.length - won - lost - open;
  return `<div class="rmine"><b>📝 How your picks did</b><div class="rm-s"><span class="g"><b>${won}</b>won</span><span class="b"><b>${lost}</b>lost</span><span class="o"><b>${open}</b>still counting</span></div>
    <details><summary>See each of your ${rows.length} picks</summary><div class="rm-l">${rows.map(x => `<button class="mrow" ${x.c ? `data-res="FL~${esc(x.c.id)}"` : `data-go="${esc(x.r.id)}"`}><span class="mq">${esc(x.q)}</span><span class="ma ${x.state}">${x.state === "won" ? "✓" : x.state === "lost" ? "✗" : "…"} ${esc(x.pick)}${x.outcome ? ` · ${esc(x.outcome)}` : ""}</span></button>`).join("")}</div>${other ? `<p class="mini muted">${other} couldn't be matched to a result yet, so ${other === 1 ? "it isn't" : "they aren't"} counted above.</p>` : ""}</details></div>`;
}

// ---------- data ----------
async function resLoad(st, force) {
  const hit = RES.files[st];
  if (hit && !force && Date.now() - hit.at < 120000) return hit.j;
  let j = null;
  try { const r = await fetch(`${API}/results/${st}`); if (r.ok) j = await r.json(); } catch (e) {}
  if (!j) try { const r = await fetch(`buddy/results/data/${st}.json`); if (r.ok) { j = await r.json(); j.backup = true; } } catch (e) {}
  if (!j) { if (hit) return hit.j; throw new Error("no results"); }
  RES.files[st] = {at: Date.now(), j};
  return j;
}

// ---------- pages ----------
function resChips() {
  const st = RES.st, more = !RES_TABS.some(t => t[0] === st);
  return `<div class="rtabs">${RES_TABS.map(([k, l]) => `<button class="rtab${k === st ? " on" : ""}" data-rtab="${k}">${l}</button>`).join("")}<select class="rtab sel${more ? " on" : ""}" id="rmore" aria-label="More states"><option value="">More states…</option>${Object.keys(RES_NAMES).filter(k => k !== "US").sort((a, b) => RES_NAMES[a].localeCompare(RES_NAMES[b])).map(k => `<option value="${k}"${more && k === st ? " selected" : ""}>${RES_NAMES[k]}</option>`).join("")}</select></div>`;
}
function resultsPage() {
  document.title = "Results · " + D.title;
  if (!RES.st) RES.st = "FL";
  $("#app").innerHTML = `<header class="appbar"><div class="ab-l">🏁 Results</div>${whoBtn()}</header>${resChips()}<div id="resBody"></div>`;
  resFill();
  clearInterval(RES.timer);
  RES.timer = setInterval(() => { if (curPage() === "results" && !document.hidden) resFill(true); else if (curPage() !== "results") clearInterval(RES.timer); }, 300000);
}
async function resFill(quiet) {
  const st = RES.st, body = $("#resBody");
  if (!body) return;
  if (!quiet) body.innerHTML = `<div class="rload"><span class="spin"></span><b>Loading ${esc(RES_NAMES[st] || st)} results…</b><small>Getting the latest count.</small></div>`;
  let j;
  try { j = await resLoad(st, quiet); }
  catch (e) { if (!quiet && RES.st === st) body.innerHTML = `<div class="panel"><b>We couldn't load ${esc(RES_NAMES[st] || st)} results.</b><br>Check your signal and try again, or come back shortly if this state's results are still being set up.<br><button class="btn ghost" style="margin-top:8px" data-rretry>Try again</button></div>`; return; }
  if (RES.st !== st || !$("#resBody")) return;
  if (quiet && body.dataset.stamp === String(j.checked)) return;
  body.dataset.stamp = String(j.checked);
  if (st === "US") resNation(j, body); else resState(j, body, st);
}
function resFresh(j) {
  const d = j.data, src = (d.sources || []).map(s => `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.name)}</a>`).join(" and ");
  return `<p class="rfresh">Unofficial until each state certifies. ${j.checked ? `Checked ${resAgo(j.checked)}. ` : ""}From ${src}. <a href="#results/rhow">How this works</a></p>
    ${j.problem || j.backup ? `<div class="panel ramber">⚠️ ${j.backup ? "The live feed isn't answering, so this is a saved copy." : "One source isn't answering, so part of this may be behind."}</div>` : ""}`;
}
function resState(j, body, st) {
  const d = j.data, C = d.contests, q = resFold(RES.q).trim(), of = v => C.filter(c => c.lvl === v);
  const views = VIEWS.filter(([k]) => k === "all" || of(k).length || (k === "top" && C.some(c => c.key === "ussen")));
  if (!views.some(v => v[0] === RES.view)) RES.view = "all";
  const inView = v => v === "top" ? C.filter(c => c.lvl === "top" || c.key === "ussen").sort((a, b) => TOP_ORDER.indexOf(a.key) - TOP_ORDER.indexOf(b.key)) : v === "fed" ? [...C.filter(c => c.key === "ussen"), ...C.filter(c => c.lvl === "fed" && c.key !== "ussen").sort((a, b) => +a.key.split("-")[1] - +b.key.split("-")[1])] : v === "leg" ? of("leg").sort((a, b) => a.key.localeCompare(b.key, "en", {numeric: true})) : of(v);
  let h = resFresh(j) + `<div class="rsearch"><input id="rq" type="search" placeholder="Search any race or candidate in ${esc(d.name)}" value="${esc(RES.q)}" autocomplete="off"></div>`;
  h += `<div class="rviews">${views.map(([k, l]) => `<button class="rview${k === RES.view && !q ? " on" : ""}" data-rview="${k}">${l}${k !== "all" ? ` <small>${inView(k).length}</small>` : ""}</button>`).join("")}</div>`;
  h += `<div id="resList">` + resListHtml(d, st, inView, q) + `</div>`;
  body.innerHTML = h;
}
function resListHtml(d, st, inView, q) {
  const C = d.contests;
  if (q) {
    const hit = C.filter(c => resFold(c.t).includes(q) || c.c.some(k => resFold(k.n).includes(q)));
    if (!hit.length) return `<p class="count" style="margin-top:12px">Nothing matches "${esc(RES.q)}". Try a last name, a county or a district number.</p>`;
    return `<p class="count" style="margin-top:12px">${hit.length} ${hit.length === 1 ? "match" : "matches"}</p><div class="rcards">${hit.slice(0, RES.shown).map(c => resCard(c, st)).join("")}</div>${resMoreBtn(hit.length)}`;
  }
  if (RES.view !== "all") {
    const arr = inView(RES.view);
    return `<div class="rcards">${arr.slice(0, RES.shown).map(c => resCard(c, st)).join("")}</div>${resMoreBtn(arr.length)}`;
  }
  let h = st === "FL" && typeof PICKS !== "undefined" ? resMineBox(d) : "";
  const top = inView("top"), house = C.filter(c => c.lvl === "fed" && c.key !== "ussen"), sen = C.filter(c => /^stsen-/.test(c.key)), asm = C.filter(c => /^sthouse-/.test(c.key)), ms = C.filter(c => c.lvl === "measure");
  if (top.length) h += `<h2 class="grp">🏛️ Statewide</h2><div class="rcards">${top.map(c => resCard(c, st)).join("")}</div>`;
  if (house.length || sen.length || asm.length) {
    h += `<h2 class="grp">🗺️ Who won the seats on the ballot</h2><div class="rcards">`;
    if (house.length) h += resSeatBar("U.S. House", resTally(house), "fed");
    if (sen.length) h += resSeatBar("State Senate", resTally(sen), "leg");
    if (asm.length) h += resSeatBar(st === "CA" ? "State Assembly" : "State House", resTally(asm), "leg");
    h += `</div><p class="deckhint" style="margin-top:8px">Only seats on this ballot are counted, so this isn't who controls the chamber.</p>`;
  }
  if (ms.length) h += `<h2 class="grp">📜 Ballot questions</h2><div class="rcards">${ms.map(c => resCard(c, st)).join("")}</div>`;
  const local = C.filter(c => c.lvl === "local").length, jud = C.filter(c => c.lvl === "jud").length;
  h += `<div class="rlist" style="margin-top:16px">${jud ? `<button class="rrow" data-rview="jud"><span class="rnum">⚖️</span><span class="rmain"><span class="rt">Judges</span><span class="rs">${jud} races and keep-or-remove votes</span></span><span class="chev">›</span></button>` : ""}${local ? `<button class="rrow" data-rview="local"><span class="rnum">🏘️</span><span class="rmain"><span class="rt">County & local</span><span class="rs">${resNum(local)} races and questions</span></span><span class="chev">›</span></button>` : ""}</div>`;
  return h;
}
const resMoreBtn = n => n > RES.shown ? `<button class="btn ghost rmorebtn" data-rshow>Show ${Math.min(30, n - RES.shown)} more of ${n - RES.shown} left</button>` : "";

function resNation(j, body) {
  const races = j.data.races, layer = RES.layer, of = k => races.filter(r => k === "ushouse" ? /^ushouse-/.test(r.key) : r.key === k);
  const L = {gov: "Governors", ussen: "U.S. Senate", ushouse: "U.S. House"}, cur = of(layer), t = resTally(cur);
  let tiles = "";
  for (const [st, [x, y]] of Object.entries(RES_GRID)) {
    const rs = cur.filter(r => r.st === st);
    let bg = "var(--chip)", ink = "var(--sub)", sub = "";
    if (rs.length) {
      const tt = resTally(rs);
      if (layer === "ushouse") {
        const lead = tt.R > tt.D ? "R" : tt.D > tt.R ? "D" : null;
        bg = lead ? resColor(lead) : "var(--none)"; ink = "#fff"; sub = lead ? `${lead}+${Math.abs(tt.R - tt.D)}` : "Tied";
        if (tt.open) sub += "*";
      } else {
        const w = rs.flatMap(resWinners)[0];
        if (w) { bg = resColor(w.p); ink = "#fff"; sub = w.p; }
        else { bg = "var(--none-bg)"; ink = "var(--ink)"; sub = "…"; }
      }
    }
    tiles += `<button class="rtile" style="grid-column:${x + 1};grid-row:${y + 1};background:${bg};color:${ink}" data-rtab="${st}" aria-label="${esc(RES_NAMES[st])}${sub ? ": " + esc(sub) : ""}"><b>${st}</b>${sub ? `<small>${esc(sub)}</small>` : ""}</button>`;
  }
  const close = races.filter(r => r.c.length > 1 && r.c[0].v > 500).map(r => [r, Math.abs(r.c[0].pc - r.c[1].pc)]).sort((a, b) => a[1] - b[1]).slice(0, 12);
  body.innerHTML = resFresh(j) + `<div class="rviews">${Object.entries(L).map(([k, l]) => `<button class="rview${k === layer ? " on" : ""}" data-rlayer="${k}">${l}</button>`).join("")}</div>
    ${resSeatBarStatic(L[layer], t)}
    <div class="rgrid">${tiles}</div>
    <p class="deckhint">Tap a state to see all of its races.${layer === "ushouse" ? " R+5 means Republicans won 5 more seats there than Democrats. * means some seats aren't decided yet." : " Gray means no race this year."}</p>
    <h2 class="grp">🔥 Closest races in the country</h2><div class="rcards">${close.map(([r]) => resCard(Object.assign({}, r, {t: RES_NAMES[r.st] + ": " + r.t}), "US")).join("")}</div>`;
}
function resSeatBarStatic(title, t) {
  const all = t.R + t.D + t.other + t.open || 1, seg = (n, col) => n ? `<i style="width:${n / all * 100}%;background:${col}"></i>` : "";
  return `<div class="rseat static"><div class="rc-h"><b>${esc(title)}: seats on this ballot</b><span class="go">${all}</span></div><div class="stk">${seg(t.D, "var(--dp)")}${seg(t.other, "var(--none)")}${seg(t.open, "var(--chip)")}${seg(t.R, "var(--rp)")}</div><div class="rseat-l"><span><i style="background:var(--dp)"></i>Democrats ${t.D}</span>${t.other ? `<span><i style="background:var(--none)"></i>Other ${t.other}</span>` : ""}${t.open ? `<span><i style="background:var(--chip)"></i>Not decided ${t.open}</span>` : ""}<span><i style="background:var(--rp)"></i>Republicans ${t.R}</span></div></div>`;
}

// ---------- one race, with its county map ----------
function resHowSheet() {
  return `<div class="panel"><h4>Where the numbers come from</h4>Florida, North Carolina and California numbers come straight from each state's election office. Every other state comes from civicAPI, a free results service. Where both exist, the state's number is the one shown.</div>
    <div class="panel"><h4>When we say someone won</h4>When civicAPI has called the race, or when every precinct is in and the gap is bigger than the state's recount margin. California never gets the second kind, because mail ballots keep arriving there after every precinct has reported.</div>
    <div class="panel"><h4>Ballot questions</h4>Each state sets its own bar. Florida amendments need 60% Yes, so a question can win most of the votes and still fail.</div>
    <div class="panel"><h4>Nothing here is final</h4>Every result stays unofficial until the state certifies it. Numbers can still move as ballots are added.</div>`;
}
async function resOpen(st, id) {
  openSheet("Loading…", `<div class="rload"><span class="spin"></span><b>Loading this race…</b></div>`);
  let j;
  try { j = await resLoad(st); } catch (e) { openSheet("Couldn't load this race", `<div class="panel">Check your signal and try again.</div>`); return; }
  const c = (j.data.contests || j.data.races).find(x => x.id === id);
  if (!c) { openSheet("Race not found", `<div class="panel">This race isn't in the latest results.</div>`); return; }
  const real = c.st || st, [cls, txt] = resStatus(c);
  openSheet(st === "US" ? RES_NAMES[real] + ": " + c.t : c.t, `<div class="rc-h"><span class="rst ${cls}">${esc(txt)}</span><span class="mini muted">${c.rp != null ? Math.round(c.rp) + "% of precincts in" : ""}</span></div>
    ${resOrder(c).map(k => resRow(k, c)).join("")}
    ${c.m && c.need && c.need !== 50 ? `<p class="mini">This question needs ${c.need}% Yes to pass.</p>` : ""}
    ${c.close ? `<p class="mini">The gap is inside the state's ${c.close}% recount margin.</p>` : ""}
    ${c.c.some(k => k.ap) ? `<p class="mini muted">Decided because every precinct is in and the gap is wider than the recount margin. No outlet's race call was available.</p>` : ""}
    <div id="rmap"><div class="rload small"><span class="spin"></span>Loading the county map…</div></div>
    <p class="mini muted">Source: ${esc(c.src || "")}. Unofficial until certified.</p>`);
  resMap(c, real);
}
async function resCounties(c, st) {
  if (st === "FL" && String(c.id).startsWith("fl-")) {
    let t = null;
    try { const r = await fetch(`${API}/results/FL/counties/${encodeURIComponent(c.id)}`); if (r.ok) t = (await r.json()).counties; } catch (e) {}
    if (!t) try { const r = await fetch("buddy/results/data/FL.counties.json"); if (r.ok) t = (await r.json())[c.id]; } catch (e) {}
    return t ? {byName: t} : null;
  }
  if (!c.civic) return null;
  try { const r = await fetch(`${API}/results/race/${c.civic}`); if (r.ok) { const j = await r.json(); return Object.keys(j.regions || {}).length ? {byFips: j.regions} : null; } } catch (e) {}
  return null;
}
async function resMap(c, st) {
  const box = $("#rmap");
  if (!box) return;
  let m = null, data = null;
  try { const [a, b] = await Promise.all([fetch(`buddy/results/maps/${st}.json`).then(r => r.ok ? r.json() : null), resCounties(c, st)]); m = a; data = b; } catch (e) {}
  const live = $("#rmap");
  if (!live) return;
  if (!m || !data) { live.innerHTML = `<p class="mini muted">No county breakdown for this race.</p>`; return; }
  const regions = {};
  if (data.byFips) Object.assign(regions, data.byFips);
  else {
    const key = s => resFold(s).replace(/[^a-z]/g, ""), idx = {};
    for (const [f, x] of Object.entries(m.c)) idx[key(x.n)] = f;
    idx.dade = idx.miamidade || idx.dade;
    for (const [name, votes] of Object.entries(data.byName)) {
      const f = idx[key(name)]; if (!f) continue;
      const total = Object.values(votes).reduce((a, b) => a + b, 0);
      regions[f] = {n: name, c: Object.entries(votes).map(([n, v]) => { const hit = c.c.find(k => resToks(n).includes(resLast(k.n))) || c.c.find(k => resFold(k.n) === resFold(n)); return {n: hit ? hit.n : n, p: hit ? hit.p : "", v, pc: total ? Math.round(v / total * 1000) / 10 : 0}; }).sort((a, b) => b.v - a.v)};
    }
  }
  let paths = "", found = 0;
  for (const [f, x] of Object.entries(m.c)) {
    const reg = regions[f], cs = reg && (reg.c || []).slice().sort((a, b) => b.v - a.v), lead = cs && cs[0] && cs[0].v ? cs[0] : null;
    if (lead) found++;
    const margin = lead && cs[1] ? lead.pc - cs[1].pc : 40, op = lead ? (.35 + .65 * Math.min(1, margin / 40)).toFixed(2) : 1;
    paths += `<path d="${x.d}" data-f="${f}" style="fill:${lead ? resColor(lead.p, lead.n) : "var(--chip)"};fill-opacity:${op}"><title>${esc(x.n)}${lead ? ": " + esc(lead.n) + " " + lead.pc + "%" : ""}</title></path>`;
  }
  if (!found) { live.innerHTML = `<p class="mini muted">No county breakdown for this race.</p>`; return; }
  live._regions = regions; live._names = m.c;
  live.innerHTML = `<h4 class="rmap-h">By county</h4><svg class="rsvg" viewBox="0 0 ${m.w} ${m.h}" role="img" aria-label="County map of ${esc(c.t)}">${paths}</svg><p class="mini muted">Darker means a wider lead. Tap a county for its numbers.${data.byFips ? " County numbers from civicAPI." : ""}</p><div id="rcty"></div>`;
}
async function resRaceBanner(r) {
  const lead = $("#app .lead") || $("#app .bar");
  if (!lead) return;
  let j; try { j = await resLoad("FL"); } catch (e) { return; }
  if (!$("#app .bar") || !lead.isConnected) return; // they moved on while the result was loading
  const cs = r.kind === "judges" ? r.judges.map((_, i) => resContestFor(r, j.data, i)).filter(Boolean) : [resContestFor(r, j.data)].filter(Boolean);
  if (document.querySelector("#app .rbanner")) return;
  if (!cs.length) { if (r.cands && r.cands.length === 1) lead.insertAdjacentHTML("beforebegin", `<div class="rbanner"><b>🏁 Result</b><div class="rbanner-r"><span>${esc(r.cands[0].name)} ran unopposed</span><span class="rst won">Unopposed</span></div></div>`); return; }
  const line = c => {
    const [cls, txt] = resStatus(c), w = resWinners(c);
    return `<button class="rbanner-r" data-res="FL~${esc(c.id)}"><span>${c.m ? esc(c.t.replace(/^Keep (.*)\?$/, "$1").replace(/ - .*/, "")) : w.length ? esc(w.map(x => x.n).join(", ")) : esc(c.c[0] ? c.c[0].n + " leads" : c.t)}${w.length && !c.m ? ` won with ${w[0].pc}%` : c.m && c.c[0] ? ` · Yes ${(c.c.find(k => /^yes$/i.test(k.n)) || {pc: 0}).pc}%` : ""}</span><span class="rst ${cls}">${esc(txt)}</span></button>`;
  };
  lead.insertAdjacentHTML(lead.classList.contains("bar") ? "afterend" : "beforebegin", `<div class="rbanner"><b>🏁 Result</b>${cs.map(line).join("")}</div>`);
}
async function resDecorateMine() {
  let j; try { j = await resLoad("FL"); } catch (e) { return; }
  document.querySelectorAll("#app .mrow[data-go]").forEach(el => {
    const k = el.dataset.k, r = el.dataset.go && raceById(el.dataset.go);
    if (!k || !r || !PICKS[k] || el.querySelector(".rchip")) return;
    const x = resLine(r, k, PICKS[k], j.data);
    if (x.state === "won" || x.state === "lost" || x.state === "open") el.querySelector(".ma").insertAdjacentHTML("beforeend", ` <span class="rchip ${x.state}">${x.state === "won" ? "won" : x.state === "lost" ? "lost" : "counting"}</span>`);
  });
}
const resHomeRow = () => `<div class="rlist" style="margin:0 0 10px"><button class="rrow rhome" data-go="results"><span class="rnum">🏁</span><span class="rmain"><span class="rt">Election results</span><span class="rs">See who won, and how your picks did</span></span><span class="chev">›</span></button></div>`;

document.addEventListener("click", e => {
  const t = e.target;
  const open = t.closest("[data-res]");
  if (open) { e.preventDefault(); location.hash = "results/x" + open.dataset.res; return; }
  const tab = t.closest("[data-rtab]");
  if (tab) { RES.st = tab.dataset.rtab; RES.view = "all"; RES.q = ""; RES.shown = 30; resultsPage(); window.scrollTo(0, 0); return; }
  const v = t.closest("[data-rview]");
  if (v) { RES.view = v.dataset.rview; RES.q = ""; RES.shown = 30; resFill(); window.scrollTo(0, 0); return; }
  const l = t.closest("[data-rlayer]");
  if (l) { RES.layer = l.dataset.rlayer; resFill(); return; }
  if (t.closest("[data-rshow]")) { RES.shown += 30; resFill(); return; }
  if (t.closest("[data-rretry]")) { delete RES.files[RES.st]; resFill(); return; }
  const p = t.closest("#rmap path");
  if (p) {
    const box = $("#rmap"), reg = box && box._regions && box._regions[p.dataset.f], nm = box && box._names && box._names[p.dataset.f], out = $("#rcty");
    if (out) out.innerHTML = reg ? `<div class="panel"><b>${esc((nm && nm.n) || reg.n)}</b>${(reg.c || []).slice().sort((a, b) => b.v - a.v).slice(0, 5).map(k => `<div class="rcty-r"><span>${esc(k.n)}</span><span>${k.pc}% · ${resNum(k.v)}</span></div>`).join("")}</div>` : `<p class="mini muted">${esc(nm ? nm.n : "")}: no numbers for this county.</p>`;
  }
});
document.addEventListener("change", e => {
  if (e.target.id === "rmore" && e.target.value) { RES.st = e.target.value; RES.view = "all"; RES.q = ""; RES.shown = 30; resultsPage(); window.scrollTo(0, 0); }
});
let resQT = null;
document.addEventListener("input", e => {
  if (e.target.id !== "rq") return;
  clearTimeout(resQT);
  resQT = setTimeout(() => {
    RES.q = e.target.value; RES.shown = 30;
    const f = RES.files[RES.st], out = $("#resList");
    if (!f || !out || RES.st === "US") return;
    const d = f.j.data, C = d.contests, of = v => C.filter(c => c.lvl === v);
    const inView = v => v === "top" ? C.filter(c => c.lvl === "top" || c.key === "ussen").sort((a, b) => TOP_ORDER.indexOf(a.key) - TOP_ORDER.indexOf(b.key)) : v === "fed" ? [...C.filter(c => c.key === "ussen"), ...C.filter(c => c.lvl === "fed" && c.key !== "ussen").sort((a, b) => +a.key.split("-")[1] - +b.key.split("-")[1])] : v === "leg" ? of("leg").sort((a, b) => a.key.localeCompare(b.key, "en", {numeric: true})) : of(v);
    out.innerHTML = resListHtml(d, RES.st, inView, resFold(RES.q).trim());
    document.querySelectorAll(".rview").forEach(b => b.classList.toggle("on", !RES.q.trim() && b.dataset.rview === RES.view));
  }, 150);
});
