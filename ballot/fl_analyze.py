"""Summarise the Florida candidate-account pulls (fl/fl_*.json) per candidate."""
import glob, json, os, re, sys
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
D, OUT = sys.argv[1], sys.argv[2]
SUFFIX = re.compile(r"\s*\([A-Z]{2,4}\)\s*\([A-Z]{2,4}\)\s*$")
MANATEE = {"34201", "34202", "34203", "34204", "34205", "34206", "34207", "34208", "34209", "34210",
           "34211", "34212", "34215", "34216", "34217", "34218", "34219", "34220", "34221", "34222",
           "34243", "34250", "34251", "34264", "34270", "34280", "34281", "34282"}
ORG = re.compile(r"\b(LLC|L\.L\.C|INC|CORP|CORPORATION|COMPANY|CO\.|P\.?A\.?|PLLC|LLP|LP|LTD|PAC|COMMITTEE|"
                 r"ASSOCIATION|ASSN|PARTY|FUND|GROUP|HOLDINGS|PARTNERS|TRUST|FOUNDATION|ENTERPRISES|"
                 r"INDUSTRIES|SERVICES|SOLUTIONS|FLORIDA|COUNCIL|UNION|FEDERATION|CHAMBER)\b", re.I)
DEV = re.compile(r"\b(HOMES?|BUILDERS?|BUILDING|DEVELOP\w*|CONSTRUCT\w*|LAND|LANDS|REALTY|REAL ESTATE|"
                 r"REALTOR\w*|PAVING|EXCAVAT\w*|ENGINEER\w*|CONCRETE|ASPHALT|PROPERT(Y|IES)|"
                 r"COMMUNITIES|SMR|LAKEWOOD RANCH|NEAL|BENDERSON|LENNAR|PULTE|HORTON)\b", re.I)
SUGAR = re.compile(r"\b(U\.?S\.? SUGAR|UNITED STATES SUGAR|FLORIDA CRYSTALS|FLO-SUN|FANJUL)\b", re.I)
UTIL = re.compile(r"\b(FLORIDA POWER|FPL|NEXTERA|DUKE ENERGY|TECO|TAMPA ELECTRIC)\b", re.I)
GAMB = re.compile(r"\b(SEMINOLE TRIBE|SEMINOLE HARD ROCK|DISNEY|WALT DISNEY|PUBLIX|AT&T)\b", re.I)

out = {}
for f in sorted(glob.glob(os.path.join(D, "fl_*.json"))):
    blob = json.load(open(f, encoding="utf-8"))
    for r in blob["rows"]:
        to = SUFFIX.sub("", (r.get("Candidate/Committee") or "").strip()).strip()
        if not to:
            continue
        typ = (r.get("Typ") or "").strip()
        try:
            amt = float((r.get("Amount") or "0").replace("$", "").replace(",", ""))
        except ValueError:
            continue
        o = out.setdefault(to, {"race": os.path.basename(f)[3:-5], "gift": 0.0, "n": 0, "loans": 0.0, "manatee": 0.0,
                                "fl": 0.0, "out": 0.0, "org": 0.0, "dev": 0.0, "named": defaultdict(float),
                                "donors": defaultdict(lambda: [0.0, 0, ""]), "addr": defaultdict(lambda: [0.0, set()]),
                                "last": ""})
        if typ == "LOA":
            o["loans"] += amt
            continue
        if typ == "INT":
            continue
        name = (r.get("Contributor Name") or "").strip()
        csz = (r.get("City State Zip") or "").strip()
        m = re.search(r"\b([A-Z]{2})\s+(\d{5})", csz)
        st, z = (m.group(1), m.group(2)) if m else ("", "")
        o["gift"] += amt; o["n"] += 1
        dt = (r.get("Date") or "")
        if len(dt) == 10:
            o["last"] = max(o["last"], dt[6:] + dt[:2] + dt[3:5])
        if z in MANATEE:
            o["manatee"] += amt
        if st == "FL":
            o["fl"] += amt
        elif st:
            o["out"] += amt
        isorg = bool(ORG.search(name))
        if isorg:
            o["org"] += amt
            k = re.sub(r"\W", "", (r.get("Address") or "").upper()) + z
            if k:
                o["addr"][k][0] += amt; o["addr"][k][1].add(name.upper())
        if DEV.search(name) or DEV.search(r.get("Occupation") or ""):
            o["dev"] += amt
        for lab, rx in (("sugar", SUGAR), ("utility", UTIL), ("big_corp", GAMB)):
            if rx.search(name):
                o["named"][lab] += amt
        d = o["donors"][(name.upper(), z)]
        d[0] += amt; d[1] += 1; d[2] = f"{csz} · {(r.get('Occupation') or '').strip()}"

final = {}
for to, o in out.items():
    g = o["gift"] or 1
    final[to] = {"race": o["race"], "raised": round(o["gift"]), "gifts": o["n"], "loans": round(o["loans"]),
                 "through": o["last"], "pct_manatee": round(100 * o["manatee"] / g, 1), "pct_fl": round(100 * o["fl"] / g, 1),
                 "pct_out_state": round(100 * o["out"] / g, 1), "pct_org": round(100 * o["org"] / g, 1),
                 "pct_build_land": round(100 * o["dev"] / g, 1),
                 "named_interests": {k: round(v) for k, v in o["named"].items()},
                 "top_donors": [(k[0], round(v[0]), v[1], v[2]) for k, v in sorted(o["donors"].items(), key=lambda kv: -kv[1][0])[:15]],
                 "same_address_groups": [(round(a), len(n), sorted(n)[:10]) for a, n in
                                         sorted(o["addr"].values(), key=lambda v: -v[0]) if len(n) >= 3][:6]}
json.dump(final, open(OUT, "w", encoding="utf-8"), indent=1)
for to, v in sorted(final.items(), key=lambda kv: (kv[1]["race"], -kv[1]["raised"])):
    print("==", v["race"], to, {k: v[k] for k in v if k not in ("top_donors", "same_address_groups")})
    print("   top:", [(a, b) for a, b, c, d in v["top_donors"][:6]])
    if v["same_address_groups"]:
        print("   groups:", v["same_address_groups"][:3])
