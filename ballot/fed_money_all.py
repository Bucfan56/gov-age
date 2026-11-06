"""Federal money profile for every U.S. House and Senate candidate with 2026 receipts in one state (any-address ballot).
Reads the FEC 2026 bulk files. Prints JSON. Run: py ballot/fed_money_all.py <fec26 folder> [ST, default FL]
The output keeps its Florida-era field names ("florida", "fl_zips"): they mean the candidate's own state."""
import csv, io, json, sys, zipfile
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
D = sys.argv[1]
ST = sys.argv[2] if len(sys.argv) > 2 else "FL"
STREET = __import__("re").compile(r"^\s*\d{1,6}\s+.*\b(ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|BLVD|LN|LANE|CT|COURT|PL|PLACE|WAY|HWY|PKWY)\.?\s*$|^\s*P\.?\s?O\.?\s?BOX\b", 2)
NAME_STREET = __import__("re").compile(r"(,[^0-9]*?)\s+\d{1,6}\s+\S.*$")
CANDS, DIST = {}, {}
with open(f"{D}/weball26.txt", encoding="latin-1") as _fh:
    for _l in _fh:
        _p = _l.rstrip().split("|")
        if _p[18] == ST and _p[0][0] in "HS" and float(_p[5] or 0) > 0:
            CANDS[_p[0]] = _p[1]
            DIST[_p[0]] = _p[19]
ORG_TP = {"C": "Corporate", "L": "Labor", "M": "Membership", "T": "Trade assoc",
          "V": "Cooperative", "W": "Corp w/o stock"}
CMTE_TP = {"Q": "PAC", "N": "PAC", "O": "Super PAC", "Y": "Party", "X": "Party", "V": "Hybrid PAC",
           "W": "Hybrid PAC", "H": "House campaign", "S": "Senate campaign", "P": "Presidential",
           "U": "Single-candidate IE", "I": "IE filer", "Z": "Party non-federal"}


def lines(name):
    with open(f"{D}/{name}", encoding="latin-1") as fh:
        for l in fh:
            yield l.rstrip("\r\n").split("|")


cm = {}
for p in lines("cm.txt"):
    cm[p[0]] = {"name": p[1], "tp": p[9], "dsgn": p[8], "org_tp": p[12], "org": p[13], "cand": p[14]}

summ = {}
for p in lines("weball26.txt"):
    if p[0] in CANDS:
        f = lambda i: float(p[i] or 0)
        summ[p[0]] = {"receipts": f(5), "from_own_jfc": f(6), "spent": f(7), "cash": f(10),
                      "self": f(11) + f(12), "indiv": f(17), "pac": f(25), "party": f(26),
                      "debt": f(16), "through": p[27]}

own = defaultdict(set)
for p in lines("ccl.txt"):
    if p[0] in CANDS and p[5] in ("P", "A"):
        own[p[0]].add(p[3])
ici = {}      # the FEC's own incumbent / challenger / open seat mark
for p in lines("cn.txt"):
    if p[0] in CANDS:
        ici[p[0]] = p[7]
    if p[0] in CANDS and p[9]:
        own[p[0]].add(p[9])
# One person can hold a House id and a Senate id that list the same committee (Gregg Mele ran for Senate in 2024 and House in 2026). Each id gets the committee's gifts, because the race decides which id a card uses.
cmte_to_cands = defaultdict(list)
for k, cs in own.items():
    for c in cs:
        cmte_to_cands[c].append(k)

# committee cheques + PAC-reported independent expenditures
pac = defaultdict(lambda: defaultdict(lambda: {"amt": 0.0, "n": 0}))
for p in lines("itpas2.txt"):
    if len(p) < 17 or p[16] not in CANDS:
        continue
    tp = p[5]
    try:
        amt = float(p[14] or 0)
    except ValueError:
        continue
    g = cm.get(p[0], {})
    key = (p[0], g.get("name", p[7]), tp)
    pac[p[16]][key]["amt"] += amt
    pac[p[16]][key]["n"] += 1

# 24/48-hour independent expenditures (super PACs etc.)
ie = defaultdict(lambda: defaultdict(float))
with open(f"{D}/ie26.csv", encoding="latin-1", newline="") as fh:
    seen = set()
    for r in csv.DictReader(fh):
        if r["cand_id"] not in CANDS:
            continue
        k = (r["spe_id"], r["tran_id"], r["file_num"])
        if (r["spe_id"], r["tran_id"]) in seen and r["amndt_ind"] != "N":
            pass
        seen.add((r["spe_id"], r["tran_id"]))
        try:
            ie[r["cand_id"]][(r["spe_nam"], r["sup_opp"])] += float(r["exp_amo"] or 0)
        except ValueError:
            pass

# The FEC files a committee's PAC gifts and outside spending under whichever of a person's ids the filer named (Mark Harris's are split between two).
# Ids that share a committee are one person, so each gets the whole list. Only an id for the same office and district shares the incumbent mark.
partners = defaultdict(set)
for cands in cmte_to_cands.values():
    for k in cands:
        partners[k].update(cands)
for cid in list(partners):      # follow the links until nothing new turns up
    while True:
        more = set().union(*(partners[k] for k in partners[cid])) - partners[cid]
        if not more:
            break
        partners[cid] |= more
pac_own, ie_own = {k: dict(v) for k, v in pac.items()}, {k: dict(v) for k, v in ie.items()}
for cid, group in partners.items():
    pac[cid], ie[cid] = defaultdict(lambda: {"amt": 0.0, "n": 0}), defaultdict(float)
    for k in group:
        for key, v in pac_own.get(k, {}).items():
            pac[cid][key]["amt"] += v["amt"]
            pac[cid][key]["n"] += v["n"]
        for key, amt in ie_own.get(k, {}).items():
            ie[cid][key] += amt
ici_own = dict(ici)
for cid, group in partners.items():
    if any(ici_own.get(k) == "I" and k[0] == cid[0] and DIST.get(k) == DIST.get(cid) for k in group):
        ici[cid] = "I"

# Land, development, data-center, mining and utility interests, matched literally on the filed employer/occupation.
import re
LAND = re.compile(r"\b(HOMES?|HOMEBUILD\w*|BUILDERS?|DEVELOP(ER|ERS|MENT)|REAL ESTATE|REALT(Y|OR\w*)|LAND (BROKER|DEVELOP\w*|COMPANY|CO)|"
                  r"PROPERTY (DEVELOP\w*|INVEST\w*)|CONSTRUCTION|PAVING|EXCAVAT\w*|ASPHALT|CONCRETE|DATA ?CENTERS?|MINING|PHOSPHATE|MOSAIC|"
                  r"QUARRY|NEXTERA|FLORIDA POWER|FPL|DUKE ENERGY|TECO|TAMPA ELECTRIC|ALABAMA POWER|SOUTHERN COMPANY|PSE&?G|PUBLIC SERVICE ENTERPRISE|PG&?E|PACIFIC GAS|SOUTHERN CALIFORNIA EDISON|SEMPRA|DOMINION ENERGY|LENNAR|PULTE|D\.?R\.? HORTON|TAYLOR MORRISON|NEAL COMMUNITIES|"
                  r"BENDERSON|SCHROEDER|LAKEWOOD RANCH|KOLTER|MATTAMY|MINTO|MERITAGE)\b", re.I)
land = defaultdict(float)

# individual contributions
want = {c.encode() for c in cmte_to_cands}
donors = defaultdict(lambda: defaultdict(lambda: {"amt": 0.0, "n": 0, "emp": "", "occ": "", "city": "", "st": ""}))
geo = defaultdict(lambda: defaultdict(float))
emp = defaultdict(lambda: defaultdict(float))
tot = defaultdict(lambda: {"amt": 0.0, "n": 0})
with zipfile.ZipFile(f"{D}/indiv26.zip") as zf:
    nm = [n for n in zf.namelist() if n.endswith(".txt")][0]
    with zf.open(nm) as fh:
        for raw in fh:
            if raw[:9] not in want:
                continue
            p = raw.decode("latin-1").rstrip("\r\n").split("|")
            if p[6] not in ("IND", "CAN"):
                continue
            try:
                amt = float(p[14] or 0)
            except ValueError:
                continue
            for c in cmte_to_cands[p[0]]:
                st, z = p[9], (p[10] or "")[:5]
                tot[c]["amt"] += amt
                if LAND.search(p[11] or "") or LAND.search(p[12] or ""):
                    land[c] += amt
                    if st == ST and z.isdigit():
                        geo[c]["L" + z] += amt
                tot[c]["n"] += 1
                if st == ST:
                    geo[c]["FL"] += amt
                    if z[:3] == "342":
                        geo[c]["SRQ_MANATEE"] += amt
                    if z.isdigit():
                        geo[c]["z" + z] += amt
                elif st:
                    geo[c]["OUT"] += amt
                    geo[c]["st_" + st] += amt
                k = (NAME_STREET.sub(r"\1", p[7].strip().upper()), z)  # a filer's street typed after a donor's name is never stored
                d = donors[c][k]
                d["amt"] += amt; d["n"] += 1
                emp_name = "" if STREET.search(p[11] or "") else p[11]  # a filer's street address in the employer box is never stored
                d["emp"], d["occ"], d["city"], d["st"] = emp_name, p[12], p[8], st
                e = (emp_name or "").strip().upper()
                if e and e not in ("RETIRED", "NOT EMPLOYED", "SELF-EMPLOYED", "SELF EMPLOYED", "SELF", "NONE", "N/A", "INFORMATION REQUESTED", "HOMEMAKER"):
                    emp[c][e] += amt

out = {}
ranked = sorted(CANDS.items(), key=lambda kv: summ[kv[0]]["receipts"])
top_id = {name: cid for cid, name in ranked}      # same name twice: the id with the most money keeps the plain name, the others carry their id
for cid, name in ranked:
    ds = sorted(donors[cid].items(), key=lambda kv: -kv[1]["amt"])
    big = [v for k, v in ds if v["amt"] >= 2000]
    t = tot[cid]["amt"] or 1
    g = geo[cid]
    out_states = sorted(((k[3:], v) for k, v in g.items() if k.startswith("st_")), key=lambda kv: -kv[1])[:6]
    pacs = sorted(pac[cid].items(), key=lambda kv: -kv[1]["amt"])
    out[name if top_id[name] == cid else f"{name} [{cid}]"] = {
        "fec_id": cid, "ici": ici.get(cid), "district": DIST.get(cid), "committees": sorted(own[cid]), "summary": summ.get(cid),
        "itemized_indiv": {"amt": round(tot[cid]["amt"]), "rows": tot[cid]["n"], "donors": len(ds)},
        "share": {"florida": round(100 * g["FL"] / t, 1), "sarasota_manatee_342xx": round(100 * g["SRQ_MANATEE"] / t, 1),
                  "fl_zips": {k[1:]: round(v) for k, v in g.items() if k.startswith("z") and v >= 1}, "land_amt": round(land[cid]),
                  "land_fl_zips": {k[1:]: round(v) for k, v in g.items() if k.startswith("L") and v >= 1}, "out_of_state": round(100 * g["OUT"] / t, 1),
                  "top_out_states": [(s, round(v)) for s, v in out_states],
                  "donors_2000plus_share": round(100 * sum(v["amt"] for v in big) / t, 1),
                  "donors_2000plus_count": len(big)},
        "top_donors": [{"name": k[0], "amt": round(v["amt"]), "n": v["n"], "emp": v["emp"], "occ": v["occ"],
                        "city": v["city"], "st": v["st"]} for k, v in ds[:25]],
        "top_employers": [(e, round(a)) for e, a in sorted(emp[cid].items(), key=lambda kv: -kv[1])[:20]],
        "committee_money": [{"cmte": k[0], "name": k[1], "type": k[2],
                             "giver_type": CMTE_TP.get(cm.get(k[0], {}).get("tp", ""), cm.get(k[0], {}).get("tp", "")),
                             "org_type": ORG_TP.get(cm.get(k[0], {}).get("org_tp", ""), ""),
                             "connected_org": cm.get(k[0], {}).get("org", ""),
                             "amt": round(v["amt"]), "n": v["n"]} for k, v in pacs[:80]],
        "outside_spending_24_48hr": sorted([{"spender": k[0], "support_oppose": k[1], "amt": round(v)}
                                            for k, v in ie[cid].items()], key=lambda r: -r["amt"])[:25],
    }
json.dump(out, sys.stdout, indent=1)
