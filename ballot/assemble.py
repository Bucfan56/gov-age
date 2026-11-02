"""Merge money + research into ballot-34221.json for build_ballot.py."""
import json, re, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S = sys.argv[1]
OUT = sys.argv[2]
J = lambda p: json.load(open(f"{S}/{p}", encoding="utf-8"))
fed, fl, loc, pc = J("fed_money.json"), J("fl_money.json"), J("local_money.json"), J("pc/pc.json")
R = {}
for f in ("A_federal_governor", "B_cabinet_judges", "C_legislature", "D_local_measures"):
    try:
        d = J(f"research/{f}.json")
    except FileNotFoundError:
        print("missing", f); continue
    for c in d.get("candidates", []):
        R[c["name"]] = c
    if d.get("measures"):
        R["__measures__"] = d["measures"]
    if d.get("district_coverage"):
        R.setdefault("__coverage__", []).append(d["district_coverage"])

OWNER_OK = re.compile(r"rumble\.com/(Owen|TheAlexJonesShowLive|c/StewPeters)|alexjoneslive|stewpeters|infowars", re.I)
NOHIT = re.compile(r"^\s*(no mention|not searched|no result|none found|searched)", re.I)


def clean(c):
    c = dict(c)
    c["local_ties"] = re.sub(r"\s*Not a carpetbagger\.?", "", c.get("local_ties") or "")
    hits, searched = [], list(c.get("owner_sources_searched") or [])
    for h in c.get("owner_sources") or []:
        src, says, title = h.get("source", ""), h.get("says", ""), h.get("title", "")
        if NOHIT.match(says) or NOHIT.match(title) or "no mention" in title.lower():
            searched.append(f"{src}: {says or title}")
            continue
        if not OWNER_OK.search((h.get("url") or "") + " " + src) or "NOT one of" in src or "Media Matters" in src:
            continue  # not from the owner's five sources
        if "rumble.com/search" in (h.get("url") or "") and "channel" in src.lower() and "owner" not in src.lower():
            continue
        if re.search(r"is not mentioned|does not mention|unverified|could not be confirmed|not shown where", says, re.I):
            searched.append(f"{src}: {title[:60]} (does not clearly name this candidate)")
            continue
        if any(x.get("url") == h.get("url") for x in hits):
            continue
        hits.append(h)
    c["owner_sources"], c["owner_sources_searched"] = hits, searched[:6]
    keep, opinion = [], []
    for x in c.get("controversies") or []:
        t = x.get("text", "")
        if re.match(r"\s*(none|no (controvers|ethics|jqc|legal|lawsuit))", t, re.I) and len(t) < 260:
            continue
        if re.search(r"editorial|\bcolumn\b|\(opinion\)|endorsement\)", t, re.I) and x.get("status") == "allegation":
            opinion.append({"text": t, "url": x.get("url")}); continue
        if re.match(r"\s*Declined to comment", t):
            continue
        if "politifact" in (x.get("url") or "").lower():
            x = dict(x, status="fact-checked")
        keep.append(x)
    c["controversies"], c["press_opinion"] = keep, opinion
    c["foreign_ties"] = [x for x in c.get("foreign_ties") or []
                         if not re.match(r"\s*(none|no foreign|no documented)", x.get("text", ""), re.I)] or \
                        [{"text": "None documented in the public records searched (FARA filings, foreign-government payments, state-owned business, foreign-agent donors)."}]
    return c


HOPE = ("Hope Florida: in 2024 Centene paid $10M to the Hope Florida Foundation alongside a Medicaid settlement; "
        "money then moved through two nonprofits to Keep Florida Clean, a political committee {role}. A Leon County "
        "grand jury report (leaked Aug 2026) called it misappropriated and {mood}, but indicted no one. On Oct 7, 2026 "
        "the 1st District Court of Appeal ordered the report expunged and rejected its finding that the money was "
        "diverted; a request for full-court rehearing is pending. No one has been charged.")

def fix_hope(c, role, mood):
    out = [x for x in c["controversies"] if "Hope Florida" not in x.get("text", "")]
    out.insert(0, {"text": HOPE.format(role=role, mood=mood), "status": "allegation",
                   "url": "https://www.wgcu.org/government-politics/2026-10-07/state-appeals-court-expunges-hope-florida-grand-jury-report"})
    c["controversies"] = out


def F(n):  # federal money block
    v = fed[n]; s = v["summary"]; sh = v["share"]
    unit = s["indiv"] - v["itemized_indiv"]["amt"]
    pacs = [[tc(x["name"])[:70], x["amt"], (x["org_type"] or x["giver_type"])] for x in v["committee_money"] if x["type"] == "24K"][:12]
    foreign = []
    for x in v["committee_money"]:
        for k, lab in (("CRH AMERICAS", "CRH plc, headquartered in Ireland"), ("UBS AMERICAS", "UBS Group, Switzerland"),
                       ("TOYOTA MOTOR NORTH AMERICA", "Toyota Motor Corp., Japan")):
            if k in x["name"]:
                foreign.append({"text": f"{tc(x['name'])} — {usd(x['amt'])}. PAC of the U.S. arm of {lab}. By law it can only be funded by U.S. employees; listed because the parent company is foreign."})
    return {"raised": s["receipts"], "through": f"FEC totals through {s['through']}",
            "fl_pct": sh["florida"], "out_pct": sh["out_of_state"], "local_pct": sh["sarasota_manatee_342xx"],
            "local_label": "from Sarasota–Manatee zips (342xx)",
            "big_pct": sh["donors_2000plus_share"], "big_label": "of itemized individual money from people giving $2,000+",
            "org_pct": round(100 * (s["pac"] + s["party"]) / s["receipts"], 1) if s["receipts"] else None,
            "org_label": "from PACs & party committees",
            "note": (f"Individuals gave {usd(s['indiv'])}; {usd(max(unit, 0))} of it came in amounts too small to be itemized "
                     f"(under $200 per donor) or is not yet processed. PAC money {usd(s['pac'])}; candidate's own money {usd(s['self'])}; "
                     f"transfers from joint fundraising committees {usd(s['from_own_jfc'])}. Percentages describe itemized individual gifts, "
                     "which the FEC has processed through about July 2026."),
            "top": [[tc(x["name"]), x["amt"], f"{x['occ'] or x['emp']} · {tc(x['city'])}, {x['st']}"] for x in v["top_donors"][:10]],
            "pacs": pacs, "outside": [[o["spender"], o["support_oppose"], o["amt"]] for o in v["outside_spending_24_48hr"][:10]],
            "foreign": foreign, "source": "FEC bulk files downloaded Nov 2, 2026",
            "source_url": f"https://www.fec.gov/data/candidate/{v['fec_id']}/?cycle=2026"}



KEEP_UP = {"PAC","LLC","NRSC","RJC","ASA","PNC","UPS","GOP","GOPAC","GEO","II","III","USA","US","PC","PA","LP","LLP","AFL-CIO",
           "SEIU","AIF","FPL","TECO","SMR","LWR","CPA","FEA","HCA","RTX","AT&T","DEC","NABPAC","PLLC","IV","JM","CRH","UBS","ACA"}
STATES = set("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC PR".split())
def tc(s):
    out = []
    for w in str(s).split():
        core = re.sub(r"[^A-Za-z&-]", "", w).upper()
        if core in ("INC", "CO", "CORP", "LTD", "MR", "DR", "JR", "SR"):
            out.append(w[:1].upper() + w[1:].lower())
        elif core in KEEP_UP or w.startswith("(") or (core in STATES and len(out) and out[-1].endswith(",")):
            out.append(w.upper())
        elif re.fullmatch(r"\(?[A-Z]{2,5}\)?", w) and not re.search(r"[AEIOU]", w[1:] if len(w) > 2 else w):
            out.append(w.upper())
        else:
            out.append(w[:1].upper() + w[1:].lower() if w.isupper() or w.islower() else w)
    return " ".join(out)


def usd(v):
    v = float(v)
    return f"${v/1e6:,.1f}M" if v >= 1e6 else (f"${v/1e3:,.0f}k" if v >= 1e4 else f"${v:,.0f}")


def ST(key, committee=None, extra=None):  # Florida state money block
    v = fl[key]
    m = {"raised": v["raised"], "through": f"campaign account, reports through {v['through'][:4]}-{v['through'][4:6]}-{v['through'][6:]}",
         "local_pct": v["pct_manatee"], "fl_pct": v["pct_fl"], "out_pct": v["pct_out_state"], "org_pct": v["pct_org"],
         "build_land_pct": v["pct_build_land"], "loans": v["loans"] or None,
         "top": [[tc(a), b, f"x{n} · {tc(d.split(' · ')[0])}"] for a, b, n, d in v["top_donors"][:10]],
         "groups": [[g[0], g[1], [tc(x) for x in g[2]]] for g in v["same_address_groups"][:3]],
         "note": "Includes primary and general. 'State of Florida' / 'Department of State' lines are public matching funds; "
                 "party-committee lines are mostly in-kind staff and mail.",
         "source": "Florida Division of Elections, pulled Nov 2, 2026",
         "source_url": "https://dos.elections.myflorida.com/campaign-finance/contributions/"}
    if committee and committee in pc:
        p = pc[committee]
        m["committee"] = {"name": committee, "total": float(p["totals"][0][2]) if p["totals"] else None,
                          "span": f"{p['span'][0][:4]}–{p['span'][1][:4]}",
                          "top": [[tc(a), b, tc(w)] for a, b, n, w in p["top"][:12]]}
    if extra:
        m.update(extra)
    return m


def L(key):  # Manatee local money block
    v = next(val for k, val in loc.items() if key in k)
    groups = []
    return {"raised": v["raised"], "through": f"county reports, last item {v['last_report_item']}",
            "local_pct": v["pct_manatee"], "out_pct": v["pct_out_state"], "org_pct": v["pct_business_committee"],
            "build_land_pct": v["pct_building_land_tagged"], "loans": v["loans"] or None,
            "top": [[tc(re.sub(r"\s*\[.*?\]", "", a)), b, re.search(r"\](.*)", a).group(1).strip() if "]" in a else ""] for a, b, n in v["top_donors"][:10]],
            "source": "Manatee County Supervisor of Elections campaign reports, pulled Nov 2, 2026",
            "source_url": "https://www.votemanatee.gov/search-financial-reports/"}


def rfind(name):
    if name in R:
        return R[name]
    last = re.sub(r"[^A-Za-z' -]", "", name).replace(" Sr", "").split()[-1].lower()
    first = name.split()[0].strip('"').lower()
    hits = [k for k in R if not k.startswith("__") and last in k.lower() and (first in k.lower() or len([x for x in R if last in x.lower()]) == 1)]
    if len(hits) == 1:
        return R[hits[0]]
    print("NO RESEARCH MATCH:", name, hits)
    return {"name": name}


def cand(name, money=None, **kw):
    c = clean(rfind(name))
    c["name"] = kw.pop("display", name)
    c["money"] = money
    c.update(kw)
    return c


json.dump({"R": {k: v for k, v in R.items() if not k.startswith("__")}, "coverage": R.get("__coverage__"), "measures": R.get("__measures__")},
          open(f"{S}/_research_index.json", "w", encoding="utf-8"), indent=0)
exec(open(f"{S}/races.py", encoding="utf-8").read())
