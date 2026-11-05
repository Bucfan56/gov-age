// Pull results with the same code the Worker runs. Writes a backup copy per state to buddy/results/data/, which ships with the
// site so the app has something to show if the API is down. Run: node buddy/results/pull.mjs [FL NC ...]
import {writeFileSync, mkdirSync} from "node:fs";
import {buildState, buildNation, PRIORITY} from "../worker/src/results.js";
const out = new URL("./data/", import.meta.url);
mkdirSync(out, {recursive: true});
const list = process.argv.length > 2 ? process.argv.slice(2) : PRIORITY;
let bad = 0;
for (const st of list) {
  const {file, counties, errors} = await buildState(fetch, st);
  writeFileSync(new URL(st + ".json", out), JSON.stringify({checked: new Date().toISOString(), changed: null, problem: errors.join("; ") || null, data: file}));
  if (Object.keys(counties).length) writeFileSync(new URL(st + ".counties.json", out), JSON.stringify(counties));
  const called = file.contests.filter(c => c.m ? c.res : c.c.some(k => k.w)).length;
  console.log(st, "contests", file.contests.length, "decided", called, "chambers", file.chambers.length, "compared", file.audit.compared, "disagree", file.audit.off.length, errors.length ? "ERRORS " + errors.join("; ") : "");
  for (const x of file.audit.off.slice(0, 8)) console.log("   differs:", x.t, "|", x.n, "official", x.official, "civic", x.civic);
  if (errors.length) bad++;
}
if (process.argv.length <= 2) { const n = await buildNation(fetch); writeFileSync(new URL("US.json", out), JSON.stringify({checked: new Date().toISOString(), changed: null, problem: null, data: n})); console.log("US races", n.races.length); }
process.exit(bad ? 1 : 0);
