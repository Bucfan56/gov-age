// Every ZIP in a state -> its congressional, state senate and state house districts plus county, by asking the Census geocoder
// about each ZIP's center point. Run: node ballot/zip_districts.mjs <ST> <gazetteer file> <out.json>
// Gazetteer: https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2020_Gazetteer/2020_Gaz_zcta_national.zip
import fs from "node:fs";
const [ST, gaz, outFile] = process.argv.slice(2);
const RANGE = {FL: ["32000", "35000"], AL: ["35000", "37000"], NJ: ["07000", "09000"], CA: ["90000", "96200"], NC: ["27000", "29000"]}[ST];
if (!RANGE) throw new Error("no ZIP range for " + ST);
const rows = fs.readFileSync(gaz, "utf8").split("\n").slice(1).map(l => l.trim().split(/\s+/)).filter(p => p[0] >= RANGE[0] && p[0] < RANGE[1]);
const out = {}, fail = [], other = [];
async function one(p) {
  const [z, , , , , lat, lon] = p;
  const u = `https://geocoding.geo.census.gov/geocoder/geographies/coordinates?x=${lon}&y=${lat}&benchmark=Public_AR_Current&vintage=Current_Current&layers=all&format=json`;
  for (let a = 0; a < 4; a++) {
    try {
      const j = await (await fetch(u)).json(), g = j.result.geographies;
      const pick = re => { const k = Object.keys(g).find(k => re.test(k)); return k && g[k][0] ? g[k][0] : null; };
      const stn = g.States && g.States[0] && g.States[0].STUSAB;
      if (stn !== ST) { other.push(z + ":" + stn); return; }     // a ZIP center over the line or in the water stays out rather than guessed
      const cd = pick(/Congressional Districts/), up = pick(/Legislative Districts - Upper/), lo = pick(/Legislative Districts - Lower/), co = pick(/^Counties$/), pl = pick(/Incorporated Places/);
      out[z] = {cd: cd && +cd.BASENAME, sd: up && +up.BASENAME, hd: lo && +lo.BASENAME, county: co && co.BASENAME, city: pl && pl.BASENAME, st: ST};
      return;
    } catch (e) { await new Promise(r => setTimeout(r, 1200 * (a + 1))); }
  }
  fail.push(z);
}
const q = [...rows];
await Promise.all(Array.from({length: 8}, async () => { while (q.length) await one(q.shift()); }));
fs.mkdirSync(new URL(".", "file:///" + outFile.replace(/\\/g, "/")), {recursive: true});
fs.writeFileSync(outFile, JSON.stringify(out));
console.log(ST, "zips", rows.length, "kept", Object.keys(out).length, "outside the state", other.length, other.slice(0, 5).join(" "), "failed", fail.length, fail.slice(0, 5).join(" "));
if (rows.length && fail.length / rows.length > .02) process.exit(1);     // too many misses: fail loudly, don't ship a thin table
