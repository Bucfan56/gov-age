"""Manatee local candidate money from the Supervisor of Elections (VoterFocus) export."""
import csv, html, json, re, sys
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SRC, OUT = sys.argv[1], sys.argv[2]
WANT = ["Poulton", "Bellamy", "Arnold, Elizabeth", "Lindroos", "Ballard", "Smith Sr, Charles",
        "Spray", "Jefferson", "Joiner", "Jones, Sheldon", "O&#39;Quinn", "O'Quinn", "Richards, Charles",
        "Johnson, Scott", "Protect Water", "Mullis", "Bedinghaus"]
MANATEE_ZIPS = {"34201", "34202", "34203", "34204", "34205", "34206", "34207", "34208", "34209",
                "34210", "34211", "34212", "34215", "34216", "34217", "34218", "34219", "34220",
                "34221", "34222", "34243", "34250", "34251", "34264", "34270", "34280", "34281", "34282"}
# Name / occupation markers of the building and land business. Deliberately literal: a
# donor is tagged only if the filed name or occupation says so, never by inference.
DEV = re.compile(r"\b(HOMES?|BUILDERS?|BUILDING|DEVELOP\w*|CONSTRUCT\w*|LAND\b|LANDS\b|REALTY|REAL ESTATE|"
                 r"REALTOR\w*|PAVING|EXCAVAT\w*|SITE ?WORK|ENGINEER\w*|SURVEY\w*|CONCRETE|ASPHALT|"
                 r"PROPERT(Y|IES)|INVESTMENTS?|RANCH|COMMUNITIES|HOLDINGS|PARTNERS|CAPITAL|"
                 r"NEAL|BENDERSON|LENNAR|PULTE|HORTON|TAYLOR MORRISON|MATTAMY|SMR|SCHROEDER|"
                 r"LAKEWOOD RANCH|KOLTER|STOCK DEVELOPMENT|MINTO|DIVOSTA|MERITAGE|M/I HOMES|"
                 r"CARLISLE|PAT NEAL|NEAL COMMUNITIES|DUNCAN SEAWALL|TITLE)\b", re.I)

rows = list(csv.DictReader(open(SRC, encoding="utf-8", errors="replace")))
out = {}
for r in rows:
    cand = html.unescape(r["Candidate"])
    hit = next((w for w in WANT if html.unescape(w) in cand), None)
    if not hit or r["Date"][-4:] < "2025":
        continue
    o = out.setdefault(cand, {"office": r["Office"], "gift": 0.0, "n": 0, "loans": 0.0, "inkind": 0.0,
                              "manatee": 0.0, "fl_other": 0.0, "out_state": 0.0, "business": 0.0,
                              "dev_tagged": 0.0, "self": 0.0, "last_date": "", "donors": defaultdict(lambda: {"amt": 0.0, "n": 0}),
                              "dev_list": defaultdict(float)})
    try:
        amt = float(r["Amount"].replace(",", ""))
    except ValueError:
        continue
    ctype, ktype = r["Contribution Type"], r["Contributor Type"]
    name = " ".join(x for x in [r["First Name"].strip(), r["Contributor LName"].strip()] if x) or r["Contributor LName"]
    name = html.unescape(name).upper()
    m, d, y = r["Date"].split("/")
    iso = f"{y}-{int(m):02d}-{int(d):02d}"
    o["last_date"] = max(o["last_date"], iso)
    if ctype == "Loan":
        o["loans"] += amt
        continue
    if ctype in ("Interest", "Refund"):
        continue
    o["gift"] += amt; o["n"] += 1
    if ctype == "In Kind":
        o["inkind"] += amt
    z, st = (r["Zip"] or "")[:5], (r["State"] or "").upper()
    if z in MANATEE_ZIPS:
        o["manatee"] += amt
    elif st == "FL":
        o["fl_other"] += amt
    elif st:
        o["out_state"] += amt
    if ktype in ("Business", "Committee", "Polical Party", "Other"):
        o["business"] += amt
    lastname = cand.split(",")[0].strip().upper()
    if lastname and lastname in name:
        o["self"] += amt
    label = f"{name} ({r['City'].strip().title()}) [{ktype or '?'}] {r['Occupation'].strip()}"
    o["donors"][label]["amt"] += amt; o["donors"][label]["n"] += 1
    if DEV.search(name) or DEV.search(r["Occupation"] or ""):
        o["dev_tagged"] += amt
        o["dev_list"][label] += amt

final = {}
for cand, o in out.items():
    g = o["gift"] or 1
    ds = sorted(o["donors"].items(), key=lambda kv: -kv[1]["amt"])
    final[cand] = {"office": o["office"], "raised": round(o["gift"]), "gifts": o["n"], "loans": round(o["loans"]),
                   "in_kind": round(o["inkind"]), "last_report_item": o["last_date"],
                   "pct_manatee": round(100 * o["manatee"] / g, 1), "pct_fl_other": round(100 * o["fl_other"] / g, 1),
                   "pct_out_state": round(100 * o["out_state"] / g, 1),
                   "pct_business_committee": round(100 * o["business"] / g, 1),
                   "pct_building_land_tagged": round(100 * o["dev_tagged"] / g, 1),
                   "self_and_same_surname": round(o["self"]),
                   "top_donors": [(k, round(v["amt"]), v["n"]) for k, v in ds[:15]],
                   "building_land_tagged": sorted(((k, round(v)) for k, v in o["dev_list"].items()), key=lambda kv: -kv[1])[:20]}
json.dump(final, open(OUT, "w", encoding="utf-8"), indent=1)
for c, v in final.items():
    print("==", c, {k: v[k] for k in v if k not in ("top_donors", "building_land_tagged")})
    print("   top:", v["top_donors"][:8])
    print("   build/land:", v["building_land_tagged"][:10])
