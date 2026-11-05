// Draws every state's county map once, from the Census Bureau's public-domain county shapes (the us-atlas package).
// Run from a folder where d3-geo, topojson-client and us-atlas are installed:
//   node build_maps.cjs <that folder> <output folder>
// Writes <ST>.json: {w, h, c: {fips: {n: county name, d: svg path}}}
const fs = require("fs"), path = require("path");
const [dir, out] = process.argv.slice(2);
const load = m => require(path.join(dir, "node_modules", m));
(async () => {
  const {geoAlbers, geoMercator, geoPath} = await import("file://" + path.join(dir, "node_modules/d3-geo/src/index.js").replace(/\\/g, "/"));
  const topo = load("topojson-client");
  const us = JSON.parse(fs.readFileSync(path.join(dir, "node_modules/us-atlas/counties-10m.json"), "utf8"));
  const FIPS = {"01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT", "10": "DE", "11": "DC", "12": "FL", "13": "GA", "15": "HI", "16": "ID", "17": "IL", "18": "IN", "19": "IA", "20": "KS", "21": "KY", "22": "LA", "23": "ME", "24": "MD", "25": "MA", "26": "MI", "27": "MN", "28": "MS", "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH", "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND", "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA", "54": "WV", "55": "WI", "56": "WY"};
  const all = topo.feature(us, us.objects.counties).features;
  fs.mkdirSync(out, {recursive: true});
  let total = 0;
  for (const [pre, st] of Object.entries(FIPS)) {
    const fs0 = all.filter(f => String(f.id).startsWith(pre));
    const fc = {type: "FeatureCollection", features: fs0};
    const w = 360;
    const proj = st === "AK" ? geoAlbers().rotate([154, 0]).center([0, 62]).parallels([55, 65]) : geoMercator();
    proj.fitWidth(w, fc);
    const pathGen = geoPath(proj).digits(1);
    const [[, y0], [, y1]] = pathGen.bounds(fc);
    const h = Math.ceil(y1 - y0) + 2;
    proj.translate([proj.translate()[0], proj.translate()[1] - y0 + 1]);
    const c = {};
    for (const f of fs0) c[String(f.id)] = {n: f.properties.name, d: pathGen(f)};
    const s = JSON.stringify({w, h, c});
    fs.writeFileSync(path.join(out, st + ".json"), s);
    total += s.length;
  }
  console.log("maps:", Object.keys(FIPS).length, "bytes:", total);
})();
