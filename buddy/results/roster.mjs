// Who gets researched first, from the results: winners and runners-up for statewide, Congress and legislature races.
// Run: node buddy/results/roster.mjs AL NJ CA NC  (reads buddy/results/data/<ST>.json, writes buddy/results/roster/<ST>.json)
import {readFileSync, writeFileSync, mkdirSync} from "node:fs";
const out = new URL("./roster/", import.meta.url);
mkdirSync(out, {recursive: true});
let total = 0;
for (const st of process.argv.slice(2)) {
  const d = JSON.parse(readFileSync(new URL(`./data/${st}.json`, import.meta.url))).data;
  const races = d.contests.filter(c => !c.m && ["top", "fed", "leg"].includes(c.lvl));
  const people = [];
  for (const c of races) {
    const vf = c.vf || 1, named = c.c.filter(k => !/^write-?ins?$/i.test(k.n)).sort((a, b) => b.v - a.v);
    const winners = named.filter(k => k.w), keep = winners.length ? [...winners, ...named.filter(k => !k.w).slice(0, 1)] : named.slice(0, vf + 1);
    for (const k of keep) people.push({st, key: c.key, race: c.t, lvl: c.lvl, name: k.n, party: k.p, won: !!k.w, pc: k.pc, votes: k.v, inc: !!k.inc, unopposed: named.length === 1});
  }
  writeFileSync(new URL(st + ".json", out), JSON.stringify(people, null, 0));
  const by = l => people.filter(p => p.lvl === l).length;
  console.log(st, "races", races.length, "people", people.length, "statewide", by("top"), "congress", by("fed"), "legislature", by("leg"), "decided", people.filter(p => p.won).length);
  total += people.length;
}
console.log("total", total);
