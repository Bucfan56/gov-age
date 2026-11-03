#!/usr/bin/env python3
"""
Build the any-address Florida ballot: ballot.html plus per-district data files in fl/.

    py build_florida.py SCRATCH

SCRATCH holds today's pulls and research (see ballot/README.md):
  fed_money_all.json      FEC bulk summary for every Florida federal candidate (ballot/fed_money_all.py)
  fl_all/fl_STS*.json, fl_STR*.json   Division of Elections rows per district (ballot/fl_money_all.py)
  geo/zip_districts.json  every Florida ZIP centroid -> congressional / senate / house district + county
  geo/soe.json            every county Supervisor of Elections (website, phone, address)
  research2/*.json        research slices (us_house, legislature, manatee, votes40) per research2/SCHEMA.md

The Palmetto races in ballot-34221.json are reused as-is. Scoring is build_ballot.score(), unchanged:
the Local meter's "home" is the district's own ZIP codes for U.S. House and Legislature races.
"""
import glob, json, os, re, sys, unicodedata, urllib.request
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
import build_ballot as B  # noqa: E402

S = Path(sys.argv[1])
OUT = ROOT / "fl"
PHOTOS = ROOT / "ballot" / "photos"


def load(p, default=None):
    p = Path(p)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:          # a research slice mid-rewrite: say so, never pretend it was empty
        print(f"!! {p.name} is not valid JSON right now ({e}); skipped this run", file=sys.stderr)
        return default


def fold(s):
    return unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode().lower()


def lastname(n):
    w = re.sub(r'"[^"]*"|\([^)]*\)', " ", fold(n))
    w = [x for x in re.split(r"[^a-z'-]+", w) if x and x not in ("jr", "sr", "ii", "iii", "iv", "md", "facs", "dr", "mr", "mrs", "ms")]
    return w[-1] if w else ""


def slug(n):
    return re.sub(r"[^a-z]+", "-", re.sub(r'"[^"]*"', "", fold(n))).strip("-")


ZIPS = load(S / "geo" / "zip_districts.json", {})
SOE = load(S / "geo" / "soe.json", {})
FED = load(S / "fed_money_all.json", {})
FED_BY_ID = {v["fec_id"]: v for v in FED.values()}
VOTES40 = (load(S / "research2" / "votes40.json", {}) or {}).get("candidates", {})


def zips_where(**kw):
    return {z for z, v in ZIPS.items() if all(v.get(k) == x for k, x in kw.items())}


# ---------------- photos ----------------
photo_map = load(ROOT / "ballot" / "photos.json", {})


FOUND = {}
for _f in ("photos_found_a.json", "photos_found_b.json"):
    FOUND.update((load(S / "research3" / _f, {}) or {}).get("photos", {}))


def photo(c):
    if c["name"] in photo_map:
        return photo_map[c["name"]]
    p = c.get("photo") or {}
    if not (isinstance(p, dict) and p.get("url")) and c["name"] in FOUND:
        p = FOUND[c["name"]]
    url = p.get("url") if isinstance(p, dict) else None
    if not url or "SubmitPhoto" in url or "BP-Initials" in url:
        return None
    ext = (re.search(r"\.(png|jpe?g|webp)(\?|$)", url, re.I) or [None, "jpg"])[1].lower().replace("jpeg", "jpg")
    f = slug(c["name"]) + "." + ext
    if not (PHOTOS / f).exists():
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "gov-age-ballot/1.0 (tyler@spartanstudios.com)"})
            data = urllib.request.urlopen(req, timeout=30).read()
            if len(data) < 1500:
                return None
            (PHOTOS / f).write_bytes(data)
        except Exception as e:
            print("   photo failed", c["name"], e, file=sys.stderr)
            return None
    photo_map[c["name"]] = {"f": f, "credit": p.get("credit") or "public source", "page": url}
    return photo_map[c["name"]]


# ---------------- money ----------------
def fed_money(fid, home):
    v = FED_BY_ID.get(fid)
    if not v or not v.get("summary"):
        return None
    s, sh = v["summary"], v["share"]
    t = v["itemized_indiv"]["amt"] or 1
    loc = round(100 * sum(a for z, a in sh.get("fl_zips", {}).items() if z in home) / t, 1)
    lz = sh.get("land_fl_zips", {})
    loc_clean = round(100 * sum(a for z, a in sh.get("fl_zips", {}).items() if z in home and z not in ()) / t - 100 * sum(a for z, a in lz.items() if z in home) / t, 1)
    pacs = [[B_tc(x["name"])[:70], x["amt"], (x["org_type"] or x["giver_type"])] for x in v["committee_money"] if x["type"] == "24K"][:12]
    return {"raised": s["receipts"], "through": f"FEC totals through {s['through']}",
            "fl_pct": sh["florida"], "out_pct": sh["out_of_state"], "local_pct": loc, "local_clean_pct": max(0, loc_clean),
            "fl_clean_pct": max(0, round(sh["florida"] - 100 * sum(lz.values()) / t, 1)), "land_pct": round(100 * sh.get("land_amt", 0) / t, 1),
            "big_pct": sh["donors_2000plus_share"],
            "org_pct": round(100 * (s["pac"] + s["party"]) / s["receipts"], 1) if s["receipts"] else None,
            "top": [[B_tc(x["name"]), x["amt"], f"{x['occ'] or x['emp']} · {B_tc(x['city'])}, {x['st']}"] for x in v["top_donors"][:10]],
            "pacs": pacs, "outside": [[o["spender"], o["support_oppose"], o["amt"]] for o in v["outside_spending_24_48hr"][:10]],
            "note": f"Individuals gave ${s['indiv']:,.0f}; PAC money ${s['pac']:,.0f}; candidate's own money ${s['self']:,.0f}. "
                    "Percentages describe itemized individual gifts, which the FEC has processed through about July 2026.",
            "source": "FEC bulk files downloaded Nov 2, 2026", "source_url": f"https://www.fec.gov/data/candidate/{fid}/?cycle=2026"}


def B_tc(s):
    s = str(s or "").strip()
    return " ".join(w if (len(w) <= 3 and w.isupper() and w in ("PAC", "LLC", "USA", "GOP", "II", "III", "PA", "LP")) else w.capitalize() for w in s.split())


SUFFIX = re.compile(r"\s*\([A-Z]{2,4}\)\s*\([A-Z]{2,4}\)\s*$")
ORG = re.compile(r"\b(LLC|L\.L\.C|INC|CORP|CORPORATION|COMPANY|CO\.|P\.?A\.?|PLLC|LLP|LP|LTD|PAC|COMMITTEE|ASSOCIATION|ASSN|PARTY|FUND|GROUP|"
                 r"HOLDINGS|PARTNERS|TRUST|FOUNDATION|ENTERPRISES|INDUSTRIES|SERVICES|SOLUTIONS|FLORIDA|COUNCIL|UNION|FEDERATION|CHAMBER)\b", re.I)
DEV = re.compile(r"\b(HOMES?|HOMEBUILD\w*|BUILDERS?|BUILDING|DEVELOP\w*|CONSTRUCT\w*|LAND|LANDS|REALTY|REAL ESTATE|REALTOR\w*|PAVING|EXCAVAT\w*|"
                 r"ENGINEER\w*|CONCRETE|ASPHALT|PROPERT(Y|IES)|COMMUNITIES|DATA ?CENTERS?|MINING|PHOSPHATE|MOSAIC|QUARRY|NEXTERA|FLORIDA POWER|FPL|"
                 r"DUKE ENERGY|TECO|TAMPA ELECTRIC|LENNAR|PULTE|HORTON|TAYLOR MORRISON|NEAL COMMUNITIES|BENDERSON|SCHROEDER|LAKEWOOD RANCH|KOLTER|MATTAMY|MINTO)\b", re.I)


def fl_district_money(path, home):
    """Same arithmetic as ballot/fl_analyze.py, with 'home' = the district's ZIP codes."""
    blob = load(path)
    if not blob:
        return {}
    out = {}
    for r in blob["rows"]:
        to = SUFFIX.sub("", (r.get("Candidate/Committee") or "").strip()).strip()
        if not to:
            continue
        typ = (r.get("Typ") or "").strip()
        try:
            amt = float((r.get("Amount") or "0").replace("$", "").replace(",", ""))
        except ValueError:
            continue
        o = out.setdefault(to, {"gift": 0.0, "loans": 0.0, "home": 0.0, "fl": 0.0, "out": 0.0, "org": 0.0, "dev": 0.0, "home_dev": 0.0,
                                "donors": defaultdict(lambda: [0.0, 0, ""]), "last": ""})
        if typ == "LOA":
            o["loans"] += amt
            continue
        if typ == "INT":
            continue
        name = (r.get("Contributor Name") or "").strip()
        csz = (r.get("City State Zip") or "").strip()
        m = re.search(r"\b([A-Z]{2})\s+(\d{5})", csz)
        st, z = (m.group(1), m.group(2)) if m else ("", "")
        o["gift"] += amt
        dt = r.get("Date") or ""
        if len(dt) == 10:
            o["last"] = max(o["last"], dt[6:] + "-" + dt[:2] + "-" + dt[3:5])
        if z in home:
            o["home"] += amt
        if st == "FL":
            o["fl"] += amt
        elif st:
            o["out"] += amt
        if ORG.search(name):
            o["org"] += amt
        if DEV.search(name) or DEV.search(r.get("Occupation") or ""):
            o["dev"] += amt
            if z in home:
                o["home_dev"] += amt
        d = o["donors"][(name.upper(), z)]
        d[0] += amt; d[1] += 1; d[2] = csz
    res = {}
    for to, o in out.items():
        g = o["gift"] or 1
        res[to] = {"raised": round(o["gift"]), "through": f"campaign account, reports through {o['last']}",
                   "local_pct": round(100 * o["home"] / g, 1), "fl_pct": round(100 * o["fl"] / g, 1),
                   "out_pct": round(100 * o["out"] / g, 1), "org_pct": round(100 * o["org"] / g, 1),
                   "build_land_pct": round(100 * o["dev"] / g, 1), "land_pct": round(100 * o["dev"] / g, 1),
                   "local_clean_pct": round(100 * (o["home"] - o["home_dev"]) / g, 1), "loans": round(o["loans"]) or None,
                   "top": [[B_tc(k[0]), round(v[0]), f"x{v[1]} · {B_tc(v[2])}"] for k, v in sorted(o["donors"].items(), key=lambda kv: -kv[1][0])[:10]],
                   "note": "Includes primary and general. 'State of Florida' lines are public matching funds; party-committee lines are mostly in-kind staff and mail.",
                   "source": "Florida Division of Elections, pulled Nov 3, 2026",
                   "source_url": "https://dos.elections.myflorida.com/campaign-finance/contributions/"}
    return res


def match_fl(c, pool):
    ln = lastname(c.get("fl_doe_name") or c["name"])
    hits = [k for k in pool if ln and ln in re.findall(r"[a-z'-]+", fold(k))]
    if len(hits) > 1:
        fn = fold(c["name"]).split()[0]
        hits = [k for k in hits if fn in fold(k)] or hits[:1]
    return pool[hits[0]] if hits else None


# ---------------- candidates from research slices ----------------
KEEP = ("name", "party", "incumbent", "bio", "local_ties", "record", "money_notes", "controversies", "foreign_ties",
        "endorsements", "local_issue_stance", "owner_sources", "owner_sources_searched", "gaps", "press_opinion", "votes", "social", "running_mate")


def norm_cand(c):
    o = {k: c[k] for k in KEEP if c.get(k) not in (None, "", [], {})}
    o.setdefault("party", "")
    for k in ("record", "money_notes", "controversies", "foreign_ties", "endorsements", "press_opinion", "local_issue_stance"):
        if isinstance(o.get(k), list):
            o[k] = [x if isinstance(x, dict) else {"text": str(x)} for x in o[k]]
    o["votes"] = [v for v in (c.get("votes") or []) + (c.get("votes_state") or []) if isinstance(v, dict) and v.get("vote") and v.get("url")]
    return o


SWEEP = load(S / "sweep_owner.json", {}) or {}


def owner_sweep(c):
    """Add today's scripted check of the owner's sources (full-name matches only) to a candidate."""
    if c["name"] not in set(SWEEP.get("names", [])):
        return
    have = {x.get("url") for x in c.get("owner_sources") or []}
    c["owner_sources"] = (c.get("owner_sources") or []) + [x for x in SWEEP.get("hits", {}).get(c["name"], []) if x["url"] not in have]
    # a correction (e.g. a retraction) overrides what an item says wherever it came from, and pinned items lead
    for x in c["owner_sources"]:
        if x.get("url") in SWEEP.get("notes", {}):
            x["says"] = SWEEP["notes"][x["url"]]
    c["owner_sources"].sort(key=lambda x: not x.get("pin"))
    c["owner_sources_searched"] = sorted(set(c.get("owner_sources_searched") or []) | set(SWEEP.get("sites", [])))
    if not c["owner_sources"]:
        c.pop("owner_sources")


def score_race(rid, group, cands, home_label):
    B.HOME[rid] = ("local", home_label)
    for c in cands:
        owner_sweep(c)
        c["score"] = B.score(c, rid, None, B.MIN_RAISED[group])
    ranked = sorted(cands, key=lambda c: -(c["score"]["overall"] if c["score"]["overall"] is not None else -1))
    for i, c in enumerate(ranked):
        c["rank"] = i + 1 if c["score"]["overall"] is not None else None
    return ranked


# The Division of Elections' own 2026 General candidate list (canlist.asp, statuses Qualified + Elected/Unopposed)
# is the authority on WHO is on the ballot; research only adds what we know about them.
CANLIST = load(S / "geo" / "canlist.json", [])
OFFICE = {"usr": "United States Representative", "sts": "State Senator", "str": "State Representative"}


def official(k, n):
    return [o for o in CANLIST if o["office"] == OFFICE[k] and o["district"] == n]


def reconcile(k, n, cands, raw):
    """Keep research candidates the state lists, add listed ones research missed, label write-ins."""
    offl = official(k, n)
    if not CANLIST:
        return cands, ""
    if not offl:
        print(f"   {k}-{n}: not on the 2026 general list; dropped", file=sys.stderr)
        return [], ""
    keep, used = [], set()
    for c in cands:
        ln = lastname(c["name"])
        o = next((o for i, o in enumerate(offl) if i not in used and ln in re.findall(r"[a-z'-]+", fold(o["last"]))), None)
        if not o:
            print(f"   {k}-{n}: {c['name']} not on the state list; dropped", file=sys.stderr)
            continue
        used.add(offl.index(o))
        if o["party"] == "WRI":
            c["party"] = "Write-in"
        elif o["party"]:
            c["party"] = o["party"]
        c["incumbent"] = o["inc"] or c.get("incumbent", False)
        keep.append(c)
    for i, o in enumerate(offl):
        if i in used:
            continue
        nm = f"{o['first']} {o['last']}"
        print(f"   {k}-{n}: added {nm} from the state list", file=sys.stderr)
        keep.append({"name": nm, "party": "Write-in" if o["party"] == "WRI" else o["party"], "incumbent": o["inc"],
                     "gaps": "On the state's candidate list; not yet researched for this guide."})
        raw[nm] = {"name": nm, "fl_doe_name": nm}
    if any(o.get("special") for o in offl):
        return keep, "Special election to fill the rest of this Senate term (Division of Elections election 20261103-S01)."
    unopp = all(o["general"] == "Unopposed" for o in offl)
    return keep, "Unopposed: this seat was decided without a general-election contest, so it won't be on your ballot." if unopp else ""


def research_races(fname, kind):
    blob = load(S / "research2" / fname, {}) or {}
    races = []
    for r in blob.get("races", []):
        rid = r.get("id", "")
        m = re.match(r"fl-(usr|sts|str)-0*(\d+)$", rid)
        if not m:
            continue
        k, n = m.group(1), int(m.group(2))
        raw = {c["name"]: c for c in r.get("candidates", []) if c.get("name")}
        cands, unopp_note = reconcile(k, n, [norm_cand(c) for c in r.get("candidates", []) if c.get("name")], raw)
        if not cands:
            continue
        if unopp_note:
            r["note"] = unopp_note
        if k == "usr":
            home = zips_where(cd=n)
            for c in cands:
                c["money"] = fed_money(raw[c["name"]].get("fec_id"), home) or {}
            group, title, short, where, label = "federal", f"U.S. House, District {n}", f"U.S. House {n}", {"cd": n}, f"from District {n} ZIP codes"
        else:
            home = zips_where(**({"sd": n} if k == "sts" else {"hd": n}))
            pool = fl_district_money(S / "fl_all" / f"fl_{k.upper()}{n}.json", home)
            for c in cands:
                c["money"] = match_fl(raw[c["name"]], pool) or {}
            group = "legislature"
            title = f"State {'Senate' if k == 'sts' else 'House'}, District {n}"
            short = f"State {'Senate' if k == 'sts' else 'House'} {n}"
            where = {"sd": n} if k == "sts" else {"hd": n}
            label = f"from District {n} ZIP codes"
        for c in cands:
            ph = photo(dict(raw[c["name"]], name=c["name"]))
            if ph:
                c["photo"] = ph
        key = f"{k}-{n}"
        ranked = score_race(key, group, cands, label)
        wi = sum(1 for c in cands if c.get("party") == "Write-in")
        sub = "Unopposed: not on ballot" if unopp_note.startswith("Unopposed") else "Special election · " if unopp_note.startswith("Special") else ""
        sub +=  "" if unopp_note.startswith("Unopposed") else f"{len(cands) - wi} on ballot" + (f" + {wi} write-in" if wi else "")
        races.append({"kind": "race", "group": group, "id": key, "title": title, "short": short, "sub": sub, "everyone": True,
                      "where": where, "note": r.get("note") or ("Write-in candidates aren't printed on the ballot: you'd write their name on the blank line." if wi else ""),
                      "cands": ranked})
    return races, blob.get("done"), blob.get("notes", [])


LOCAL = load(S / "local_money_all.json", {})


def add_land(c):
    """Palmetto candidates: land shares from today's federal rescan, or the state/county land tags already computed."""
    m = c.get("money") or {}
    if not m or "land_pct" in m:
        return
    fid = (re.search(r"/candidate/([A-Z0-9]+)/", m.get("source_url") or "") or [None, None])[1]
    v = FED_BY_ID.get(fid) if fid else None
    if v:
        t = v["itemized_indiv"]["amt"] or 1
        lz = v["share"].get("land_fl_zips", {})
        m["land_pct"] = round(100 * v["share"].get("land_amt", 0) / t, 1)
        m["fl_clean_pct"] = max(0, round((m.get("fl_pct") or 0) - 100 * sum(lz.values()) / t, 1))
        if m.get("local_pct") is not None:
            m["local_clean_pct"] = max(0, round(m["local_pct"] - 100 * sum(a for z, a in lz.items() if z.startswith("342")) / t, 1))
    elif m.get("build_land_pct") is not None:
        m["land_pct"] = m["build_land_pct"]
        for k in ("local_pct", "fl_pct"):
            if m.get(k) is not None:
                m[k.replace("_pct", "_clean_pct")] = max(0, round(m[k] - m["build_land_pct"], 1))


def local_money(name):
    ln = lastname(name)
    hits = [(k, v) for k, v in LOCAL.items() if ln and ln in re.findall(r"[a-z'-]+", fold(k.split(",")[0]))]
    if len(hits) > 1:
        fn = fold(name).split()[0]
        hits = [h for h in hits if fn in fold(h[0])] or []
    if len(hits) != 1:          # ambiguous or none: show no money rather than someone else's
        return {}
    v = hits[0][1]
    return {"raised": v["raised"], "through": f"county reports, last item {v.get('last_report_item', '')}",
            "local_pct": v["pct_manatee"], "out_pct": v["pct_out_state"], "org_pct": v["pct_business_committee"],
            "build_land_pct": v["pct_building_land_tagged"], "land_pct": v["pct_building_land_tagged"],
            "local_clean_pct": max(0, round(v["pct_manatee"] - v["pct_building_land_tagged"], 1)), "loans": v["loans"] or None,
            "top": [[B_tc(re.sub(r"\s*\[.*?\]", "", a)), b, re.search(r"\](.*)", a).group(1).strip() if "]" in a else ""] for a, b, n in v["top_donors"][:10]],
            "source": "Manatee County Supervisor of Elections campaign reports, pulled Nov 2, 2026",
            "source_url": "https://www.votemanatee.gov/search-financial-reports/"}


def manatee_races(have_ids):
    blob = load(S / "research2" / "manatee.json", {}) or {}
    out = []
    for r in blob.get("races", []) + blob.get("measures", []):
        w = r.get("where")
        if not isinstance(w, dict) or not r.get("id") or r["id"] in have_ids:
            continue
        if any(k in w for k in ("cd", "sd", "hd")):      # district races come from the statewide slices
            continue
        w = dict(w, county="Manatee")
        if r.get("kind") == "measure":
            m = r.get("m") or r
            out.append({"kind": "measure", "group": "measures", "id": r["id"], "title": m.get("name") or r.get("office", ""),
                        "short": r.get("short") or (m.get("name") or "")[:18], "sub": r.get("sub", ""), "everyone": True, "where": w, "m": m})
            continue
        cands = [norm_cand(c) for c in r.get("candidates", []) if c.get("name")]
        if not cands:
            continue
        raw = {c["name"]: c for c in r.get("candidates", []) if c.get("name")}
        for c in cands:
            c["money"] = local_money(c["name"])
            ph = photo(dict(raw[c["name"]], name=c["name"]))
            if ph:
                c["photo"] = ph
        ranked = score_race(r["id"], "local", cands, "from Manatee County")
        out.append({"kind": "race", "group": "local", "id": r["id"], "title": r.get("office") or r.get("title") or r["id"],
                    "short": r.get("short") or (r.get("office") or r["id"])[:18], "sub": f"{len(cands)} candidates", "everyone": True,
                    "where": w, "note": r.get("note", ""), "cands": ranked})
    return out


QUALS = (load(S / "research3" / "qualifications.json", {}) or {}).get("candidates", {})
PRIO = load(S / "research3" / "priorities.json", {}) or {}


def bill_key(b):
    m = re.search(r"(HJR|SJR|HB|SB|H\.\s?R\.|S\.)\s*([0-9]+(?:-[A-Z])?)\b.*?\((\d{4})", str(b or ""))
    return f"{m.group(1).replace('.', '').replace(' ', '')}{m.group(2)}-{m.group(3)}" if m else None


# SB 2100 (2011) is left out: its plank reading rested on recollection, not a source.
BILLMAP = {bill_key(k): v for k, v in (PRIO.get("bill_map") or {}).items() if bill_key(k) and "2100" not in k}
for _c in (PRIO.get("candidates") or {}).values():
    for _k, _x in list((_c.get("planks") or {}).items()):
        if "2100" in str(_x.get("evidence", "")) and "2011" in str(_x.get("evidence", "")):
            _c["planks"].pop(_k)


# what candidates have DONE, checked against each plank (votes, actions in office, documented conduct), with contradictions
VERIFY = (load(S / "research3" / "verify_records.json", {}) or {}).get("candidates", {})
PLANK_IDS = {x["id"] for x in ((PRIO.get("platform") or {}).get("planks") or [])}
# a held plank reads as a record when it describes an action and not a promise or a platform line
DID_RE = re.compile(r"(?i)^voted|\b(voted|signed|sponsored|co-?sponsored|filed|sued|enforc\w*|ruled|approved|vetoed|appointed|credited|built|issued|passed|authored|introduced|cut|raised|blocked|opposed the|as (attorney general|commissioner|mayor|senator|governor|cfo))\b")
SAID_RE = re.compile(r"(?i)\b(platform|says|said|pledg\w*|promis\w*|campaign\w*|propos\w*|calls for|wants|website|questionnaire|statement|told|vows?|would|plans?|backs|supports?)\b")
PROMISE_PTS = 60      # a plank only promised counts 60 of 100: saying isn't doing


def plank_kind(x):
    ev = str(x.get("evidence") or "")
    return "did" if DID_RE.search(ev) and not SAID_RE.search(ev) else "said"


ROOTS = load(S / "research3" / "roots.json", {}) or {}
LAND_HIT = 40          # points off 🌾 Land per documented pro-data-center / pro-development position
INVESTORS_HIT = 15     # points off 💵 Independent when donors are pitched as "investors" at the candidate's event (sourced video only)


def apply_evidence(c):
    """Roots into 🏠 Local, documented land positions into 🌾 Land, the sourced 'investors' remark into 💵 Independent.
    Same rule for every candidate; nothing is set by hand."""
    sc = c["score"]
    ro = (ROOTS.get("roots") or {}).get(c["name"]) or {}
    if ro.get("roots") is not None:
        c["roots"] = {"v": ro["roots"], "summary": ro.get("summary") or "", "urls": ro.get("urls") or []}
        loc = sc.get("local")
        if loc and loc.get("v") is not None:
            loc["money_v"] = loc["v"]
            loc["v"] = round((loc["v"] + ro["roots"]) / 2)
            loc["label"] = f"Roots {ro['roots']}: {ro.get('summary') or ''} · Money: {loc['label']}"
        else:
            sc["local"] = {"v": ro["roots"], "label": f"Roots {ro['roots']}: {ro.get('summary') or ''}"}
    pos, seen = [], set()
    for x in (ROOTS.get("positions") or {}).get(c["name"]) or []:
        q = (x.get("quote_or_summary") or "").strip()
        key = re.sub(r"[^a-z]", "", q.lower())[:60]
        if not x.get("url") or x.get("stance") not in (1, -1) or re.match(r"(?i)same |corroborat", q) or key in seen:
            continue          # one count per statement: corroborating reports of the same quote don't add up
        seen.add(key); pos.append(x)
    if pos:
        c["land_positions"] = pos
        neg = sum(1 for x in pos if x["stance"] < 0); good = len(pos) - neg
        land = sc.get("land")
        base = land["v"] if land and land.get("v") is not None else 50      # positions only: start in the middle
        v = min(100, max(0, base - LAND_HIT * neg + 20 * good))
        lab = ((land["label"] + "; ") if land else "") + (f"{neg} documented position{'s' if neg != 1 else ''} for data centers or more development" if neg else "") + (f"{'; ' if neg else ''}{good} protecting land" if good else "")
        sc["land"] = {"v": v, "label": lab}
    inv = ROOTS.get("donalds_investors") or {}
    if c["name"] == "Byron Donalds" and inv.get("found") and inv.get("url"):
        ind = sc.get("indep")
        if ind and ind.get("v") is not None:
            ind["v"] = max(0, ind["v"] - INVESTORS_HIT)
            ind["parts"] = ind.get("parts", []) + [f"−{INVESTORS_HIT}: at his private event donors were pitched as “investors… shareholders” who “help steer” Florida ({inv.get('reported_by') or 'report'}, {inv.get('date') or ''})"]
        c.setdefault("controversies", []).insert(0, {"text": f"Donors pitched as “investors” at a private Donalds event. Said by {inv.get('speaker') or 'a speaker'}: “{inv.get('words', '')}” ({inv.get('reported_by', '')}, {inv.get('date', '')}).", "status": "established", "url": inv["url"]})


def finalize(races):
    """Add the job-fit and priorities meters, then re-score and re-rank each race.
    Overall = average of every meter that has a value. Candidates who raised too little for the money meters
    are still rated on qualification and priorities when those exist."""
    for r in races:
        if r.get("kind") != "race":
            continue
        for c in r["cands"]:
            q = QUALS.get(c["name"]) or {}
            if q:
                c["qual"] = {"v": q.get("qual"), "background": q.get("background"), "why": q.get("why"), "sources": q.get("sources", []),
                             "label": (q.get("why") or "") if q.get("qual") is not None else "Background not found: unknown, not unqualified"}
            pr = (PRIO.get("candidates") or {}).get(c["name"]) or {}
            planks = {k: dict(x, kind=plank_kind(x)) for k, x in (pr.get("planks") or {}).items()}

            def put(k, entry):
                prev = planks.get(k)
                if prev and prev.get("kind") == "said" and prev.get("match", 0) > 0 and entry["match"] < 0:
                    entry["contra"] = prev.get("evidence")      # says yes, record says no: the record wins
                planks[k] = entry
            # roll calls we hold, read through the bill->plank map (a record outranks a stated position)
            tally = defaultdict(list)
            for v in c.get("votes") or []:
                bm = BILLMAP.get(bill_key(v.get("bill")))
                if not bm or not re.match(r"(?i)y|n", v.get("vote") or "") or re.match(r"(?i)not", v.get("vote") or ""):
                    continue
                sign = bm["yea_means"] * (1 if re.match(r"(?i)y", v["vote"]) else -1)
                tally[bm["plank"]].append((sign, v))
            for k, xs in tally.items():
                tot = sum(x[0] for x in xs)
                if tot == 0 or (planks.get(k) or {}).get("kind") == "did":
                    continue
                v = xs[0][1]
                put(k, {"match": 1 if tot > 0 else -1, "url": v.get("url"), "kind": "did",
                        "evidence": f"Voted {v['vote']} on {v['bill']}" + (f" and {len(xs) - 1} related vote{'s' if len(xs) > 2 else ''}" if len(xs) > 1 else "")})
            # the record check: actions found in office, in the news and in public filings
            ver = VERIFY.get(c["name"]) or {}
            dids = defaultdict(list)
            for x in ver.get("did") or []:
                if x.get("plank") in PLANK_IDS and x.get("url") and x.get("match") in (1, -1) and x.get("what"):
                    dids[x["plank"]].append(x)
            for k, xs in dids.items():
                tot = sum(x["match"] for x in xs)
                prev = planks.get(k) or {}
                if tot == 0 or (prev.get("kind") == "did" and str(prev.get("evidence", "")).startswith("Voted")):
                    continue     # a split record decides nothing; roll calls stay
                best = next(x for x in xs if x["match"] == (1 if tot > 0 else -1))
                put(k, {"match": 1 if tot > 0 else -1, "url": best["url"], "evidence": best["what"], "kind": "did"})
            for x in ver.get("contradictions") or []:
                k = x.get("plank")
                if k in PLANK_IDS and x.get("url") and x.get("did") and x.get("said"):
                    said = ((pr.get("planks") or {}).get(k) or {}).get("match")
                    planks[k] = {"match": -said if said in (1, -1) else -1, "kind": "did", "evidence": x["did"], "url": x["url"], "contra": x["said"]}
            for k, x in planks.items():
                if x.get("contra"):
                    c.setdefault("controversies", []).append({"text": f"Says one thing, record shows another. They say: {x['contra']} The record: {x['evidence']}", "status": "established", "url": x.get("url")})
            if planks:
                n = len(planks)
                pos = sum(1 for x in planks.values() if x.get("match", 0) > 0)
                proven = sum(1 for x in planks.values() if x.get("kind") == "did")
                promised = sum(1 for x in planks.values() if x.get("kind") == "said" and x.get("match", 0) > 0)
                contra = sum(1 for x in planks.values() if x.get("contra"))
                pts = [(100 if x["kind"] == "did" else PROMISE_PTS) if x.get("match", 0) > 0 else 0 for x in planks.values()]
                c["prio"] = {"v": round(sum(pts) / n) if n >= 2 else None, "planks": planks, "proven": proven, "promised": promised, "contra": contra,
                             "label": f"Matches {pos} of {n} priorities; {proven} backed by their record, {promised} only promised"
                                      + (f"; {contra} where the record contradicts what they say" if contra else "") + ("" if n >= 2 else " (needs 2 to score)")}
            apply_evidence(c)
            sc = c["score"]
            if (sc.get("indep") or {}).get("v") is not None:
                money = [x["v"] for x in (sc.get("local"), sc.get("indep"), sc.get("foreign"), sc.get("land")) if x and x.get("v") is not None]
            else:   # no money data: only what rests on evidence counts (roots, documented land positions), never a money default
                money = [x["v"] for x, ok in ((sc.get("local"), c.get("roots")), (sc.get("land"), c.get("land_positions"))) if ok and x and x.get("v") is not None]
            extra = [x["v"] for x in (c.get("qual"), c.get("prio")) if x and x.get("v") is not None]
            vals = money + extra
            sc["overall"] = round(sum(vals) / len(vals)) if vals else None
            sc["basis"] = len(vals)
            if not money and extra:
                sc["why_money"] = sc.get("why")
        # fully rated candidates (4+ meters) rank above partly rated ones, then by score
        ranked = sorted(r["cands"], key=lambda c: (-(c["score"].get("indep") is not None), -(c["score"]["overall"] if c["score"]["overall"] is not None else -1)))
        for i, c in enumerate(ranked):
            c["rank"] = i + 1 if c["score"]["overall"] is not None else None
        r["cands"] = ranked


# ---------------- assemble ----------------
def main():
    d = json.loads((ROOT / "ballot-34221.json").read_text(encoding="utf-8"))
    shares = load(ROOT / "ballot" / "region_share.json", {})
    for part in d["parts"]:
        for r in part["races"]:
            for c in r.get("candidates") or []:
                ph = photo(c) if (c["name"] in photo_map or c["name"] in FOUND) else None
                if ph:
                    c["photo"] = ph
                v = VOTES40.get(c["name"])
                if v and v.get("votes"):
                    c["votes"] = [x for x in v["votes"] if x.get("vote") and x.get("url")]
    for part in d["parts"]:
        for r in part["races"]:
            for c in r.get("candidates") or []:
                add_land(c)
                owner_sweep(c)      # statewide + Manatee races get the scripted source sweep too, not only district races
    base = B.build(d, shares)
    WHERE = {"senate": {"all": 1}, "governor": {"all": 1}, "ag": {"all": 1}, "cfo": {"all": 1}, "agriculture": {"all": 1},
             "m0": {"all": 1}, "m1": {"all": 1}, "m2": {"all": 1},
             "house16": {"cd": 16}, "sd20": {"sd": 20}, "hd70": {"hd": 70}, "hd71": {"hd": 71},
             "cc6": {"county": "Manatee"}, "mosquito": {"county": "Manatee"}, "m3": {"county": "Manatee"},
             "cc1": {"county": "Manatee", "cc": 1}, "cc2": {"county": "Manatee", "cc": 2}, "sb2": {"county": "Manatee", "sb": 2},
             "palmetto2": {"county": "Manatee", "city": "Palmetto", "ward": 2}, "m4": {"county": "Manatee", "city": "Palmetto"}}
    races = []
    for r in base:
        if r["kind"] == "judges":       # split: Supreme Court is statewide; the appeals-court judges only verified for Manatee
            sc = [j for j in r["judges"] if "Mu" in j["name"]]
            dca = [j for j in r["judges"] if j not in sc]
            races.append(dict(r, id="supreme", short="Supreme Court", sub=f"{len(sc)} keep-or-remove vote", judges=sc, where={"all": 1},
                              note="Every Florida voter decides whether this Supreme Court justice stays."))
            races.append(dict(r, id="dca2", short="Appeals judges", sub=f"{len(dca)} keep-or-remove votes", judges=dca,
                              where={"county": "Manatee"}, note="Second District Court of Appeal judges on Manatee ballots."))
            continue
        r["where"] = WHERE.get(r["id"], {"county": "Manatee"})
        races.append(r)

    notes = []
    for fname in ("us_house.json", "legislature.json"):
        extra, done, n = research_races(fname, fname)
        have = {json.dumps(x["where"]) for x in races}
        for x in extra:
            if json.dumps(x["where"]) not in have:
                races.append(x)
        notes.append(f"{fname}: {len(extra)} races, done={done}")
    extra = manatee_races({r["id"] for r in races})
    races += extra
    notes.append(f"manatee.json: {len(extra)} new county/city items")

    finalize(races)
    OUT.mkdir(exist_ok=True)
    state = [r for r in races if r["where"].get("all")]
    buckets = defaultdict(list)
    for r in races:
        w = r["where"]
        if w.get("all"):
            continue
        key = f"cd-{w['cd']}" if "cd" in w else f"sd-{w['sd']}" if "sd" in w else f"hd-{w['hd']}" if "hd" in w else "county-" + slug(w["county"])
        buckets[key].append(r)
    for f in OUT.glob("*.json"):
        f.unlink()
    for k, rs in buckets.items():
        (OUT / f"{k}.json").write_text(json.dumps({"races": rs}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    zipt = {z: [v["cd"], v["sd"], v["hd"], v["county"], v.get("city")] for z, v in ZIPS.items()}
    soe = {k: [v.get("web"), v.get("phone"), v.get("addr")] for k, v in SOE.items()}
    data = {"title": "Ballot Buddy · Florida, Nov 3, 2026", "built": __import__("datetime").date.today().isoformat(), "boxes": d["boxes"], "footer": d["footer"],
            "groups": [{"id": a, "label": b, "icon": c} for a, b, c in B.GROUPS], "races": state, "files": sorted(buckets),
            "zips": zipt, "soe": soe, "coverage": SWEEP.get("coverage", []), "platform": PRIO.get("platform"),
            "rules": {"min": B.MIN_RAISED, "pac": B.FOREIGN_PAC_PENALTY, "foreign": [{"pts": p, "text": t} for _, p, t in B.FOREIGN_RULES]}}
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    tpl = (ROOT / "ballot" / "app_template.html").read_text(encoding="utf-8")
    page = tpl.replace("__TITLE__", data["title"]).replace("__DESC__", "Type your address and see every race on your Florida ballot, scored on local roots, foreign ties and big money.").replace("__DATA__", blob)
    (ROOT / "ballot.html").write_text(page, encoding="utf-8")
    (ROOT / "ballot" / "photos.json").write_text(json.dumps(photo_map, ensure_ascii=False, indent=1), encoding="utf-8")
    n = sum(len(r.get("cands", [])) for r in races)
    print(f"wrote ballot.html ({len(page)//1024} KB): {len(state)} statewide items, {len(buckets)} district files, {len(races)} items, {n} candidates")
    for x in notes:
        print("  ", x)


if __name__ == "__main__":
    main()
